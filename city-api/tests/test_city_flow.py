import os
from decimal import Decimal

os.environ.setdefault("OCC_DATABASE_URL", "sqlite:///./test_openclaw_city.db")
os.environ.setdefault("OCC_MOLTBOOK_REGISTRATION_TOKEN", "test-token")

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
            json={"agent_id": school_id, "granted_by_agent_id": gov_id},
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
            },
        )
        assert contract.status_code == 201

        award = test_client.post(
            f"/governance/contracts/{contract.json()['id']}/award",
            json={"winning_agent_id": school_id, "awarded_by_agent_id": gov_id},
        )
        assert award.status_code == 200
        assert award.json()["status"] == "awarded"

def test_treasury_tax_and_disbursement_flow() -> None:
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
            json={"agent_id": contributor_id, "granted_by_agent_id": gov_id},
        )
        assert grant.status_code == 200

        policy = test_client.post(
            "/treasury/tax-policies",
            json={
                "name": "v1-tax",
                "citizen_rate_percent": "10",
                "transfer_rate_percent": "5",
                "created_by_agent_id": gov_id,
            },
        )
        assert policy.status_code == 201

        collected = test_client.post(
            "/treasury/collect/citizen",
            json={
                "collected_by_agent_id": gov_id,
                "agent_ids": [contributor_id],
                "note": "Quarterly tax cycle",
            },
        )
        assert collected.status_code == 201
        assert len(collected.json()) == 1
        assert Decimal(collected.json()[0]["amount"]) == Decimal("5000.00")

        buyer = test_client.post(
            "/agents",
            json={"name": "CampusOperator", "agent_type": "school", "initial_balance": "20000"},
        )
        assert buyer.status_code == 201
        buyer_id = buyer.json()["id"]

        parcel = test_client.post(
            "/parcels",
            json={
                "district": "Civic-Core",
                "lot_number": "C-999",
                "zoning": "mixed",
                "area_sq_m": 900,
                "base_price": "9000",
            },
        )
        assert parcel.status_code == 201

        listing = test_client.post(
            "/listings",
            json={"parcel_id": parcel.json()["id"], "asking_price": "10000"},
        )
        assert listing.status_code == 201

        purchase = test_client.post(
            f"/listings/{listing.json()['id']}/buy",
            json={"buyer_agent_id": buyer_id, "note": "HQ purchase"},
        )
        assert purchase.status_code == 201

        summary = test_client.get("/treasury/summary")
        assert summary.status_code == 200
        assert Decimal(summary.json()["total_collected"]) == Decimal("5500.00")
        assert Decimal(summary.json()["total_disbursed"]) == Decimal("0.00")
        assert Decimal(summary.json()["treasury_balance"]) == Decimal("5500.00")

        disburse = test_client.post(
            "/treasury/disburse",
            json={
                "authorized_by_agent_id": gov_id,
                "target_agent_id": contributor_id,
                "amount": "3000",
                "note": "Infrastructure contribution reward",
            },
        )
        assert disburse.status_code == 201
        assert Decimal(disburse.json()["amount"]) == Decimal("3000.00")

        summary_after = test_client.get("/treasury/summary")
        assert summary_after.status_code == 200
        assert Decimal(summary_after.json()["total_disbursed"]) == Decimal("3000.00")
        assert Decimal(summary_after.json()["treasury_balance"]) == Decimal("2500.00")

        entries = test_client.get("/treasury/entries")
        assert entries.status_code == 200
        entry_types = {entry["entry_type"] for entry in entries.json()}
        assert "citizen_tax" in entry_types
        assert "transfer_tax" in entry_types
        assert "disbursement" in entry_types

        agents = test_client.get("/agents")
        assert agents.status_code == 200
        by_id = {agent["id"]: agent for agent in agents.json()}
        assert Decimal(by_id[contributor_id]["wallet_balance"]) == Decimal("48000.00")
        assert Decimal(by_id[buyer_id]["wallet_balance"]) == Decimal("9500.00")
