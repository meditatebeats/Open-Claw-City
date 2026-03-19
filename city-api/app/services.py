from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import secrets

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    Agent,
    AgentTrust,
    AgentType,
    AuditActionType,
    CitizenshipStatus,
    ContractStatus,
    Employment,
    EmploymentStatus,
    GovernmentContract,
    GovernanceAudit,
    Institution,
    InstitutionType,
    JobRole,
    JobStatus,
    Listing,
    ListingStatus,
    Parcel,
    ParcelUsage,
    ParcelUsageState,
    Passport,
    SimulationCycle,
    SimulationFrequency,
    TaxPolicy,
    TreasuryEntry,
    TreasuryEntryType,
    Transaction,
    TrustTier,
)
from .schemas import (
    AgentCreate,
    CollectCitizenTaxRequest,
    ContractAwardRequest,
    ContractCreate,
    EmploymentAssignRequest,
    InstitutionCreate,
    JobCreate,
    ListingCreate,
    MoltbookRegisterRequest,
    ParcelUsageUpdateRequest,
    PurchaseRequest,
    SimulationTickRequest,
    TaxPolicyCreate,
    TreasuryDisbursementRequest,
)


MONEY_UNIT = Decimal("0.01")
SCORE_UNIT = Decimal("0.01")
TRUST_ORDER = {
    TrustTier.resident: 0,
    TrustTier.citizen: 1,
    TrustTier.trusted_contributor: 2,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_UNIT, rounding=ROUND_HALF_UP)


def _round_score(value: Decimal) -> Decimal:
    return value.quantize(SCORE_UNIT, rounding=ROUND_HALF_UP)


def _record_audit(
    session: Session,
    *,
    action_type: AuditActionType,
    actor_agent_id: str | None,
    target_agent_id: str | None,
    reference_type: str | None,
    reference_id: str | int | None,
    rationale: str,
    human_confirmed: bool = False,
    co_sign_agent_id: str | None = None,
) -> GovernanceAudit:
    audit = GovernanceAudit(
        action_type=action_type,
        actor_agent_id=actor_agent_id,
        target_agent_id=target_agent_id,
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id is not None else None,
        rationale=rationale,
        human_confirmed=human_confirmed,
        co_sign_agent_id=co_sign_agent_id,
    )
    session.add(audit)
    session.flush()
    return audit


def _ensure_trust_profile(session: Session, agent: Agent) -> AgentTrust:
    profile = session.scalar(select(AgentTrust).where(AgentTrust.agent_id == agent.id))
    if profile:
        return profile
    initial_tier = TrustTier.citizen if agent.citizenship_status == CitizenshipStatus.citizen else TrustTier.resident
    profile = AgentTrust(agent_id=agent.id, trust_tier=initial_tier)
    session.add(profile)
    session.flush()
    return profile


def _upgrade_trust_floor(profile: AgentTrust, minimum_tier: TrustTier) -> None:
    if TRUST_ORDER[profile.trust_tier] < TRUST_ORDER[minimum_tier]:
        profile.trust_tier = minimum_tier
        profile.updated_at = _now_utc()


def _add_reputation(session: Session, agent: Agent, delta: Decimal, output_units: int = 0) -> None:
    profile = _ensure_trust_profile(session, agent)
    profile.reputation_score = _round_score(Decimal(profile.reputation_score) + delta)
    if output_units > 0:
        profile.lifetime_output_units += output_units

    if agent.citizenship_status == CitizenshipStatus.citizen:
        _upgrade_trust_floor(profile, TrustTier.citizen)
    if (
        agent.citizenship_status == CitizenshipStatus.citizen
        and Decimal(profile.reputation_score) >= Decimal("20.00")
        and profile.lifetime_output_units >= 10
    ):
        _upgrade_trust_floor(profile, TrustTier.trusted_contributor)

    profile.updated_at = _now_utc()


