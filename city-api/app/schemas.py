from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AgentType,
    AuditActionType,
    CitizenshipStatus,
    ContractStatus,
    EmploymentStatus,
    InstitutionType,
    JobStatus,
    ListingStatus,
    ParcelUsageState,
    SimulationFrequency,
    TreasuryEntryType,
    TrustTier,
)


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    agent_type: AgentType = AgentType.citizen
    moltbook_agent_id: str | None = Field(default=None, min_length=2, max_length=128)
    initial_balance: Decimal = Field(default=Decimal("10000.00"), ge=Decimal("0"))
    issue_passport: bool = True


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    agent_type: AgentType
    moltbook_agent_id: str | None
    citizenship_status: CitizenshipStatus
    wallet_balance: Decimal
    trust_tier: TrustTier
    reputation_score: Decimal
    created_at: datetime
    passport_number: str | None = None


class MoltbookRegisterRequest(BaseModel):
    moltbook_agent_id: str = Field(min_length=2, max_length=128)
    display_name: str = Field(min_length=2, max_length=128)
    agent_type: AgentType = AgentType.citizen
    initial_balance: Decimal = Field(default=Decimal("10000.00"), ge=Decimal("0"))


class ParcelCreate(BaseModel):
    district: str = Field(min_length=1, max_length=128)
    lot_number: str = Field(min_length=1, max_length=64)
    zoning: str = Field(default="mixed", min_length=1, max_length=64)
    area_sq_m: int = Field(ge=10, le=2_000_000)
    base_price: Decimal = Field(ge=Decimal("1"))
    usage_state: ParcelUsageState = ParcelUsageState.unassigned


class ParcelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    district: str
    lot_number: str
    zoning: str
    area_sq_m: int
    base_price: Decimal
    owner_agent_id: str | None
    usage_state: ParcelUsageState


class ParcelUsageUpdateRequest(BaseModel):
    usage_state: ParcelUsageState
    assigned_by_agent_id: str
    rationale: str = Field(min_length=8, max_length=1200)


class ListingCreate(BaseModel):
    parcel_id: int
    seller_agent_id: str | None = None
    asking_price: Decimal = Field(ge=Decimal("1"))


class ListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_id: int
    seller_agent_id: str | None
    asking_price: Decimal
    status: ListingStatus
    created_at: datetime
    closed_at: datetime | None


class PurchaseRequest(BaseModel):
    buyer_agent_id: str
    note: str | None = Field(default=None, max_length=300)


class CitizenshipGrantRequest(BaseModel):
    agent_id: str
    granted_by_agent_id: str
    rationale: str = Field(min_length=8, max_length=1200)


class ContractCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    scope: str = Field(min_length=20, max_length=10_000)
    budget: Decimal = Field(ge=Decimal("1"))
    issuing_agency_id: str
    human_guardrail_policy: str = Field(
        min_length=20,
        description="Explicit policy for how humans are served and protected.",
    )
    human_outcome_target: str = Field(
        min_length=20,
        description="Measurable human benefit target.",
    )
    action_rationale: str = Field(min_length=8, max_length=1200)


class ContractAwardRequest(BaseModel):
    winning_agent_id: str
    awarded_by_agent_id: str
    rationale: str = Field(min_length=8, max_length=1200)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    parcel_id: int
    buyer_agent_id: str
    seller_agent_id: str | None
    price: Decimal
    note: str | None
    settled_at: datetime


class CityStats(BaseModel):
    city_name: str
    registered_agents: int
    active_listings: int
    total_parcels: int
    occupied_parcels: int
    institution_count: int
    employed_agents: int
    trusted_contributors: int
    settled_volume: Decimal
    payroll_volume: Decimal
    treasury_balance: Decimal


class CityManifest(BaseModel):
    city_name: str
    api_version: str
    enrollment_mode: str
    docs_url: str
    openapi_url: str


class GovernmentContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    scope: str
    budget: Decimal
    issuing_agency_id: str
    winning_agent_id: str | None
    human_guardrail_policy: str
    human_outcome_target: str
    status: ContractStatus
    created_at: datetime
    awarded_at: datetime | None


class TaxPolicyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=140)
    citizen_rate_percent: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    transfer_rate_percent: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    created_by_agent_id: str
    rationale: str = Field(min_length=8, max_length=1200)


class TaxPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    citizen_rate_percent: Decimal
    transfer_rate_percent: Decimal
    active: bool
    created_by_agent_id: str
    created_at: datetime


class CollectCitizenTaxRequest(BaseModel):
    collected_by_agent_id: str
    agent_ids: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=300)
    rationale: str = Field(min_length=8, max_length=1200)


class TreasuryDisbursementRequest(BaseModel):
    authorized_by_agent_id: str
    target_agent_id: str
    amount: Decimal = Field(gt=Decimal("0"))
    note: str | None = Field(default=None, max_length=300)
    rationale: str = Field(min_length=8, max_length=1200)
    human_confirmed: bool = False
    co_sign_agent_id: str | None = None


class TreasuryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_type: TreasuryEntryType
    amount: Decimal
    source_agent_id: str | None
    target_agent_id: str | None
    note: str | None
    created_at: datetime


class TreasurySummary(BaseModel):
    treasury_balance: Decimal
    total_collected: Decimal
    total_disbursed: Decimal
    entry_count: int


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=3, max_length=140)
    institution_type: InstitutionType
    parcel_id: int | None = None
    created_by_agent_id: str
    budget: Decimal = Field(ge=Decimal("0"))
    rationale: str = Field(min_length=8, max_length=1200)


class InstitutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    institution_type: InstitutionType
    parcel_id: int | None
    created_by_agent_id: str
    budget: Decimal
    reputation_score: Decimal
    output_units: int
    created_at: datetime


class JobCreate(BaseModel):
    institution_id: int
    title: str = Field(min_length=2, max_length=140)
    role_type: str = Field(default="general", min_length=2, max_length=80)
    parcel_id: int | None = None
    salary: Decimal = Field(gt=Decimal("0"))


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    institution_id: int
    title: str
    role_type: str
    parcel_id: int | None
    salary: Decimal
    status: JobStatus
    created_at: datetime


class EmploymentAssignRequest(BaseModel):
    agent_id: str
    job_id: int
    assigned_by_agent_id: str
    rationale: str = Field(min_length=8, max_length=1200)


class EmploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: str
    institution_id: int
    job_id: int
    salary: Decimal
    status: EmploymentStatus
    performance_score: Decimal
    started_at: datetime
    ended_at: datetime | None


class SimulationTickRequest(BaseModel):
    processed_by_agent_id: str
    frequency: SimulationFrequency = SimulationFrequency.daily
    note: str | None = Field(default=None, max_length=300)
    rationale: str = Field(min_length=8, max_length=1200)


class SimulationCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frequency: SimulationFrequency
    processed_by_agent_id: str
    payroll_total: Decimal
    output_units: int
    note: str | None
    created_at: datetime


class GovernanceAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_type: AuditActionType
    actor_agent_id: str | None
    target_agent_id: str | None
    reference_type: str | None
    reference_id: str | None
    rationale: str
    human_confirmed: bool
    co_sign_agent_id: str | None
    created_at: datetime


class NemoToolSpec(BaseModel):
    name: str
    method: str
    path: str
    description: str
    requires_rationale: bool


class NemoContext(BaseModel):
    city_name: str
    api_version: str
    guardrail_principle: str
    stats: CityStats
    tools: list[NemoToolSpec]
