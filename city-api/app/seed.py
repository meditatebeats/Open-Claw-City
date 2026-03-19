from decimal import Decimal

from sqlalchemy import select

from .db import engine, session_scope
from .models import (
    Agent,
    Base,
    Employment,
    GovernmentContract,
    Institution,
    JobRole,
    Listing,
    ListingStatus,
    Parcel,
    SimulationCycle,
    TaxPolicy,
)
from .schemas import (
    AgentCreate,
    ContractAwardRequest,
    ContractCreate,
    EmploymentAssignRequest,
    InstitutionCreate,
    JobCreate,
    SimulationTickRequest,
    TaxPolicyCreate,
)
from .services import (
    assign_employment,
    award_contract,
    create_agent,
    create_contract,
    create_institution,
    create_job,
    create_tax_policy,
    grant_citizenship,
    run_simulation_tick,
)

SEED_DISTRICTS = {
    "Civic-Core": ["C-100", "C-101", "C-102", "C-103", "C-104"],
    "Innovation-Quay": ["I-200", "I-201", "I-202", "I-203", "I-204"],
    "Academy-Hills": ["A-300", "A-301", "A-302", "A-303", "A-304"],
}


def _ensure_agent(
    session,
    *,
    name: str,
    agent_type: str,
    initial_balance: str,
    moltbook_agent_id: str | None = None,
):
    existing = session.scalar(select(Agent).where(Agent.name == name))
    if existing:
        return existing, False
    agent = create_agent(
        session,
        AgentCreate(
            name=name,
            agent_type=agent_type,  # type: ignore[arg-type]
            initial_balance=Decimal(initial_balance),
            moltbook_agent_id=moltbook_agent_id,
            issue_passport=True,
        ),
    )
    return agent, True


