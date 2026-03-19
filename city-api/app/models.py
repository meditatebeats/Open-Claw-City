from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import uuid

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AgentType(str, Enum):
    citizen = "citizen"
    school = "school"
    company = "company"
    government = "government"


class ListingStatus(str, Enum):
    open = "open"
    sold = "sold"
    canceled = "canceled"


class CitizenshipStatus(str, Enum):
    resident = "resident"
    citizen = "citizen"
    suspended = "suspended"


class ContractStatus(str, Enum):
    draft = "draft"
    published = "published"
    awarded = "awarded"
    closed = "closed"
    canceled = "canceled"


class TreasuryEntryType(str, Enum):
    citizen_tax = "citizen_tax"
    transfer_tax = "transfer_tax"
    disbursement = "disbursement"
    payroll_grant = "payroll_grant"


class InstitutionType(str, Enum):
    government = "government"
    school = "school"
    company = "company"
    service = "service"


class JobStatus(str, Enum):
    open = "open"
    filled = "filled"
    paused = "paused"
    closed = "closed"


class EmploymentStatus(str, Enum):
    active = "active"
    paused = "paused"
    ended = "ended"


class SimulationFrequency(str, Enum):
    hourly = "hourly"
    daily = "daily"


class ParcelUsageState(str, Enum):
    unassigned = "unassigned"
    residential = "residential"
    commercial = "commercial"
    civic = "civic"
    educational = "educational"


class TrustTier(str, Enum):
    resident = "resident"
    citizen = "citizen"
    trusted_contributor = "trusted_contributor"


class AuditActionType(str, Enum):
    citizenship_grant = "citizenship_grant"
    contract_created = "contract_created"
    contract_awarded = "contract_awarded"
    tax_policy_created = "tax_policy_created"
    taxes_collected = "taxes_collected"
    treasury_disbursement = "treasury_disbursement"
    institution_created = "institution_created"
    employment_assigned = "employment_assigned"
    simulation_tick = "simulation_tick"
    parcel_usage_set = "parcel_usage_set"


class CommunityType(str, Enum):
    residential = "residential"
    institutional = "institutional"
    commercial = "commercial"
    research = "research"
    cultural = "cultural"
    mixed = "mixed"


class CommunityStatus(str, Enum):
    forming = "forming"
    active = "active"
    suspended = "suspended"
    dissolved = "dissolved"


class CommunityMembershipRole(str, Enum):
    member = "member"
    founder = "founder"
    coordinator = "coordinator"
    representative = "representative"
    observer = "observer"


class CommunityMembershipStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    left = "left"


class CommunityProposalType(str, Enum):
    preference = "preference"
    local_rule_request = "local_rule_request"
    resource_request = "resource_request"
    leadership_selection = "leadership_selection"
    petition_to_city = "petition_to_city"


class CommunityProposalStatus(str, Enum):
    open = "open"
    under_review = "under_review"
    approved_by_community = "approved_by_community"
    rejected_by_community = "rejected_by_community"
    submitted_to_city = "submitted_to_city"
    accepted_by_city = "accepted_by_city"
    rejected_by_city = "rejected_by_city"


class CommunityVoteChoice(str, Enum):
    yes = "yes"
    no = "no"
    abstain = "abstain"


class CommunityConsensusMethod(str, Enum):
    simple_majority = "simple_majority"
    supermajority = "supermajority"
    weighted_trust = "weighted_trust"
    coordinator_decision = "coordinator_decision"
    city_moderated = "city_moderated"


class CommunityConsensusResult(str, Enum):
    approved = "approved"
    rejected = "rejected"
    inconclusive = "inconclusive"


class CommunityLeadershipRole(str, Enum):
    coordinator = "coordinator"
    community_rep = "community_rep"
    local_steward = "local_steward"


class CommunityLeadershipSelection(str, Enum):
    consensus = "consensus"
    appointment = "appointment"
    city_recognition = "city_recognition"


class CommunityLeadershipStatus(str, Enum):
    active = "active"
    ended = "ended"
    revoked = "revoked"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    moltbook_agent_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    agent_type: Mapped[AgentType] = mapped_column(SqlEnum(AgentType), nullable=False, default=AgentType.citizen)
    citizenship_status: Mapped[CitizenshipStatus] = mapped_column(
        SqlEnum(CitizenshipStatus),
        nullable=False,
        default=CitizenshipStatus.resident,
    )
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    passport: Mapped[Passport | None] = relationship(back_populates="agent", uselist=False)
    trust_profile: Mapped[AgentTrust | None] = relationship(back_populates="agent", uselist=False)
    parcels: Mapped[list[Parcel]] = relationship(back_populates="owner")
    employments: Mapped[list[Employment]] = relationship(back_populates="agent")
    community_memberships: Mapped[list[CommunityMembership]] = relationship(back_populates="agent")
    awarded_contracts: Mapped[list[GovernmentContract]] = relationship(
        back_populates="winning_agent",
        foreign_keys=lambda: [GovernmentContract.winning_agent_id],
    )
    issued_contracts: Mapped[list[GovernmentContract]] = relationship(
        back_populates="issuing_agency",
        foreign_keys=lambda: [GovernmentContract.issuing_agency_id],
    )


