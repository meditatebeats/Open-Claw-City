import os
from pathlib import Path

os.environ.setdefault("OCC_DATABASE_URL", "sqlite:///./test_openclaw_city.db")
os.environ.setdefault("OCC_MOLTBOOK_REGISTRATION_TOKEN", "test-token")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
DB_PATH = Path("test_openclaw_city.db")


def _cleanup_db() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_marketplace_governance_flow() -> None:
    _cleanup_db()

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

    _cleanup_db()
