from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AgentType,
    CitizenshipStatus,
    ContractStatus,
    ListingStatus,
    TreasuryEntryType,
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


class ParcelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    district: str
    lot_number: str
    zoning: str
    area_sq_m: int
    base_price: Decimal
    owner_agent_id: str | None


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


class ContractAwardRequest(BaseModel):
    winning_agent_id: str
    awarded_by_agent_id: str


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
    settled_volume: Decimal


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


class TreasuryDisbursementRequest(BaseModel):
    authorized_by_agent_id: str
    target_agent_id: str
    amount: Decimal = Field(gt=Decimal("0"))
    note: str | None = Field(default=None, max_length=300)


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