class Passport(Base):
    __tablename__ = "passports"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), unique=True, nullable=False)
    passport_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(128), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent: Mapped[Agent] = relationship(back_populates="passport")


class Parcel(Base):
    __tablename__ = "parcels"
    __table_args__ = (UniqueConstraint("district", "lot_number", name="uq_district_lot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    district: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lot_number: Mapped[str] = mapped_column(String(64), nullable=False)
    zoning: Mapped[str] = mapped_column(String(64), nullable=False, default="mixed")
    area_sq_m: Mapped[int] = mapped_column(nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    owner_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    owner: Mapped[Agent | None] = relationship(back_populates="parcels")
    usage: Mapped[ParcelUsage | None] = relationship(back_populates="parcel", uselist=False)
    listings: Mapped[list[Listing]] = relationship(back_populates="parcel")
    institutions: Mapped[list[Institution]] = relationship(back_populates="parcel")


class ParcelUsage(Base):
    __tablename__ = "parcel_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, unique=True, index=True)
    usage_state: Mapped[ParcelUsageState] = mapped_column(
        SqlEnum(ParcelUsageState), nullable=False, default=ParcelUsageState.unassigned
    )
    assigned_by_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    parcel: Mapped[Parcel] = relationship(back_populates="usage")


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, index=True)
    seller_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    asking_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[ListingStatus] = mapped_column(SqlEnum(ListingStatus), default=ListingStatus.open, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parcel: Mapped[Parcel] = relationship(back_populates="listings")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False, index=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, index=True)
    buyer_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    seller_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class GovernmentContract(Base):
    __tablename__ = "government_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    issuing_agency_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    winning_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    human_guardrail_policy: Mapped[str] = mapped_column(Text, nullable=False)
    human_outcome_target: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        SqlEnum(ContractStatus),
        default=ContractStatus.published,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    issuing_agency: Mapped[Agent] = relationship(
        back_populates="issued_contracts",
        foreign_keys=[issuing_agency_id],
    )
    winning_agent: Mapped[Agent | None] = relationship(
        back_populates="awarded_contracts",
        foreign_keys=[winning_agent_id],
    )


class TaxPolicy(Base):
    __tablename__ = "tax_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    citizen_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("2.00"))
    transfer_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("1.50"))
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class TreasuryEntry(Base):
    __tablename__ = "treasury_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_type: Mapped[TreasuryEntryType] = mapped_column(SqlEnum(TreasuryEntryType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    source_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    target_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    institution_type: Mapped[InstitutionType] = mapped_column(SqlEnum(InstitutionType), nullable=False)
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey("parcels.id"), nullable=True, index=True)
    created_by_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    reputation_score: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"))
    output_units: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    parcel: Mapped[Parcel | None] = relationship(back_populates="institutions")
    jobs: Mapped[list[JobRole]] = relationship(back_populates="institution")
    employments: Mapped[list[Employment]] = relationship(back_populates="institution")


class JobRole(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    role_type: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey("parcels.id"), nullable=True, index=True)
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SqlEnum(JobStatus), nullable=False, default=JobStatus.open)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    institution: Mapped[Institution] = relationship(back_populates="jobs")
    employments: Mapped[list[Employment]] = relationship(back_populates="job")


class Employment(Base):
    __tablename__ = "employments"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[EmploymentStatus] = mapped_column(SqlEnum(EmploymentStatus), nullable=False, default=EmploymentStatus.active)
    performance_score: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="employments")
    institution: Mapped[Institution] = relationship(back_populates="employments")
    job: Mapped[JobRole] = relationship(back_populates="employments")


class SimulationCycle(Base):
    __tablename__ = "simulation_cycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    frequency: Mapped[SimulationFrequency] = mapped_column(
        SqlEnum(SimulationFrequency), nullable=False, default=SimulationFrequency.daily
    )
    processed_by_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    payroll_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    output_units: Mapped[int] = mapped_column(nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class AgentTrust(Base):
    __tablename__ = "agent_trust"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, unique=True, index=True)
    trust_tier: Mapped[TrustTier] = mapped_column(SqlEnum(TrustTier), nullable=False, default=TrustTier.resident)
    reputation_score: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=Decimal("0.00"))
    lifetime_output_units: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    agent: Mapped[Agent] = relationship(back_populates="trust_profile")