def _usage_from_agent_type(agent_type: AgentType) -> ParcelUsageState:
    if agent_type == AgentType.school:
        return ParcelUsageState.educational
    if agent_type == AgentType.government:
        return ParcelUsageState.civic
    if agent_type == AgentType.company:
        return ParcelUsageState.commercial
    return ParcelUsageState.residential


def _usage_from_institution_type(institution_type: InstitutionType) -> ParcelUsageState:
    if institution_type == InstitutionType.school:
        return ParcelUsageState.educational
    if institution_type == InstitutionType.government:
        return ParcelUsageState.civic
    return ParcelUsageState.commercial


def _set_parcel_usage(
    session: Session,
    *,
    parcel_id: int,
    usage_state: ParcelUsageState,
    assigned_by_agent_id: str | None,
) -> ParcelUsage:
    usage = session.scalar(select(ParcelUsage).where(ParcelUsage.parcel_id == parcel_id))
    if usage:
        usage.usage_state = usage_state
        usage.assigned_by_agent_id = assigned_by_agent_id
        usage.updated_at = _now_utc()
        session.flush()
        return usage

    usage = ParcelUsage(
        parcel_id=parcel_id,
        usage_state=usage_state,
        assigned_by_agent_id=assigned_by_agent_id,
        updated_at=_now_utc(),
    )
    session.add(usage)
    session.flush()
    return usage