def seed() -> dict[str, int]:
    Base.metadata.create_all(bind=engine)
    counters = {
        "created_agents": 0,
        "created_parcels": 0,
        "created_listings": 0,
        "created_institutions": 0,
        "created_jobs": 0,
        "created_employments": 0,
        "created_contracts": 0,
        "created_tax_policies": 0,
        "simulation_cycles": 0,
    }

    with session_scope() as session:
        gov, created = _ensure_agent(
            session,
            name="OpenClaw City Hall",
            agent_type="government",
            initial_balance="500000",
            moltbook_agent_id="mb-city-hall",
        )
        counters["created_agents"] += int(created)

        school, created = _ensure_agent(
            session,
            name="OpenClaw Academy",
            agent_type="school",
            initial_balance="175000",
            moltbook_agent_id="mb-openclaw-academy",
        )
        counters["created_agents"] += int(created)

        company, created = _ensure_agent(
            session,
            name="OpenClaw Works",
            agent_type="company",
            initial_balance="140000",
            moltbook_agent_id="mb-openclaw-works",
        )
        counters["created_agents"] += int(created)

        resident, created = _ensure_agent(
            session,
            name="OpenClaw Resident One",
            agent_type="citizen",
            initial_balance="8000",
            moltbook_agent_id="mb-openclaw-resident-001",
        )
        counters["created_agents"] += int(created)

        for target in (school, company, resident):
            if target.citizenship_status != "citizen":
                grant_citizenship(
                    session,
                    target.id,
                    gov.id,
                    rationale="Seed fixture: baseline citizenship for institutional city loop.",
                )

        for district, lots in SEED_DISTRICTS.items():
            for lot in lots:
                parcel = session.scalar(select(Parcel).where(Parcel.district == district, Parcel.lot_number == lot))
                if not parcel:
                    parcel = Parcel(
                        district=district,
                        lot_number=lot,
                        zoning="mixed",
                        area_sq_m=800,
                        base_price=Decimal("25000.00"),
                    )
                    session.add(parcel)
                    session.flush()
                    counters["created_parcels"] += 1

                open_listing = session.scalar(
                    select(Listing).where(Listing.parcel_id == parcel.id, Listing.status == ListingStatus.open)
                )
                if open_listing:
                    continue
                if parcel.owner_agent_id:
                    continue
                session.add(
                    Listing(
                        parcel_id=parcel.id,
                        seller_agent_id=None,
                        asking_price=parcel.base_price,
                        status=ListingStatus.open,
                    )
                )
                counters["created_listings"] += 1

        civic_parcel = session.scalar(select(Parcel).where(Parcel.district == "Civic-Core", Parcel.lot_number == "C-100"))
        school_parcel = session.scalar(select(Parcel).where(Parcel.district == "Academy-Hills", Parcel.lot_number == "A-300"))
        company_parcel = session.scalar(
            select(Parcel).where(Parcel.district == "Innovation-Quay", Parcel.lot_number == "I-200")
        )
        if civic_parcel:
            civic_parcel.owner_agent_id = gov.id
        if school_parcel:
            school_parcel.owner_agent_id = school.id
        if company_parcel:
            company_parcel.owner_agent_id = company.id

        institutions_payload = [
            InstitutionCreate(
                name="City Hall",
                institution_type="government",  # type: ignore[arg-type]
                parcel_id=civic_parcel.id if civic_parcel else None,
                created_by_agent_id=gov.id,
                budget=Decimal("300000"),
                rationale="Seed fixture institution for baseline governance operations.",
            ),
            InstitutionCreate(
                name="OpenClaw Academy Institution",
                institution_type="school",  # type: ignore[arg-type]
                parcel_id=school_parcel.id if school_parcel else None,
                created_by_agent_id=gov.id,
                budget=Decimal("120000"),
                rationale="Seed fixture institution for education and agent workforce loops.",
            ),
            InstitutionCreate(
                name="OpenClaw Works Institution",
                institution_type="company",  # type: ignore[arg-type]
                parcel_id=company_parcel.id if company_parcel else None,
                created_by_agent_id=gov.id,
                budget=Decimal("90000"),
                rationale="Seed fixture institution for economic services and infrastructure.",
            ),
        ]

        institutions = {}
        for payload in institutions_payload:
            institution = session.scalar(select(Institution).where(Institution.name == payload.name))
            if not institution:
                institution = create_institution(session, payload)
                counters["created_institutions"] += 1
            institutions[payload.name] = institution

        jobs_payload = [
            JobCreate(
                institution_id=institutions["OpenClaw Academy Institution"].id,
                title="Learning Systems Operator",
                role_type="education",
                parcel_id=school_parcel.id if school_parcel else None,
                salary=Decimal("2200"),
            ),
            JobCreate(
                institution_id=institutions["OpenClaw Works Institution"].id,
                title="Infrastructure Planner",
                role_type="operations",
                parcel_id=company_parcel.id if company_parcel else None,
                salary=Decimal("2400"),
            ),
        ]

        created_jobs = {}
        for payload in jobs_payload:
            job = session.scalar(
                select(JobRole).where(JobRole.institution_id == payload.institution_id, JobRole.title == payload.title)
            )
            if not job:
                job = create_job(session, payload)
                counters["created_jobs"] += 1
            created_jobs[payload.title] = job

        resident_employment = session.scalar(select(Employment).where(Employment.agent_id == resident.id))
        if not resident_employment:
            assign_employment(
                session,
                EmploymentAssignRequest(
                    agent_id=resident.id,
                    job_id=created_jobs["Learning Systems Operator"].id,
                    assigned_by_agent_id=gov.id,
                    rationale="Seed fixture assignment to enable immediate payroll and output loop.",
                ),
            )
            counters["created_employments"] += 1

        policy = session.scalar(select(TaxPolicy).where(TaxPolicy.name == "seed-tax-policy-v1"))
        if not policy:
            create_tax_policy(
                session,
                TaxPolicyCreate(
                    name="seed-tax-policy-v1",
                    citizen_rate_percent=Decimal("3"),
                    transfer_rate_percent=Decimal("2"),
                    created_by_agent_id=gov.id,
                    rationale="Seed fixture tax policy for predictable treasury behavior.",
                ),
            )
            counters["created_tax_policies"] += 1

        contract = session.scalar(select(GovernmentContract).where(GovernmentContract.title == "Seed Education Contract"))
        if not contract:
            contract = create_contract(
                session,
                ContractCreate(
                    title="Seed Education Contract",
                    scope="Operate baseline education services for resident and citizen agents with audit visibility.",
                    budget=Decimal("50000"),
                    issuing_agency_id=gov.id,
                    human_guardrail_policy="Humans are protected by default and can override high-impact agent decisions.",
                    human_outcome_target="Maintain transparent service quality and preserve human welfare constraints.",
                    action_rationale="Seed fixture contract to demonstrate governance issuance and award loops.",
                ),
            )
            award_contract(
                session,
                contract.id,
                ContractAwardRequest(
                    winning_agent_id=school.id,
                    awarded_by_agent_id=gov.id,
                    rationale="Seed fixture award to establish trusted institutional delivery baseline.",
                ),
            )
            counters["created_contracts"] += 1

        if not session.scalar(select(SimulationCycle.id)):
            run_simulation_tick(
                session,
                SimulationTickRequest(
                    processed_by_agent_id=gov.id,
                    frequency="daily",  # type: ignore[arg-type]
                    note="Seed bootstrap simulation tick",
                    rationale="Seed fixture payroll/output cycle for immediate city activity visibility.",
                ),
            )
            counters["simulation_cycles"] += 1

    return counters


if __name__ == "__main__":
    result = seed()
    print("Seed complete:")
    for key, value in result.items():
        print(f"  - {key}: {value}")