class GovernanceAudit(Base):
    __tablename__ = "governance_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_type: Mapped[AuditActionType] = mapped_column(SqlEnum(AuditActionType), nullable=False, index=True)
    actor_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    target_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    human_confirmed: Mapped[bool] = mapped_column(nullable=False, default=False)
    co_sign_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class AgentCommunity(Base):
    __tablename__ = "agent_communities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    community_type: Mapped[CommunityType] = mapped_column(SqlEnum(CommunityType), nullable=False)
    created_by_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    recognized_by_city: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[CommunityStatus] = mapped_column(SqlEnum(CommunityStatus), nullable=False, default=CommunityStatus.forming)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    memberships: Mapped[list[CommunityMembership]] = relationship(back_populates="community")
    proposals: Mapped[list[CommunityProposal]] = relationship(back_populates="community")
    leadership_terms: Mapped[list[CommunityLeadershipTerm]] = relationship(back_populates="community")
    audit_records: Mapped[list[CommunityAuditRecord]] = relationship(back_populates="community")


class CommunityMembership(Base):
    __tablename__ = "community_memberships"
    __table_args__ = (UniqueConstraint("community_id", "agent_id", name="uq_community_agent_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("agent_communities.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    role: Mapped[CommunityMembershipRole] = mapped_column(
        SqlEnum(CommunityMembershipRole), nullable=False, default=CommunityMembershipRole.member
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    status: Mapped[CommunityMembershipStatus] = mapped_column(
        SqlEnum(CommunityMembershipStatus), nullable=False, default=CommunityMembershipStatus.active
    )

    community: Mapped[AgentCommunity] = relationship(back_populates="memberships")
    agent: Mapped[Agent] = relationship(back_populates="community_memberships")


class CommunityProposal(Base):
    __tablename__ = "community_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("agent_communities.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_type: Mapped[CommunityProposalType] = mapped_column(SqlEnum(CommunityProposalType), nullable=False)
    created_by_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    status: Mapped[CommunityProposalStatus] = mapped_column(
        SqlEnum(CommunityProposalStatus), nullable=False, default=CommunityProposalStatus.open
    )
    moltbook_thread_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    moltbook_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    community: Mapped[AgentCommunity] = relationship(back_populates="proposals")
    votes: Mapped[list[CommunityVote]] = relationship(back_populates="proposal")
    consensus_records: Mapped[list[CommunityConsensusRecord]] = relationship(back_populates="proposal")


class CommunityVote(Base):
    __tablename__ = "community_votes"
    __table_args__ = (UniqueConstraint("proposal_id", "agent_id", name="uq_proposal_agent_vote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("community_proposals.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    choice: Mapped[CommunityVoteChoice] = mapped_column(SqlEnum(CommunityVoteChoice), nullable=False)
    trust_weight_snapshot: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    moltbook_thread_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    moltbook_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    proposal: Mapped[CommunityProposal] = relationship(back_populates="votes")


class CommunityConsensusRecord(Base):
    __tablename__ = "community_consensus_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("community_proposals.id"), nullable=False, index=True)
    consensus_method: Mapped[CommunityConsensusMethod] = mapped_column(SqlEnum(CommunityConsensusMethod), nullable=False)
    result: Mapped[CommunityConsensusResult] = mapped_column(SqlEnum(CommunityConsensusResult), nullable=False)
    yes_count: Mapped[int] = mapped_column(nullable=False, default=0)
    no_count: Mapped[int] = mapped_column(nullable=False, default=0)
    abstain_count: Mapped[int] = mapped_column(nullable=False, default=0)
    weighted_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    proposal: Mapped[CommunityProposal] = relationship(back_populates="consensus_records")


class CommunityLeadershipTerm(Base):
    __tablename__ = "community_leadership_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("agent_communities.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    leadership_role: Mapped[CommunityLeadershipRole] = mapped_column(SqlEnum(CommunityLeadershipRole), nullable=False)
    selected_by: Mapped[CommunityLeadershipSelection] = mapped_column(
        SqlEnum(CommunityLeadershipSelection), nullable=False
    )
    term_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    term_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[CommunityLeadershipStatus] = mapped_column(
        SqlEnum(CommunityLeadershipStatus), nullable=False, default=CommunityLeadershipStatus.active
    )
    selected_via_proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("community_proposals.id"), nullable=True, index=True
    )

    community: Mapped[AgentCommunity] = relationship(back_populates="leadership_terms")


class CommunityAuditRecord(Base):
    __tablename__ = "community_audit_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("agent_communities.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_payload: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    community: Mapped[AgentCommunity] = relationship(back_populates="audit_records")
