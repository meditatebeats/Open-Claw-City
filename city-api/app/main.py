from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import engine, get_session
from .models import (
    Agent,
    Base,
    GovernmentContract,
    Listing,
    ListingStatus,
    Parcel,
    Passport,
    TaxPolicy,
    TreasuryEntry,
    Transaction,
)
from .schemas import (
    AgentCreate,
    AgentRead,
    CollectCitizenTaxRequest,
    CitizenshipGrantRequest,
    CityStats,
    ContractAwardRequest,
    ContractCreate,
    GovernmentContractRead,
    ListingCreate,
    ListingRead,
    MoltbookRegisterRequest,
    ParcelCreate,
    ParcelRead,
    PurchaseRequest,
    TaxPolicyCreate,
    TaxPolicyRead,
    TreasuryDisbursementRequest,
    TreasuryEntryRead,
    TreasurySummary,
    TransactionRead,
)
from .services import (
    award_contract,
    buy_listing,
    city_stats,
    create_agent,
    create_contract,
    create_listing,
    create_tax_policy,
    disburse_treasury_funds,
    grant_citizenship,
    collect_citizen_tax,
    register_moltbook_agent,
    treasury_totals,
)

settings = get_settings()
app = FastAPI(title=f"{settings.city_name} API", version="0.2.0")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _to_agent_read(agent: Agent) -> AgentRead:
    passport_number = agent.passport.passport_number if agent.passport else None
    return AgentRead.model_validate({
        **agent.__dict__,
        "passport_number": passport_number,
    })


@app.get("/city/stats", response_model=CityStats)
def get_city_stats(session: Session = Depends(get_session)) -> CityStats:
    return CityStats(**city_stats(session))


@app.post("/agents", response_model=AgentRead, status_code=201)
def create_city_agent(payload: AgentCreate, session: Session = Depends(get_session)) -> AgentRead:
    return _to_agent_read(create_agent(session, payload))


@app.post("/moltbook/register", response_model=AgentRead)
def register_via_moltbook(
    payload: MoltbookRegisterRequest,
    session: Session = Depends(get_session),
    x_moltbook_token: str | None = Header(default=None, alias="X-Moltbook-Token"),
) -> AgentRead:
    expected = settings.moltbook_registration_token
    if expected and x_moltbook_token != expected:
        raise HTTPException(status_code=401, detail="Invalid Moltbook registration token")

    return _to_agent_read(register_moltbook_agent(session, payload))


@app.get("/agents", response_model=list[AgentRead])
def list_agents(session: Session = Depends(get_session)) -> list[AgentRead]:
    agents = session.scalars(select(Agent).order_by(Agent.created_at.desc())).all()
    return [_to_agent_read(agent) for agent in agents]


@app.post("/governance/citizenship/grant", response_model=AgentRead)
def grant_city_citizenship(
    payload: CitizenshipGrantRequest,
    session: Session = Depends(get_session),
) -> AgentRead:
    return _to_agent_read(grant_citizenship(session, payload.agent_id, payload.granted_by_agent_id))


@app.post("/parcels", response_model=ParcelRead, status_code=201)
def create_parcel(payload: ParcelCreate, session: Session = Depends(get_session)) -> ParcelRead:
    parcel = Parcel(**payload.model_dump())
    session.add(parcel)
    session.flush()
    session.refresh(parcel)
    return ParcelRead.model_validate(parcel)


@app.get("/parcels", response_model=list[ParcelRead])
def list_parcels(
    owner_agent_id: str | None = None,
    for_sale: bool = False,
    session: Session = Depends(get_session),
) -> list[ParcelRead]:
    query = select(Parcel)
    if owner_agent_id:
        query = query.where(Parcel.owner_agent_id == owner_agent_id)

    parcels = session.scalars(query.order_by(Parcel.id.asc())).all()
    if for_sale:
        open_ids = set(
            session.scalars(select(Listing.parcel_id).where(Listing.status == ListingStatus.open)).all()
        )
        parcels = [parcel for parcel in parcels if parcel.id in open_ids]

    return [ParcelRead.model_validate(parcel) for parcel in parcels]


@app.post("/listings", response_model=ListingRead, status_code=201)
def create_property_listing(payload: ListingCreate, session: Session = Depends(get_session)) -> ListingRead:
    listing = create_listing(session, payload)
    return ListingRead.model_validate(listing)


@app.get("/listings", response_model=list[ListingRead])
def list_listings(
    status: ListingStatus = ListingStatus.open,
    session: Session = Depends(get_session),
) -> list[ListingRead]:
    listings = session.scalars(
        select(Listing).where(Listing.status == status).order_by(Listing.created_at.desc())
    ).all()
    return [ListingRead.model_validate(item) for item in listings]


