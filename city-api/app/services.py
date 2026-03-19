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
    TaxPolicy,
    TreasuryEntry,
    TreasuryEntryType,
    Transaction,
)
from .schemas import (
    AgentCreate,
    CollectCitizenTaxRequest,
    ContractAwardRequest,
    ContractCreate,
    ListingCreate,
    MoltbookRegisterRequest,
    PurchaseRequest,
    TaxPolicyCreate,
    TreasuryDisbursementRequest,
)


MONEY_UNIT = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_UNIT)


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

    price = _round_money(Decimal(listing.asking_price))
    active_tax_policy = get_active_tax_policy(session)
    transfer_tax = Decimal("0.00")
    if active_tax_policy:
        transfer_tax = _round_money(
            price * Decimal(active_tax_policy.transfer_rate_percent) / Decimal("100")
        )

    total_cost = _round_money(price + transfer_tax)
    if Decimal(buyer.wallet_balance) < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    seller = None
    if listing.seller_agent_id:
        seller = session.scalar(select(Agent).where(Agent.id == listing.seller_agent_id).with_for_update())

    buyer.wallet_balance = _round_money(Decimal(buyer.wallet_balance) - total_cost)
    if seller:
        seller.wallet_balance = _round_money(Decimal(seller.wallet_balance) + price)

    parcel.owner_agent_id = buyer.id
    listing.status = ListingStatus.sold
    listing.closed_at = datetime.now(timezone.utc)

    if transfer_tax > 0:
        session.add(
            TreasuryEntry(
                entry_type=TreasuryEntryType.transfer_tax,
                amount=transfer_tax,
                source_agent_id=buyer.id,
                target_agent_id=None,
                note=f"Transfer tax for listing {listing.id}",
            )
        )

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
        "settled_volume": _round_money(Decimal(settled_volume)),
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


def get_active_tax_policy(session: Session) -> TaxPolicy | None:
    return session.scalar(select(TaxPolicy).where(TaxPolicy.active.is_(True)).order_by(TaxPolicy.id.desc()))


def create_tax_policy(session: Session, payload: TaxPolicyCreate) -> TaxPolicy:
    _require_government_citizen(session, payload.created_by_agent_id)

    active_policies = session.scalars(select(TaxPolicy).where(TaxPolicy.active.is_(True))).all()
    for policy in active_policies:
        policy.active = False

    policy = TaxPolicy(
        name=payload.name,
        citizen_rate_percent=payload.citizen_rate_percent,
        transfer_rate_percent=payload.transfer_rate_percent,
        active=True,
        created_by_agent_id=payload.created_by_agent_id,
    )
    session.add(policy)
    session.flush()
    session.refresh(policy)
    return policy


def collect_citizen_tax(session: Session, payload: CollectCitizenTaxRequest) -> list[TreasuryEntry]:
    _require_government_citizen(session, payload.collected_by_agent_id)
    active_policy = get_active_tax_policy(session)
    if not active_policy:
        raise HTTPException(status_code=400, detail="No active tax policy found")

    query = select(Agent).where(
        Agent.citizenship_status == CitizenshipStatus.citizen,
        Agent.agent_type != AgentType.government,
    )
    if payload.agent_ids:
        query = query.where(Agent.id.in_(payload.agent_ids))

    citizens = session.scalars(query).all()
    entries: list[TreasuryEntry] = []
    for citizen in citizens:
        tax = _round_money(
            Decimal(citizen.wallet_balance) * Decimal(active_policy.citizen_rate_percent) / Decimal("100")
        )
        if tax <= 0:
            continue
        if Decimal(citizen.wallet_balance) < tax:
            tax = _round_money(Decimal(citizen.wallet_balance))
        if tax <= 0:
            continue

        citizen.wallet_balance = _round_money(Decimal(citizen.wallet_balance) - tax)
        entry = TreasuryEntry(
            entry_type=TreasuryEntryType.citizen_tax,
            amount=tax,
            source_agent_id=citizen.id,
            target_agent_id=None,
            note=payload.note or f"Citizen tax collection by {payload.collected_by_agent_id}",
        )
        session.add(entry)
        entries.append(entry)

    session.flush()
    return entries


def treasury_totals(session: Session) -> dict[str, Decimal]:
    collected = session.scalar(
        select(func.coalesce(func.sum(TreasuryEntry.amount), 0)).where(
            TreasuryEntry.entry_type.in_([TreasuryEntryType.citizen_tax, TreasuryEntryType.transfer_tax])
        )
    ) or Decimal("0.00")
    disbursed = session.scalar(
        select(func.coalesce(func.sum(TreasuryEntry.amount), 0)).where(
            TreasuryEntry.entry_type == TreasuryEntryType.disbursement
        )
    ) or Decimal("0.00")

    collected_amount = _round_money(Decimal(collected))
    disbursed_amount = _round_money(Decimal(disbursed))
    return {
        "total_collected": collected_amount,
        "total_disbursed": disbursed_amount,
        "treasury_balance": _round_money(collected_amount - disbursed_amount),
    }


def disburse_treasury_funds(session: Session, payload: TreasuryDisbursementRequest) -> TreasuryEntry:
    _require_government_citizen(session, payload.authorized_by_agent_id)

    target_agent = session.scalar(select(Agent).where(Agent.id == payload.target_agent_id))
    if not target_agent:
        raise HTTPException(status_code=404, detail="Target agent not found")

    amount = _round_money(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Disbursement amount must be greater than zero")

    totals = treasury_totals(session)
    if totals["treasury_balance"] < amount:
        raise HTTPException(status_code=400, detail="Insufficient treasury balance")

    target_agent.wallet_balance = _round_money(Decimal(target_agent.wallet_balance) + amount)
    entry = TreasuryEntry(
        entry_type=TreasuryEntryType.disbursement,
        amount=amount,
        source_agent_id=payload.authorized_by_agent_id,
        target_agent_id=target_agent.id,
        note=payload.note or "Treasury disbursement",
    )
    session.add(entry)
    session.flush()
    session.refresh(entry)
    return entry
