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
    parcels: Mapped[list[Parcel]] = relationship(back_populates="owner")
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
    listings: Mapped[list[Listing]] = relationship(back_populates="parcel")


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