@app.post("/listings/{listing_id}/buy", response_model=TransactionRead, status_code=201)
def buy_property(
    listing_id: int,
    payload: PurchaseRequest,
    session: Session = Depends(get_session),
) -> TransactionRead:
    tx = buy_listing(session, listing_id, payload)
    return TransactionRead.model_validate(tx)


@app.get("/transactions", response_model=list[TransactionRead])
def list_transactions(limit: int = 100, session: Session = Depends(get_session)) -> list[TransactionRead]:
    safe_limit = min(max(limit, 1), 500)
    txs = session.scalars(
        select(Transaction).order_by(Transaction.settled_at.desc()).limit(safe_limit)
    ).all()
    return [TransactionRead.model_validate(tx) for tx in txs]


@app.post("/treasury/tax-policies", response_model=TaxPolicyRead, status_code=201)
def create_tax_policy_endpoint(
    payload: TaxPolicyCreate,
    session: Session = Depends(get_session),
) -> TaxPolicyRead:
    policy = create_tax_policy(session, payload)
    return TaxPolicyRead.model_validate(policy)


@app.get("/treasury/tax-policies", response_model=list[TaxPolicyRead])
def list_tax_policies(
    active_only: bool = False,
    session: Session = Depends(get_session),
) -> list[TaxPolicyRead]:
    query = select(TaxPolicy).order_by(TaxPolicy.created_at.desc())
    if active_only:
        query = query.where(TaxPolicy.active.is_(True))
    policies = session.scalars(query).all()
    return [TaxPolicyRead.model_validate(policy) for policy in policies]


@app.post("/treasury/collect/citizen", response_model=list[TreasuryEntryRead], status_code=201)
def collect_citizen_taxes_endpoint(
    payload: CollectCitizenTaxRequest,
    session: Session = Depends(get_session),
) -> list[TreasuryEntryRead]:
    entries = collect_citizen_tax(session, payload)
    return [TreasuryEntryRead.model_validate(entry) for entry in entries]


@app.post("/treasury/disburse", response_model=TreasuryEntryRead, status_code=201)
def disburse_treasury_endpoint(
    payload: TreasuryDisbursementRequest,
    session: Session = Depends(get_session),
) -> TreasuryEntryRead:
    entry = disburse_treasury_funds(session, payload)
    return TreasuryEntryRead.model_validate(entry)


@app.get("/treasury/summary", response_model=TreasurySummary)
def get_treasury_summary(session: Session = Depends(get_session)) -> TreasurySummary:
    totals = treasury_totals(session)
    entry_count = session.scalar(select(func.count(TreasuryEntry.id))) or 0
    return TreasurySummary(
        treasury_balance=totals["treasury_balance"],
        total_collected=totals["total_collected"],
        total_disbursed=totals["total_disbursed"],
        entry_count=int(entry_count),
    )


@app.get("/treasury/entries", response_model=list[TreasuryEntryRead])
def list_treasury_entries(
    limit: int = 200,
    session: Session = Depends(get_session),
) -> list[TreasuryEntryRead]:
    safe_limit = min(max(limit, 1), 1000)
    entries = session.scalars(
        select(TreasuryEntry).order_by(TreasuryEntry.created_at.desc()).limit(safe_limit)
    ).all()
    return [TreasuryEntryRead.model_validate(entry) for entry in entries]


@app.post("/governance/contracts", response_model=GovernmentContractRead, status_code=201)
def publish_contract(payload: ContractCreate, session: Session = Depends(get_session)) -> GovernmentContractRead:
    contract = create_contract(session, payload)
    return GovernmentContractRead.model_validate(contract)


@app.get("/governance/contracts", response_model=list[GovernmentContractRead])
def list_contracts(session: Session = Depends(get_session)) -> list[GovernmentContractRead]:
    contracts = session.scalars(
        select(GovernmentContract).order_by(GovernmentContract.created_at.desc())
    ).all()
    return [GovernmentContractRead.model_validate(contract) for contract in contracts]


@app.post("/governance/contracts/{contract_id}/award", response_model=GovernmentContractRead)
def assign_contract(
    contract_id: int,
    payload: ContractAwardRequest,
    session: Session = Depends(get_session),
) -> GovernmentContractRead:
    contract = award_contract(session, contract_id, payload)
    return GovernmentContractRead.model_validate(contract)


@app.get("/passports")
def list_passports(session: Session = Depends(get_session)) -> list[dict[str, str]]:
    passports = session.scalars(select(Passport).order_by(Passport.issued_at.desc())).all()
    return [
        {
            "passport_number": passport.passport_number,
            "agent_id": passport.agent_id,
            "jurisdiction": passport.jurisdiction,
            "issued_at": passport.issued_at.isoformat(),
        }
        for passport in passports
    ]
