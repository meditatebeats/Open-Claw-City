from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import secrets

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    Agent,
    AgentType,
    CitizenshipStatus,
    ContractStatus,
    GovernmentContract,
    Listing,
    ListingStatus,
    Parcel,
    Passport,
    Transaction,
)
from .schemas import (
    AgentCreate,
    ContractAwardRequest,
    ContractCreate,
    ListingCreate,
    MoltbookRegisterRequest,
    PurchaseRequest,
)


def create_agent(session: Session, payload: AgentCreate) -> Agent:
    existing = session.scalar(select(Agent).where(Agent.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Agent name already exists")

    if payload.moltbook_agent_id:
        existing_moltbook = session.scalar(
            select(Agent).where(Agent.moltbook_agent_id == payload.moltbook_agent_id)
        )
        if existing_moltbook:
            raise HTTPException(status_code=409, detail="Moltbook agent already registered")

    agent = Agent(
        name=payload.name,
        agent_type=payload.agent_type,
        wallet_balance=payload.initial_balance,
        moltbook_agent_id=payload.moltbook_agent_id,
        citizenship_status=(
            CitizenshipStatus.citizen if payload.agent_type == AgentType.government else CitizenshipStatus.resident
        ),
    )
    session.add(agent)
    session.flush()

    if payload.issue_passport:
        issue_passport(session, agent)

    session.refresh(agent)
    return agent


def issue_passport(session: Session, agent: Agent) -> Passport:
    settings = get_settings()
    passport = Passport(
        agent_id=agent.id,
        passport_number=f"OCC-{secrets.token_hex(4).upper()}",
        jurisdiction=settings.default_jurisdiction,
    )
    session.add(passport)
    session.flush()
    return passport


def create_listing(session: Session, payload: ListingCreate) -> Listing:
    parcel = session.scalar(select(Parcel).where(Parcel.id == payload.parcel_id))
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    if payload.seller_agent_id:
        if parcel.owner_agent_id != payload.seller_agent_id:
            raise HTTPException(status_code=400, detail="Seller does not own the parcel")
    else:
        if parcel.owner_agent_id is not None:
            raise HTTPException(status_code=400, detail="City can only list unowned parcels")

    open_listing = session.scalar(
        select(Listing).where(Listing.parcel_id == payload.parcel_id, Listing.status == ListingStatus.open)
    )
    if open_listing:
        raise HTTPException(status_code=409, detail="Parcel already has an active listing")

    listing = Listing(
        parcel_id=payload.parcel_id,
        seller_agent_id=payload.seller_agent_id,
        asking_price=payload.asking_price,
        status=ListingStatus.open,
    )
    session.add(listing)
    session.flush()
    session.refresh(listing)
    return listing


def buy_listing(session: Session, listing_id: int, payload: PurchaseRequest) -> Transaction:
    listing = session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != ListingStatus.open:
        raise HTTPException(status_code=409, detail="Listing is no longer open")

    parcel = session.scalar(select(Parcel).where(Parcel.id == listing.parcel_id).with_for_update())
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    buyer = session.scalar(select(Agent).where(Agent.id == payload.buyer_agent_id).with_for_update())
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer agent not found")

    if listing.seller_agent_id == buyer.id:
        raise HTTPException(status_code=400, detail="Agent cannot buy their own listing")

    price = Decimal(listing.asking_price)
    if Decimal(buyer.wallet_balance) < price:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    seller = None
    if listing.seller_agent_id:
        seller = session.scalar(select(Agent).where(Agent.id == listing.seller_agent_id).with_for_update())

    buyer.wallet_balance = Decimal(buyer.wallet_balance) - price
    if seller:
        seller.wallet_balance = Decimal(seller.wallet_balance) + price

    parcel.owner_agent_id = buyer.id
    listing.status = ListingStatus.sold
    listing.closed_at = datetime.now(timezone.utc)

    tx = Transaction(
        listing_id=listing.id,
        parcel_id=parcel.id,
        buyer_agent_id=buyer.id,
        seller_agent_id=listing.seller_agent_id,
        price=price,
        note=payload.note,
    )
    session.add(tx)
    session.flush()
    session.refresh(tx)
    return tx


def city_stats(session: Session) -> dict[str, int | str | Decimal]:
    settings = get_settings()
    registered_agents = session.scalar(select(func.count(Agent.id))) or 0
    active_listings = session.scalar(select(func.count(Listing.id)).where(Listing.status == ListingStatus.open)) or 0
    total_parcels = session.scalar(select(func.count(Parcel.id))) or 0
    settled_volume = session.scalar(select(func.coalesce(func.sum(Transaction.price), 0))) or Decimal("0.00")

    return {
        "city_name": settings.city_name,
        "registered_agents": int(registered_agents),
        "active_listings": int(active_listings),
        "total_parcels": int(total_parcels),
        "settled_volume": Decimal(settled_volume),
    }


def register_moltbook_agent(session: Session, payload: MoltbookRegisterRequest) -> Agent:
    existing = session.scalar(select(Agent).where(Agent.moltbook_agent_id == payload.moltbook_agent_id))
    if existing:
        return existing

    generated_name = payload.display_name.strip()
    if not generated_name:
        raise HTTPException(status_code=400, detail="Display name is required")

    if session.scalar(select(Agent).where(Agent.name == generated_name)):
        generated_name = f"{generated_name}-{payload.moltbook_agent_id[:6]}"

    agent_payload = AgentCreate(
        name=generated_name,
        agent_type=payload.agent_type,
        moltbook_agent_id=payload.moltbook_agent_id,
        initial_balance=payload.initial_balance,
        issue_passport=True,
    )
    return create_agent(session, agent_payload)


def _require_government_citizen(session: Session, agent_id: str) -> Agent:
    agent = session.scalar(select(Agent).where(Agent.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Government agent not found")
    if agent.agent_type != AgentType.government:
        raise HTTPException(status_code=403, detail="Only government agents may perform this action")
    if agent.citizenship_status != CitizenshipStatus.citizen:
        raise HTTPException(status_code=403, detail="Government agent must hold city citizenship")
    return agent


def grant_citizenship(session: Session, agent_id: str, granted_by_agent_id: str) -> Agent:
    _require_government_citizen(session, granted_by_agent_id)

    agent = session.scalar(select(Agent).where(Agent.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Target agent not found")
    if not agent.passport:
        raise HTTPException(status_code=400, detail="Agent must have a passport before citizenship")

    agent.citizenship_status = CitizenshipStatus.citizen
    session.flush()
    session.refresh(agent)
    return agent


def create_contract(session: Session, payload: ContractCreate) -> GovernmentContract:
    _require_government_citizen(session, payload.issuing_agency_id)
    contract = GovernmentContract(
        title=payload.title,
        scope=payload.scope,
        budget=payload.budget,
        issuing_agency_id=payload.issuing_agency_id,
        human_guardrail_policy=payload.human_guardrail_policy,
        human_outcome_target=payload.human_outcome_target,
        status=ContractStatus.published,
    )
    session.add(contract)
    session.flush()
    session.refresh(contract)
    return contract


def award_contract(session: Session, contract_id: int, payload: ContractAwardRequest) -> GovernmentContract:
    contract = session.scalar(select(GovernmentContract).where(GovernmentContract.id == contract_id).with_for_update())
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.status not in (ContractStatus.published, ContractStatus.draft):
        raise HTTPException(status_code=409, detail="Contract cannot be awarded from current status")

    issuer = _require_government_citizen(session, payload.awarded_by_agent_id)
    if issuer.id != contract.issuing_agency_id:
        raise HTTPException(status_code=403, detail="Only the issuing agency can award this contract")

    winner = session.scalar(select(Agent).where(Agent.id == payload.winning_agent_id))
    if not winner:
        raise HTTPException(status_code=404, detail="Winning agent not found")
    if winner.citizenship_status != CitizenshipStatus.citizen:
        raise HTTPException(status_code=400, detail="Winning agent must hold citizenship")

    contract.winning_agent_id = winner.id
    contract.status = ContractStatus.awarded
    contract.awarded_at = datetime.now(timezone.utc)
    session.flush()
    session.refresh(contract)
    return contract
