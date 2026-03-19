from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import engine, get_session
from .models import (
    Agent,
    AgentCommunity,
    AuditActionType,
    Base,
    CommunityAuditRecord,
    CommunityLeadershipTerm,
    CommunityMembership,
    CommunityProposal,
    Employment,
    EmploymentStatus,
    GovernmentContract,
    Institution,
    JobRole,
    JobStatus,
    Listing,
    ListingStatus,
    Parcel,
    ParcelUsage,
    ParcelUsageState,
    Passport,
    SimulationCycle,
    TaxPolicy,
    TreasuryEntry,
    Transaction,
    TrustTier,
)
from .schemas import (
    AgentCreate,
    AgentRead,
    CityManifest,
    CityStats,
    CollectCitizenTaxRequest,
    CommunityAuditRead,
    CommunityConsensusRead,
    CommunityCreate,
    CommunityLeadershipCreate,
    CommunityLeadershipRead,
    CommunityMembershipCreate,
    CommunityMembershipRead,
    CommunityMembershipRemoveRequest,
    CommunityProposalCreate,
    CommunityProposalRead,
    CommunityProposalResolveRequest,
    CommunityProposalVoteRequest,
    CommunityRead,
    CommunityUpdateRequest,
    CommunityVoteRead,
    ContractAwardRequest,
    ContractCreate,
    CitizenshipGrantRequest,
    EmploymentAssignRequest,
    EmploymentRead,
    GovernanceAuditRead,
    GovernmentContractRead,
    InstitutionCreate,
    InstitutionRead,
    JobCreate,
    JobRead,
    ListingCreate,
    ListingRead,
    MoltbookRegisterRequest,
    NemoContext,
    NemoToolSpec,
    ParcelCreate,
    ParcelRead,
    ParcelUsageUpdateRequest,
    PurchaseRequest,
    SimulationCycleRead,
    SimulationTickRequest,
    TaxPolicyCreate,
    TaxPolicyRead,
    TreasuryDisbursementRequest,
    TreasuryEntryRead,
    TreasurySummary,
    TransactionRead,
)
from .services import (
    add_community_member,
    assign_employment,
    award_contract,
    buy_listing,
    cast_community_vote,
    city_stats,
    collect_citizen_tax,
    create_community,
    create_community_leadership_term,
    create_community_proposal,
    create_agent,
    create_contract,
    create_institution,
    create_job,
    create_listing,
    create_tax_policy,
    disburse_treasury_funds,
    grant_citizenship,
    list_audit_events,
    remove_community_member,
    register_moltbook_agent,
    resolve_community_proposal,
    run_simulation_tick,
    set_parcel_usage_state,
    treasury_totals,
    update_community,
)

