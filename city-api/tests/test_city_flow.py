import os
from decimal import Decimal

os.environ.setdefault("OCC_DATABASE_URL", "sqlite:///./test_openclaw_city.db")
os.environ.setdefault("OCC_MOLTBOOK_REGISTRATION_TOKEN", "test-token")
os.environ.setdefault("OCC_ENROLLMENT_MODE", "token_required")
os.environ.setdefault("OCC_TREASURY_HUMAN_CONFIRMATION_THRESHOLD", "5000")

from fastapi.testclient import TestClient

from app.db import engine
from app.main import app
from app.models import Base


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_marketplace_governance_flow() -> None:
    _reset_db()

    with TestClient(app) as test_client:
        manifest = test_client.get("/city/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["enrollment_mode"] == "token_required"
        nemo = test_client.get("/integrations/nemo/context")
        assert nemo.status_code == 200
        assert any(tool["name"] == "run_simulation_tick" for tool in nemo.json()["tools"])

        denied = test_client.post(
            "/moltbook/register",
            json={
                "moltbook_agent_id": "moltbook-denied-001",
                "display_name": "Denied Agent",
                "agent_type": "citizen",
                "initial_balance": "1000",
            },
        )
        assert denied.status_code == 401

        gov = test_client.post(
            "/agents",
            json={"name": "CityCouncil", "agent_type": "government", "initial_balance": "500000"},
        )
        assert gov.status_code == 201
        gov_id = gov.json()["id"]

        school = test_client.post(
            "/moltbook/register",
            json={
                "moltbook_agent_id": "moltbook-school-001",
                "display_name": "AI School District",
                "agent_type": "school",
                "initial_balance": "150000",
            },
            headers={"X-Moltbook-Token": "test-token"},
        )
        assert school.status_code == 200
        school_id = school.json()["id"]
        assert school.json()["passport_number"]

        grant = test_client.post(
            "/governance/citizenship/grant",
            json={
                "agent_id": school_id,
                "granted_by_agent_id": gov_id,
                "rationale": "School agent passed onboarding and should participate in civic contracts.",
            },
        )
        assert grant.status_code == 200
        assert grant.json()["citizenship_status"] == "citizen"

        parcel = test_client.post(
            "/parcels",
            json={
                "district": "Academy-Hills",
                "lot_number": "A-900",
                "zoning": "education",
                "area_sq_m": 1000,
                "base_price": "80000",
            },
        )
        assert parcel.status_code == 201

        listing = test_client.post(
            "/listings",
            json={"parcel_id": parcel.json()["id"], "asking_price": "100000"},
        )
        assert listing.status_code == 201
        listing_id = listing.json()["id"]

        purchase = test_client.post(
            f"/listings/{listing_id}/buy",
            json={"buyer_agent_id": school_id, "note": "Initial campus acquisition"},
        )
        assert purchase.status_code == 201

        contract = test_client.post(
            "/governance/contracts",
            json={
                "title": "AI Public Education Platform",
                "scope": "Build and operate a city-wide learning platform with audit logs and safety checks.",
                "budget": "75000",
                "issuing_agency_id": gov_id,
                "human_guardrail_policy": "All recommendations must prioritize student well-being, safety, and human oversight.",
                "human_outcome_target": "Increase access to education while preserving human teacher review on major decisions.",
                "action_rationale": "Public contract needed to guarantee transparent education delivery.",
            },
        )
        assert contract.status_code == 201

        award = test_client.post(
            f"/governance/contracts/{contract.json()['id']}/award",
            json={
                "winning_agent_id": school_id,
                "awarded_by_agent_id": gov_id,
                "rationale": "School agent met criteria and has citizen status.",
            },
        )
        assert award.status_code == 200
        assert award.json()["status"] == "awarded"

        contract_audit = test_client.get("/audit/contracts")
        assert contract_audit.status_code == 200
        actions = {entry["action_type"] for entry in contract_audit.json()}
        assert "contract_created" in actions
        assert "contract_awarded" in actions


def test_treasury_tax_and_disbursement_guardrails() -> None:
    _reset_db()

    with TestClient(app) as test_client:
        gov = test_client.post(
            "/agents",
            json={"name": "TreasuryCouncil", "agent_type": "government", "initial_balance": "300000"},
        )
        assert gov.status_code == 201
        gov_id = gov.json()["id"]

        contributor = test_client.post(
            "/agents",
            json={"name": "BuilderGuild", "agent_type": "company", "initial_balance": "50000"},
        )
        assert contributor.status_code == 201
        contributor_id = contributor.json()["id"]

        grant = test_client.post(
            "/governance/citizenship/grant",
            json={
                "agent_id": contributor_id,
                "granted_by_agent_id": gov_id,
                "rationale": "Company should be eligible for taxed commerce and contributor payouts.",
            },
        )
        assert grant.status_code == 200

        policy = test_client.post(
            "/treasury/tax-policies",
            json={
                "name": "v1-tax",
                "citizen_rate_percent": "10",
                "transfer_rate_percent": "5",
                "created_by_agent_id": gov_id,
                "rationale": "Initial policy to fund public services and contributor disbursements.",
            },
        )
        assert policy.status_code == 201

        collected = test_client.post(
            "/treasury/collect/citizen",
            json={
                "collected_by_agent_id": gov_id,
                "agent_ids": [contributor_id],
                "note": "Quarterly tax cycle",
                "rationale": "Collect scheduled taxes from participating citizens.",
            },
        )
        assert collected.status_code == 201
        assert len(collected.json()) == 1
        assert Decimal(collected.json()[0]["amount"]) == Decimal("5000.00")

        blocked = test_client.post(
            "/treasury/disburse",
            json={
                "authorized_by_agent_id": gov_id,
                "target_agent_id": contributor_id,
                "amount": "5000",
                "note": "Large payout without confirmation",
                "rationale": "Attempt disbursement over threshold without confirmation.",
            },
        )
        assert blocked.status_code == 400

        disburse = test_client.post(
            "/treasury/disburse",
            json={
                "authorized_by_agent_id": gov_id,
                "target_agent_id": contributor_id,
                "amount": "5000",
                "note": "Approved infrastructure payout",
                "rationale": "Approved payout for verified contributor output.",
                "human_confirmed": True,
            },
        )
        assert disburse.status_code == 201
        assert Decimal(disburse.json()["amount"]) == Decimal("5000.00")

        summary_after = test_client.get("/treasury/summary")
        assert summary_after.status_code == 200
        assert Decimal(summary_after.json()["total_disbursed"]) == Decimal("5000.00")
        assert Decimal(summary_after.json()["treasury_balance"]) == Decimal("0.00")

        treasury_audit = test_client.get("/audit/treasury")
        assert treasury_audit.status_code == 200
        treasury_actions = {entry["action_type"] for entry in treasury_audit.json()}
        assert "tax_policy_created" in treasury_actions
        assert "taxes_collected" in treasury_actions
        assert "treasury_disbursement" in treasury_actions


def test_institution_employment_simulation_loop() -> None:
    _reset_db()

    with TestClient(app) as test_client:
        gov = test_client.post(
            "/agents",
            json={"name": "GovLoop", "agent_type": "government", "initial_balance": "400000"},
        )
        assert gov.status_code == 201
        gov_id = gov.json()["id"]

        resident = test_client.post(
            "/agents",
            json={"name": "ResidentLoop", "agent_type": "citizen", "initial_balance": "1000"},
        )
        assert resident.status_code == 201
        resident_id = resident.json()["id"]

        grant = test_client.post(
            "/governance/citizenship/grant",
            json={
                "agent_id": resident_id,
                "granted_by_agent_id": gov_id,
                "rationale": "Resident should be promoted to citizen for labor participation.",
            },
        )
        assert grant.status_code == 200

        parcel = test_client.post(
            "/parcels",
            json={
                "district": "Civic-Core",
                "lot_number": "C-111",
                "zoning": "civic",
                "area_sq_m": 850,
                "base_price": "10000",
            },
        )
        assert parcel.status_code == 201
        parcel_id = parcel.json()["id"]

        institution = test_client.post(
            "/institutions",
            json={
                "name": "Loop Academy",
                "institution_type": "school",
                "parcel_id": parcel_id,
                "created_by_agent_id": gov_id,
                "budget": "15000",
                "rationale": "Create education institution for recurring service output.",
            },
        )
        assert institution.status_code == 201
        institution_id = institution.json()["id"]

        job = test_client.post(
            "/jobs",
            json={
                "institution_id": institution_id,
                "title": "Learning Systems Operator",
                "role_type": "education",
                "salary": "2200",
            },
        )
        assert job.status_code == 201

        assign = test_client.post(
            "/employment/assign",
            json={
                "agent_id": resident_id,
                "job_id": job.json()["id"],
                "assigned_by_agent_id": gov_id,
                "rationale": "Assign resident to active institution role for payroll loop.",
            },
        )
        assert assign.status_code == 201

        tick = test_client.post(
            "/simulation/tick",
            json={
                "processed_by_agent_id": gov_id,
                "frequency": "daily",
                "note": "Daily simulation",
                "rationale": "Process payroll and output generation for active employments.",
            },
        )
        assert tick.status_code == 201
        assert Decimal(tick.json()["payroll_total"]) == Decimal("2200.00")
        assert tick.json()["output_units"] >= 1

        agents = test_client.get("/agents")
        by_id = {agent["id"]: agent for agent in agents.json()}
        assert Decimal(by_id[resident_id]["wallet_balance"]) >= Decimal("3200.00")
        assert by_id[resident_id]["trust_tier"] in {"citizen", "trusted_contributor"}

        stats = test_client.get("/city/stats")
        assert stats.status_code == 200
        assert stats.json()["institution_count"] >= 1
        assert stats.json()["employed_agents"] >= 1
        assert Decimal(stats.json()["payroll_volume"]) >= Decimal("2200.00")
        assert stats.json()["occupied_parcels"] >= 1

        events = test_client.get("/audit/events")
        assert events.status_code == 200
        actions = {entry["action_type"] for entry in events.json()}
        assert "employment_assigned" in actions
        assert "simulation_tick" in actions