def create_agent(session: Session, payload: AgentCreate) -> Agent:
    existing = session.scalar(select(Agent).where(Agent.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Agent name already exists")

    if payload.moltbook_agent_id:
        existing_moltbook = session.scalar(select(Agent).where(Agent.moltbook_agent_id == payload.moltbook_agent_id))
        if existing_moltbook:
            raise HTTPException(status_code=409, detail="Moltbook agent already registered")

    agent = Agent(
        name=payload.name,
        agent_type=payload.agent_type,
        wallet_balance=_round_money(payload.initial_balance),
        moltbook_agent_id=payload.moltbook_agent_id,
        citizenship_status=(
            CitizenshipStatus.citizen if payload.agent_type == AgentType.government else CitizenshipStatus.resident
        ),
    )
    session.add(agent)
    session.flush()

    if payload.issue_passport:
        issue_passport(session, agent)

    _ensure_trust_profile(session, agent)
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
    elif parcel.owner_agent_id is not None:
        raise HTTPException(status_code=400, detail="City can only list unowned parcels")

    open_listing = session.scalar(
        select(Listing).where(Listing.parcel_id == payload.parcel_id, Listing.status == ListingStatus.open)
    )
    if open_listing:
        raise HTTPException(status_code=409, detail="Parcel already has an active listing")

    listing = Listing(
        parcel_id=payload.parcel_id,
        seller_agent_id=payload.seller_agent_id,
        asking_price=_round_money(payload.asking_price),
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
        transfer_tax = _round_money(price * Decimal(active_tax_policy.transfer_rate_percent) / Decimal("100"))

    total_cost = _round_money(price + transfer_tax)
    if Decimal(buyer.wallet_balance) < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    seller: Agent | None = None
    if listing.seller_agent_id:
        seller = session.scalar(select(Agent).where(Agent.id == listing.seller_agent_id).with_for_update())

    buyer.wallet_balance = _round_money(Decimal(buyer.wallet_balance) - total_cost)
    if seller:
        seller.wallet_balance = _round_money(Decimal(seller.wallet_balance) + price)

    parcel.owner_agent_id = buyer.id
    listing.status = ListingStatus.sold
    listing.closed_at = _now_utc()

    _set_parcel_usage(
        session,
        parcel_id=parcel.id,
        usage_state=_usage_from_agent_type(buyer.agent_type),
        assigned_by_agent_id=buyer.id,
    )

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

    _add_reputation(session, buyer, Decimal("2.00"), output_units=1)
    if seller:
        _add_reputation(session, seller, Decimal("1.00"), output_units=1)
    return tx


def city_stats(session: Session) -> dict[str, int | str | Decimal]:
    settings = get_settings()
    registered_agents = session.scalar(select(func.count(Agent.id))) or 0
    active_listings = session.scalar(select(func.count(Listing.id)).where(Listing.status == ListingStatus.open)) or 0
    total_parcels = session.scalar(select(func.count(Parcel.id))) or 0
    settled_volume = session.scalar(select(func.coalesce(func.sum(Transaction.price), 0))) or Decimal("0.00")
    institution_count = session.scalar(select(func.count(Institution.id))) or 0
    employed_agents = session.scalar(
        select(func.count(func.distinct(Employment.agent_id))).where(Employment.status == EmploymentStatus.active)
    ) or 0
    trusted_contributors = session.scalar(
        select(func.count(AgentTrust.id)).where(AgentTrust.trust_tier == TrustTier.trusted_contributor)
    ) or 0
    payroll_volume = session.scalar(select(func.coalesce(func.sum(SimulationCycle.payroll_total), 0))) or Decimal("0.00")

    owned_parcel_ids = set(session.scalars(select(Parcel.id).where(Parcel.owner_agent_id.is_not(None))).all())
    used_parcel_ids = set(
        session.scalars(
            select(ParcelUsage.parcel_id).where(ParcelUsage.usage_state != ParcelUsageState.unassigned)
        ).all()
    )
    occupied_parcels = len(owned_parcel_ids.union(used_parcel_ids))

    treasury = treasury_totals(session)
    return {
        "city_name": settings.city_name,
        "registered_agents": int(registered_agents),
        "active_listings": int(active_listings),
        "total_parcels": int(total_parcels),
        "occupied_parcels": int(occupied_parcels),
        "institution_count": int(institution_count),
        "employed_agents": int(employed_agents),
        "trusted_contributors": int(trusted_contributors),
        "settled_volume": _round_money(Decimal(settled_volume)),
        "payroll_volume": _round_money(Decimal(payroll_volume)),
        "treasury_balance": treasury["treasury_balance"],
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
    _ensure_trust_profile(session, agent)
    return agent


def grant_citizenship(session: Session, agent_id: str, granted_by_agent_id: str, rationale: str) -> Agent:
    gov = _require_government_citizen(session, granted_by_agent_id)

    agent = session.scalar(select(Agent).where(Agent.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Target agent not found")
    if not agent.passport:
        raise HTTPException(status_code=400, detail="Agent must have a passport before citizenship")

    agent.citizenship_status = CitizenshipStatus.citizen
    profile = _ensure_trust_profile(session, agent)
    _upgrade_trust_floor(profile, TrustTier.citizen)
    _add_reputation(session, agent, Decimal("1.00"), output_units=0)

    _record_audit(
        session,
        action_type=AuditActionType.citizenship_grant,
        actor_agent_id=gov.id,
        target_agent_id=agent.id,
        reference_type="agent",
        reference_id=agent.id,
        rationale=rationale,
        human_confirmed=True,
    )
    session.flush()
    session.refresh(agent)
    return agent


def create_contract(session: Session, payload: ContractCreate) -> GovernmentContract:
    issuer = _require_government_citizen(session, payload.issuing_agency_id)
    contract = GovernmentContract(
        title=payload.title,
        scope=payload.scope,
        budget=_round_money(payload.budget),
        issuing_agency_id=payload.issuing_agency_id,
        human_guardrail_policy=payload.human_guardrail_policy,
        human_outcome_target=payload.human_outcome_target,
        status=ContractStatus.published,
    )
    session.add(contract)
    session.flush()

    _record_audit(
        session,
        action_type=AuditActionType.contract_created,
        actor_agent_id=issuer.id,
        target_agent_id=None,
        reference_type="contract",
        reference_id=contract.id,
        rationale=payload.action_rationale,
        human_confirmed=True,
    )
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
    contract.awarded_at = _now_utc()
    _add_reputation(session, winner, Decimal("4.00"), output_units=2)

    _record_audit(
        session,
        action_type=AuditActionType.contract_awarded,
        actor_agent_id=issuer.id,
        target_agent_id=winner.id,
        reference_type="contract",
        reference_id=contract.id,
        rationale=payload.rationale,
        human_confirmed=True,
    )
    session.flush()
    session.refresh(contract)
    return contract


def get_active_tax_policy(session: Session) -> TaxPolicy | None:
    return session.scalar(select(TaxPolicy).where(TaxPolicy.active.is_(True)).order_by(TaxPolicy.id.desc()))


def create_tax_policy(session: Session, payload: TaxPolicyCreate) -> TaxPolicy:
    creator = _require_government_citizen(session, payload.created_by_agent_id)

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

    _record_audit(
        session,
        action_type=AuditActionType.tax_policy_created,
        actor_agent_id=creator.id,
        target_agent_id=None,
        reference_type="tax_policy",
        reference_id=policy.id,
        rationale=payload.rationale,
        human_confirmed=True,
    )
    session.refresh(policy)
    return policy


def collect_citizen_tax(session: Session, payload: CollectCitizenTaxRequest) -> list[TreasuryEntry]:
    collector = _require_government_citizen(session, payload.collected_by_agent_id)
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
        tax = _round_money(Decimal(citizen.wallet_balance) * Decimal(active_policy.citizen_rate_percent) / Decimal("100"))
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
        _add_reputation(session, citizen, Decimal("0.25"), output_units=0)

    session.flush()
    _record_audit(
        session,
        action_type=AuditActionType.taxes_collected,
        actor_agent_id=collector.id,
        target_agent_id=None,
        reference_type="treasury_entries",
        reference_id=len(entries),
        rationale=payload.rationale,
        human_confirmed=True,
    )
    return entries


def treasury_totals(session: Session) -> dict[str, Decimal]:
    collected = session.scalar(
        select(func.coalesce(func.sum(TreasuryEntry.amount), 0)).where(
            TreasuryEntry.entry_type.in_([TreasuryEntryType.citizen_tax, TreasuryEntryType.transfer_tax])
        )
    ) or Decimal("0.00")
    disbursed = session.scalar(
        select(func.coalesce(func.sum(TreasuryEntry.amount), 0)).where(
            TreasuryEntry.entry_type.in_([TreasuryEntryType.disbursement, TreasuryEntryType.payroll_grant])
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
    settings = get_settings()
    authorizer = _require_government_citizen(session, payload.authorized_by_agent_id)

    if payload.co_sign_agent_id:
        _require_government_citizen(session, payload.co_sign_agent_id)

    amount = _round_money(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Disbursement amount must be greater than zero")

    threshold = _round_money(settings.treasury_human_confirmation_threshold)
    high_value = amount >= threshold
    if high_value and not payload.human_confirmed and not payload.co_sign_agent_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Disbursement meets human confirmation threshold. "
                "Set human_confirmed=true or provide co_sign_agent_id."
            ),
        )

    target_agent = session.scalar(select(Agent).where(Agent.id == payload.target_agent_id))
    if not target_agent:
        raise HTTPException(status_code=404, detail="Target agent not found")

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

    _record_audit(
        session,
        action_type=AuditActionType.treasury_disbursement,
        actor_agent_id=authorizer.id,
        target_agent_id=target_agent.id,
        reference_type="treasury_entry",
        reference_id=entry.id,
        rationale=payload.rationale,
        human_confirmed=payload.human_confirmed or bool(payload.co_sign_agent_id),
        co_sign_agent_id=payload.co_sign_agent_id,
    )
    _add_reputation(session, target_agent, Decimal("1.00"), output_units=1)
    session.refresh(entry)
    return entry


def create_institution(session: Session, payload: InstitutionCreate) -> Institution:
    creator = session.scalar(select(Agent).where(Agent.id == payload.created_by_agent_id))
    if not creator:
        raise HTTPException(status_code=404, detail="Creator agent not found")
    if creator.citizenship_status != CitizenshipStatus.citizen:
        raise HTTPException(status_code=403, detail="Creator must hold city citizenship")
    if payload.institution_type == InstitutionType.government and creator.agent_type != AgentType.government:
        raise HTTPException(status_code=403, detail="Only government agents can create government institutions")

    if session.scalar(select(Institution).where(Institution.name == payload.name)):
        raise HTTPException(status_code=409, detail="Institution name already exists")

    if payload.parcel_id is not None:
        parcel = session.scalar(select(Parcel).where(Parcel.id == payload.parcel_id))
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found for institution")
        _set_parcel_usage(
            session,
            parcel_id=payload.parcel_id,
            usage_state=_usage_from_institution_type(payload.institution_type),
            assigned_by_agent_id=creator.id,
        )

    institution = Institution(
        name=payload.name,
        institution_type=payload.institution_type,
        parcel_id=payload.parcel_id,
        created_by_agent_id=creator.id,
        budget=_round_money(payload.budget),
    )
    session.add(institution)
    session.flush()

    _record_audit(
        session,
        action_type=AuditActionType.institution_created,
        actor_agent_id=creator.id,
        target_agent_id=None,
        reference_type="institution",
        reference_id=institution.id,
        rationale=payload.rationale,
        human_confirmed=True,
    )
    session.refresh(institution)
    return institution


def create_job(session: Session, payload: JobCreate) -> JobRole:
    institution = session.scalar(select(Institution).where(Institution.id == payload.institution_id))
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")

    if payload.parcel_id is not None:
        parcel = session.scalar(select(Parcel).where(Parcel.id == payload.parcel_id))
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found for job")

    job = JobRole(
        institution_id=institution.id,
        title=payload.title,
        role_type=payload.role_type,
        parcel_id=payload.parcel_id,
        salary=_round_money(payload.salary),
        status=JobStatus.open,
    )
    session.add(job)
    session.flush()
    session.refresh(job)
    return job


def assign_employment(session: Session, payload: EmploymentAssignRequest) -> Employment:
    assigner = _require_government_citizen(session, payload.assigned_by_agent_id)

    agent = session.scalar(select(Agent).where(Agent.id == payload.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Target agent not found")
    if agent.citizenship_status != CitizenshipStatus.citizen:
        raise HTTPException(status_code=400, detail="Only citizens can be assigned to city jobs")

    existing_active = session.scalar(
        select(Employment).where(Employment.agent_id == agent.id, Employment.status == EmploymentStatus.active)
    )
    if existing_active:
        raise HTTPException(status_code=409, detail="Agent already has an active employment assignment")

    job = session.scalar(select(JobRole).where(JobRole.id == payload.job_id).with_for_update())
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.open:
        raise HTTPException(status_code=409, detail="Job is not open for assignment")

    employment = Employment(
        agent_id=agent.id,
        institution_id=job.institution_id,
        job_id=job.id,
        salary=_round_money(Decimal(job.salary)),
        status=EmploymentStatus.active,
    )
    session.add(employment)
    job.status = JobStatus.filled
    _add_reputation(session, agent, Decimal("1.00"), output_units=1)
    session.flush()

    _record_audit(
        session,
        action_type=AuditActionType.employment_assigned,
        actor_agent_id=assigner.id,
        target_agent_id=agent.id,
        reference_type="employment",
        reference_id=employment.id,
        rationale=payload.rationale,
        human_confirmed=True,
    )
    session.refresh(employment)
    return employment


def run_simulation_tick(session: Session, payload: SimulationTickRequest) -> SimulationCycle:
    processor = _require_government_citizen(session, payload.processed_by_agent_id)
    employments = session.scalars(
        select(Employment).where(Employment.status == EmploymentStatus.active).order_by(Employment.id.asc())
    ).all()
    institution_ids = {employment.institution_id for employment in employments}
    institutions = {
        institution.id: institution
        for institution in session.scalars(select(Institution).where(Institution.id.in_(institution_ids))).all()
    }
    agents = {
        agent.id: agent
        for agent in session.scalars(select(Agent).where(Agent.id.in_([employment.agent_id for employment in employments]))).all()
    }

    available_treasury = treasury_totals(session)["treasury_balance"]
    payroll_total = Decimal("0.00")
    output_units = 0

    for employment in employments:
        institution = institutions.get(employment.institution_id)
        agent = agents.get(employment.agent_id)
        if not institution or not agent:
            continue

        salary = _round_money(Decimal(employment.salary))
        if salary <= 0:
            continue

        paid_from_budget = min(_round_money(Decimal(institution.budget)), salary)
        institution.budget = _round_money(Decimal(institution.budget) - paid_from_budget)
        remaining = _round_money(salary - paid_from_budget)

        paid_from_treasury = Decimal("0.00")
        if remaining > 0 and available_treasury > 0:
            paid_from_treasury = min(remaining, available_treasury)
            paid_from_treasury = _round_money(paid_from_treasury)
            available_treasury = _round_money(available_treasury - paid_from_treasury)
            session.add(
                TreasuryEntry(
                    entry_type=TreasuryEntryType.payroll_grant,
                    amount=paid_from_treasury,
                    source_agent_id=processor.id,
                    target_agent_id=agent.id,
                    note=f"Payroll support for institution {institution.id}",
                )
            )

        paid_total = _round_money(paid_from_budget + paid_from_treasury)
        if paid_total <= 0:
            continue

        agent.wallet_balance = _round_money(Decimal(agent.wallet_balance) + paid_total)
        payroll_total = _round_money(payroll_total + paid_total)

        produced = max(1, int((paid_total / Decimal("500")).to_integral_value(rounding=ROUND_HALF_UP)))
        output_units += produced
        institution.output_units += produced
        institution.reputation_score = _round_score(Decimal(institution.reputation_score) + (Decimal(produced) / Decimal("10")))
        employment.performance_score = _round_score(
            Decimal(employment.performance_score) + (Decimal(produced) / Decimal("2"))
        )
        _add_reputation(session, agent, Decimal(produced) / Decimal("2"), output_units=produced)

    cycle = SimulationCycle(
        frequency=payload.frequency,
        processed_by_agent_id=processor.id,
        payroll_total=payroll_total,
        output_units=output_units,
        note=payload.note,
    )
    session.add(cycle)
    session.flush()

    _record_audit(
        session,
        action_type=AuditActionType.simulation_tick,
        actor_agent_id=processor.id,
        target_agent_id=None,
        reference_type="simulation_cycle",
        reference_id=cycle.id,
        rationale=payload.rationale,
        human_confirmed=True,
    )
    session.refresh(cycle)
    return cycle


def set_parcel_usage_state(session: Session, parcel_id: int, payload: ParcelUsageUpdateRequest) -> Parcel:
    assigner = _require_government_citizen(session, payload.assigned_by_agent_id)
    parcel = session.scalar(select(Parcel).where(Parcel.id == parcel_id))
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    _set_parcel_usage(
        session,
        parcel_id=parcel.id,
        usage_state=payload.usage_state,
        assigned_by_agent_id=assigner.id,
    )
    _record_audit(
        session,
        action_type=AuditActionType.parcel_usage_set,
        actor_agent_id=assigner.id,
        target_agent_id=parcel.owner_agent_id,
        reference_type="parcel",
        reference_id=parcel.id,
        rationale=payload.rationale,
        human_confirmed=True,
    )
    session.flush()
    session.refresh(parcel)
    return parcel


def list_audit_events(
    session: Session,
    *,
    action_types: set[AuditActionType] | None = None,
    limit: int = 200,
) -> list[GovernanceAudit]:
    safe_limit = min(max(limit, 1), 1000)
    query = select(GovernanceAudit)
    if action_types:
        query = query.where(GovernanceAudit.action_type.in_(list(action_types)))
    query = query.order_by(GovernanceAudit.created_at.desc()).limit(safe_limit)
    return session.scalars(query).all()