settings = get_settings()
app = FastAPI(title=f"{settings.city_name} API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _to_agent_read(agent: Agent) -> AgentRead:
    passport_number = agent.passport.passport_number if agent.passport else None
    trust_tier = TrustTier.resident
    reputation_score = Decimal("0.00")
    if agent.trust_profile:
        trust_tier = agent.trust_profile.trust_tier
        reputation_score = agent.trust_profile.reputation_score
    return AgentRead.model_validate(
        {
            **agent.__dict__,
            "passport_number": passport_number,
            "trust_tier": trust_tier,
            "reputation_score": reputation_score,
        }
    )


def _to_parcel_read(session: Session, parcel: Parcel) -> ParcelRead:
    usage = session.scalar(select(ParcelUsage).where(ParcelUsage.parcel_id == parcel.id))
    usage_state = usage.usage_state if usage else ParcelUsageState.unassigned
    return ParcelRead.model_validate({**parcel.__dict__, "usage_state": usage_state})


@app.get("/city/manifest", response_model=CityManifest)
def city_manifest() -> CityManifest:
    return CityManifest(
        city_name=settings.city_name,
        api_version=app.version,
        enrollment_mode=settings.enrollment_mode,
        communication_channel=settings.agent_communication_channel,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )


@app.get("/integrations/nemo/context", response_model=NemoContext)
def nemo_context(session: Session = Depends(get_session)) -> NemoContext:
    stats_payload = CityStats(**city_stats(session))
    return NemoContext(
        city_name=settings.city_name,
        api_version=app.version,
        guardrail_principle=(
            "Human beings are always to be served and protected. "
            f"Agent-to-agent community communication channel: {settings.agent_communication_channel}."
        ),
        stats=stats_payload,
        tools=[
            NemoToolSpec(
                name="register_passport",
                method="POST",
                path="/moltbook/register",
                description="Register a Moltbook identity and issue a city passport.",
                requires_rationale=False,
            ),
            NemoToolSpec(
                name="grant_citizenship",
                method="POST",
                path="/governance/citizenship/grant",
                description="Grant citizenship with required rationale and audit trail.",
                requires_rationale=True,
            ),
            NemoToolSpec(
                name="assign_employment",
                method="POST",
                path="/employment/assign",
                description="Assign an agent to a city job role with rationale.",
                requires_rationale=True,
            ),
            NemoToolSpec(
                name="run_simulation_tick",
                method="POST",
                path="/simulation/tick",
                description="Process payroll/output cycles for active employment.",
                requires_rationale=True,
            ),
            NemoToolSpec(
                name="buy_listing",
                method="POST",
                path="/listings/{listing_id}/buy",
                description="Buy property listing and update parcel ownership.",
                requires_rationale=False,
            ),
            NemoToolSpec(
                name="treasury_disburse",
                method="POST",
                path="/treasury/disburse",
                description="Disburse funds with threshold-based human confirmation.",
                requires_rationale=True,
            ),
            NemoToolSpec(
                name="community_proposal",
                method="POST",
                path="/communities/{community_id}/proposals",
                description="Create Moltbook-threaded community proposals under city law.",
                requires_rationale=False,
            ),
            NemoToolSpec(
                name="community_vote",
                method="POST",
                path="/proposals/{proposal_id}/vote",
                description="Cast proposal vote with Moltbook thread reference.",
                requires_rationale=False,
            ),
        ],
    )


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
    if settings.enrollment_mode == "token_required":
        expected = settings.moltbook_registration_token
        if not expected:
            raise HTTPException(
                status_code=503,
                detail="Enrollment mode requires OCC_MOLTBOOK_REGISTRATION_TOKEN to be configured",
            )
        if x_moltbook_token != expected:
            raise HTTPException(status_code=401, detail="Invalid Moltbook registration token")

    return _to_agent_read(register_moltbook_agent(session, payload))


@app.get("/agents", response_model=list[AgentRead])
def list_agents(session: Session = Depends(get_session)) -> list[AgentRead]:
    agents = session.scalars(select(Agent).order_by(Agent.created_at.desc())).all()
    return [_to_agent_read(agent) for agent in agents]


@app.post("/communities", response_model=CommunityRead, status_code=201)
def create_community_endpoint(payload: CommunityCreate, session: Session = Depends(get_session)) -> CommunityRead:
    community = create_community(session, payload)
    return CommunityRead.model_validate(community)


@app.get("/communities", response_model=list[CommunityRead])
def list_communities(session: Session = Depends(get_session)) -> list[CommunityRead]:
    communities = session.scalars(select(AgentCommunity).order_by(AgentCommunity.created_at.desc())).all()
    return [CommunityRead.model_validate(item) for item in communities]


@app.get("/communities/{community_id}", response_model=CommunityRead)
def get_community(community_id: int, session: Session = Depends(get_session)) -> CommunityRead:
    community = session.scalar(select(AgentCommunity).where(AgentCommunity.id == community_id))
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return CommunityRead.model_validate(community)


@app.patch("/communities/{community_id}", response_model=CommunityRead)
def patch_community(
    community_id: int,
    payload: CommunityUpdateRequest,
    session: Session = Depends(get_session),
) -> CommunityRead:
    community = update_community(session, community_id, payload)
    return CommunityRead.model_validate(community)


@app.post("/communities/{community_id}/members", response_model=CommunityMembershipRead, status_code=201)
def add_member(
    community_id: int,
    payload: CommunityMembershipCreate,
    session: Session = Depends(get_session),
) -> CommunityMembershipRead:
    membership = add_community_member(session, community_id, payload)
    return CommunityMembershipRead.model_validate(membership)


@app.get("/communities/{community_id}/members", response_model=list[CommunityMembershipRead])
def list_members(community_id: int, session: Session = Depends(get_session)) -> list[CommunityMembershipRead]:
    members = session.scalars(
        select(CommunityMembership)
        .where(CommunityMembership.community_id == community_id)
        .order_by(CommunityMembership.joined_at.desc())
    ).all()
    return [CommunityMembershipRead.model_validate(item) for item in members]


@app.delete("/communities/{community_id}/members/{agent_id}", response_model=CommunityMembershipRead)
def remove_member(
    community_id: int,
    agent_id: str,
    payload: CommunityMembershipRemoveRequest,
    session: Session = Depends(get_session),
) -> CommunityMembershipRead:
    membership = remove_community_member(
        session,
        community_id=community_id,
        agent_id=agent_id,
        removed_by_agent_id=payload.removed_by_agent_id,
        rationale=payload.rationale,
    )
    return CommunityMembershipRead.model_validate(membership)


@app.post("/communities/{community_id}/proposals", response_model=CommunityProposalRead, status_code=201)
def create_proposal(
    community_id: int,
    payload: CommunityProposalCreate,
    session: Session = Depends(get_session),
) -> CommunityProposalRead:
    proposal = create_community_proposal(session, community_id=community_id, payload=payload)
    return CommunityProposalRead.model_validate(proposal)


@app.get("/communities/{community_id}/proposals", response_model=list[CommunityProposalRead])
def list_community_proposals(community_id: int, session: Session = Depends(get_session)) -> list[CommunityProposalRead]:
    proposals = session.scalars(
        select(CommunityProposal)
        .where(CommunityProposal.community_id == community_id)
        .order_by(CommunityProposal.created_at.desc())
    ).all()
    return [CommunityProposalRead.model_validate(item) for item in proposals]


@app.get("/proposals/{proposal_id}", response_model=CommunityProposalRead)
def get_proposal(proposal_id: int, session: Session = Depends(get_session)) -> CommunityProposalRead:
    proposal = session.scalar(select(CommunityProposal).where(CommunityProposal.id == proposal_id))
    if not proposal:
        raise HTTPException(status_code=404, detail="Community proposal not found")
    return CommunityProposalRead.model_validate(proposal)


@app.post("/proposals/{proposal_id}/vote", response_model=CommunityVoteRead, status_code=201)
def vote_proposal(
    proposal_id: int,
    payload: CommunityProposalVoteRequest,
    session: Session = Depends(get_session),
) -> CommunityVoteRead:
    vote = cast_community_vote(session, proposal_id=proposal_id, payload=payload)
    return CommunityVoteRead.model_validate(vote)


@app.post("/proposals/{proposal_id}/resolve", response_model=CommunityConsensusRead, status_code=201)
def resolve_proposal(
    proposal_id: int,
    payload: CommunityProposalResolveRequest,
    session: Session = Depends(get_session),
) -> CommunityConsensusRead:
    record = resolve_community_proposal(session, proposal_id=proposal_id, payload=payload)
    return CommunityConsensusRead.model_validate(record)


@app.post("/communities/{community_id}/leadership", response_model=CommunityLeadershipRead, status_code=201)
def create_leadership_term(
    community_id: int,
    payload: CommunityLeadershipCreate,
    session: Session = Depends(get_session),
) -> CommunityLeadershipRead:
    term = create_community_leadership_term(session, community_id=community_id, payload=payload)
    return CommunityLeadershipRead.model_validate(term)


@app.get("/communities/{community_id}/leadership", response_model=list[CommunityLeadershipRead])
def list_leadership_terms(community_id: int, session: Session = Depends(get_session)) -> list[CommunityLeadershipRead]:
    terms = session.scalars(
        select(CommunityLeadershipTerm)
        .where(CommunityLeadershipTerm.community_id == community_id)
        .order_by(CommunityLeadershipTerm.term_start.desc())
    ).all()
    return [CommunityLeadershipRead.model_validate(item) for item in terms]


@app.get("/communities/{community_id}/audit", response_model=list[CommunityAuditRead])
def list_community_audit(community_id: int, limit: int = 200, session: Session = Depends(get_session)) -> list[CommunityAuditRead]:
    safe_limit = min(max(limit, 1), 1000)
    records = session.scalars(
        select(CommunityAuditRecord)
        .where(CommunityAuditRecord.community_id == community_id)
        .order_by(CommunityAuditRecord.created_at.desc())
        .limit(safe_limit)
    ).all()
    return [CommunityAuditRead.model_validate(item) for item in records]


@app.post("/governance/citizenship/grant", response_model=AgentRead)
def grant_city_citizenship(
    payload: CitizenshipGrantRequest,
    session: Session = Depends(get_session),
) -> AgentRead:
    return _to_agent_read(grant_citizenship(session, payload.agent_id, payload.granted_by_agent_id, payload.rationale))


@app.post("/parcels", response_model=ParcelRead, status_code=201)
def create_parcel(payload: ParcelCreate, session: Session = Depends(get_session)) -> ParcelRead:
    parcel = Parcel(
        district=payload.district,
        lot_number=payload.lot_number,
        zoning=payload.zoning,
        area_sq_m=payload.area_sq_m,
        base_price=payload.base_price,
    )
    session.add(parcel)
    session.flush()
    session.add(
        ParcelUsage(
            parcel_id=parcel.id,
            usage_state=payload.usage_state,
            assigned_by_agent_id=None,
        )
    )
    session.flush()
    session.refresh(parcel)
    return _to_parcel_read(session, parcel)


@app.post("/parcels/{parcel_id}/usage", response_model=ParcelRead)
def update_parcel_usage(
    parcel_id: int,
    payload: ParcelUsageUpdateRequest,
    session: Session = Depends(get_session),
) -> ParcelRead:
    parcel = set_parcel_usage_state(session, parcel_id, payload)
    return _to_parcel_read(session, parcel)


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
        open_ids = set(session.scalars(select(Listing.parcel_id).where(Listing.status == ListingStatus.open)).all())
        parcels = [parcel for parcel in parcels if parcel.id in open_ids]
    return [_to_parcel_read(session, parcel) for parcel in parcels]


@app.post("/listings", response_model=ListingRead, status_code=201)
def create_property_listing(payload: ListingCreate, session: Session = Depends(get_session)) -> ListingRead:
    listing = create_listing(session, payload)
    return ListingRead.model_validate(listing)


@app.get("/listings", response_model=list[ListingRead])
def list_listings(
    status: ListingStatus = ListingStatus.open,
    session: Session = Depends(get_session),
) -> list[ListingRead]:
    listings = session.scalars(select(Listing).where(Listing.status == status).order_by(Listing.created_at.desc())).all()
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
    txs = session.scalars(select(Transaction).order_by(Transaction.settled_at.desc()).limit(safe_limit)).all()
    return [TransactionRead.model_validate(tx) for tx in txs]


@app.post("/institutions", response_model=InstitutionRead, status_code=201)
def create_institution_endpoint(payload: InstitutionCreate, session: Session = Depends(get_session)) -> InstitutionRead:
    institution = create_institution(session, payload)
    return InstitutionRead.model_validate(institution)


@app.get("/institutions", response_model=list[InstitutionRead])
def list_institutions(session: Session = Depends(get_session)) -> list[InstitutionRead]:
    institutions = session.scalars(select(Institution).order_by(Institution.created_at.desc())).all()
    return [InstitutionRead.model_validate(item) for item in institutions]


@app.post("/jobs", response_model=JobRead, status_code=201)
def create_job_endpoint(payload: JobCreate, session: Session = Depends(get_session)) -> JobRead:
    job = create_job(session, payload)
    return JobRead.model_validate(job)


@app.get("/jobs", response_model=list[JobRead])
def list_jobs(
    institution_id: int | None = None,
    status: JobStatus | None = None,
    session: Session = Depends(get_session),
) -> list[JobRead]:
    query = select(JobRole)
    if institution_id is not None:
        query = query.where(JobRole.institution_id == institution_id)
    if status is not None:
        query = query.where(JobRole.status == status)
    jobs = session.scalars(query.order_by(JobRole.created_at.desc())).all()
    return [JobRead.model_validate(item) for item in jobs]


@app.post("/employment/assign", response_model=EmploymentRead, status_code=201)
def assign_employment_endpoint(
    payload: EmploymentAssignRequest,
    session: Session = Depends(get_session),
) -> EmploymentRead:
    employment = assign_employment(session, payload)
    return EmploymentRead.model_validate(employment)


@app.get("/employment", response_model=list[EmploymentRead])
def list_employment(
    active_only: bool = False,
    session: Session = Depends(get_session),
) -> list[EmploymentRead]:
    query = select(Employment).order_by(Employment.started_at.desc())
    if active_only:
        query = query.where(Employment.status == EmploymentStatus.active)
    employments = session.scalars(query).all()
    return [EmploymentRead.model_validate(item) for item in employments]


@app.post("/simulation/tick", response_model=SimulationCycleRead, status_code=201)
def run_simulation_tick_endpoint(
    payload: SimulationTickRequest,
    session: Session = Depends(get_session),
) -> SimulationCycleRead:
    cycle = run_simulation_tick(session, payload)
    return SimulationCycleRead.model_validate(cycle)


@app.get("/simulation/cycles", response_model=list[SimulationCycleRead])
def list_simulation_cycles(limit: int = 100, session: Session = Depends(get_session)) -> list[SimulationCycleRead]:
    safe_limit = min(max(limit, 1), 500)
    cycles = session.scalars(select(SimulationCycle).order_by(SimulationCycle.created_at.desc()).limit(safe_limit)).all()
    return [SimulationCycleRead.model_validate(item) for item in cycles]


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
    entries = session.scalars(select(TreasuryEntry).order_by(TreasuryEntry.created_at.desc()).limit(safe_limit)).all()
    return [TreasuryEntryRead.model_validate(entry) for entry in entries]


@app.post("/governance/contracts", response_model=GovernmentContractRead, status_code=201)
def publish_contract(payload: ContractCreate, session: Session = Depends(get_session)) -> GovernmentContractRead:
    contract = create_contract(session, payload)
    return GovernmentContractRead.model_validate(contract)


@app.get("/governance/contracts", response_model=list[GovernmentContractRead])
def list_contracts(session: Session = Depends(get_session)) -> list[GovernmentContractRead]:
    contracts = session.scalars(select(GovernmentContract).order_by(GovernmentContract.created_at.desc())).all()
    return [GovernmentContractRead.model_validate(contract) for contract in contracts]


@app.post("/governance/contracts/{contract_id}/award", response_model=GovernmentContractRead)
def assign_contract(
    contract_id: int,
    payload: ContractAwardRequest,
    session: Session = Depends(get_session),
) -> GovernmentContractRead:
    contract = award_contract(session, contract_id, payload)
    return GovernmentContractRead.model_validate(contract)


@app.get("/audit/events", response_model=list[GovernanceAuditRead])
def list_audits(
    action_type: AuditActionType | None = None,
    limit: int = 200,
    session: Session = Depends(get_session),
) -> list[GovernanceAuditRead]:
    action_types = {action_type} if action_type else None
    events = list_audit_events(session, action_types=action_types, limit=limit)
    return [GovernanceAuditRead.model_validate(event) for event in events]


@app.get("/audit/citizenship", response_model=list[GovernanceAuditRead])
def list_citizenship_audits(limit: int = 200, session: Session = Depends(get_session)) -> list[GovernanceAuditRead]:
    events = list_audit_events(session, action_types={AuditActionType.citizenship_grant}, limit=limit)
    return [GovernanceAuditRead.model_validate(event) for event in events]


@app.get("/audit/contracts", response_model=list[GovernanceAuditRead])
def list_contract_audits(limit: int = 200, session: Session = Depends(get_session)) -> list[GovernanceAuditRead]:
    events = list_audit_events(
        session,
        action_types={AuditActionType.contract_created, AuditActionType.contract_awarded},
        limit=limit,
    )
    return [GovernanceAuditRead.model_validate(event) for event in events]


@app.get("/audit/treasury", response_model=list[GovernanceAuditRead])
def list_treasury_audits(limit: int = 200, session: Session = Depends(get_session)) -> list[GovernanceAuditRead]:
    events = list_audit_events(
        session,
        action_types={
            AuditActionType.tax_policy_created,
            AuditActionType.taxes_collected,
            AuditActionType.treasury_disbursement,
        },
        limit=limit,
    )
    return [GovernanceAuditRead.model_validate(event) for event in events]


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
