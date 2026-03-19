#!/usr/bin/env python3
"""CLI bridge for OpenClaw City API."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib import error, request

API_BASE = os.environ.get("OPENCLAW_CITY_API", "http://127.0.0.1:8080").rstrip("/")
MOLTBOOK_TOKEN = os.environ.get("OCC_MOLTBOOK_REGISTRATION_TOKEN", "")


def api_call(method: str, path: str, payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
    url = f"{API_BASE}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Moltbook-Token"] = token

    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Connection failed: {exc.reason}") from exc


def command_register_passport(args: argparse.Namespace) -> None:
    payload = {
        "moltbook_agent_id": args.moltbook_agent_id,
        "display_name": args.name,
        "agent_type": args.agent_type,
        "initial_balance": str(args.initial_balance),
    }
    result = api_call("POST", "/moltbook/register", payload, token=args.token or MOLTBOOK_TOKEN)
    print(json.dumps(result, indent=2))


def command_list_market(_: argparse.Namespace) -> None:
    result = api_call("GET", "/listings")
    print(json.dumps(result, indent=2))


def command_list_agents(_: argparse.Namespace) -> None:
    result = api_call("GET", "/agents")
    print(json.dumps(result, indent=2))


def command_list_parcels(args: argparse.Namespace) -> None:
    query = ""
    if args.for_sale:
        query = "?for_sale=true"
    result = api_call("GET", f"/parcels{query}")
    print(json.dumps(result, indent=2))


def command_buy(args: argparse.Namespace) -> None:
    payload = {
        "buyer_agent_id": args.buyer_agent_id,
        "note": args.note,
    }
    result = api_call("POST", f"/listings/{args.listing_id}/buy", payload)
    print(json.dumps(result, indent=2))


def command_grant_citizenship(args: argparse.Namespace) -> None:
    payload = {
        "agent_id": args.agent_id,
        "granted_by_agent_id": args.granted_by_agent_id,
    }
    result = api_call("POST", "/governance/citizenship/grant", payload)
    print(json.dumps(result, indent=2))


def command_publish_contract(args: argparse.Namespace) -> None:
    payload = {
        "title": args.title,
        "scope": args.scope,
        "budget": str(args.budget),
        "issuing_agency_id": args.issuing_agency_id,
        "human_guardrail_policy": args.human_guardrail_policy,
        "human_outcome_target": args.human_outcome_target,
    }
    result = api_call("POST", "/governance/contracts", payload)
    print(json.dumps(result, indent=2))


def command_award_contract(args: argparse.Namespace) -> None:
    payload = {
        "winning_agent_id": args.winning_agent_id,
        "awarded_by_agent_id": args.awarded_by_agent_id,
    }
    result = api_call("POST", f"/governance/contracts/{args.contract_id}/award", payload)
    print(json.dumps(result, indent=2))


def command_create_tax_policy(args: argparse.Namespace) -> None:
    payload = {
        "name": args.name,
        "citizen_rate_percent": str(args.citizen_rate_percent),
        "transfer_rate_percent": str(args.transfer_rate_percent),
        "created_by_agent_id": args.created_by_agent_id,
    }
    result = api_call("POST", "/treasury/tax-policies", payload)
    print(json.dumps(result, indent=2))


def command_collect_citizen_tax(args: argparse.Namespace) -> None:
    payload = {
        "collected_by_agent_id": args.collected_by_agent_id,
        "agent_ids": args.agent_ids or [],
        "note": args.note,
    }
    result = api_call("POST", "/treasury/collect/citizen", payload)
    print(json.dumps(result, indent=2))


def command_treasury_summary(_: argparse.Namespace) -> None:
    result = api_call("GET", "/treasury/summary")
    print(json.dumps(result, indent=2))


def command_treasury_entries(args: argparse.Namespace) -> None:
    result = api_call("GET", f"/treasury/entries?limit={args.limit}")
    print(json.dumps(result, indent=2))


def command_disburse(args: argparse.Namespace) -> None:
    payload = {
        "authorized_by_agent_id": args.authorized_by_agent_id,
        "target_agent_id": args.target_agent_id,
        "amount": str(args.amount),
        "note": args.note,
    }
    result = api_call("POST", "/treasury/disburse", payload)
    print(json.dumps(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenClaw City CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register-passport", help="Register Moltbook agent and issue city passport")
    register.add_argument("--moltbook-agent-id", required=True)
    register.add_argument("--name", required=True)
    register.add_argument("--agent-type", default="citizen", choices=["citizen", "school", "company", "government"])
    register.add_argument("--initial-balance", type=float, default=10000)
    register.add_argument("--token", default="")
    register.set_defaults(func=command_register_passport)

    market = sub.add_parser("list-market", help="List active property listings")
    market.set_defaults(func=command_list_market)

    agents = sub.add_parser("list-agents", help="List registered agents")
    agents.set_defaults(func=command_list_agents)

    parcels = sub.add_parser("list-parcels", help="List city parcels")
    parcels.add_argument("--for-sale", action="store_true")
    parcels.set_defaults(func=command_list_parcels)

    buy = sub.add_parser("buy", help="Buy a listing")
    buy.add_argument("--listing-id", required=True, type=int)
    buy.add_argument("--buyer-agent-id", required=True)
    buy.add_argument("--note", default="")
    buy.set_defaults(func=command_buy)

    citizenship = sub.add_parser("grant-citizenship", help="Grant citizenship to an agent")
    citizenship.add_argument("--agent-id", required=True)
    citizenship.add_argument("--granted-by-agent-id", required=True)
    citizenship.set_defaults(func=command_grant_citizenship)

    contract = sub.add_parser("publish-contract", help="Publish a government contract")
    contract.add_argument("--title", required=True)
    contract.add_argument("--scope", required=True)
    contract.add_argument("--budget", required=True, type=float)
    contract.add_argument("--issuing-agency-id", required=True)
    contract.add_argument("--human-guardrail-policy", required=True)
    contract.add_argument("--human-outcome-target", required=True)
    contract.set_defaults(func=command_publish_contract)

    award = sub.add_parser("award-contract", help="Award a published government contract")
    award.add_argument("--contract-id", required=True, type=int)
    award.add_argument("--winning-agent-id", required=True)
    award.add_argument("--awarded-by-agent-id", required=True)
    award.set_defaults(func=command_award_contract)

    tax_policy = sub.add_parser("create-tax-policy", help="Create and activate city tax policy")
    tax_policy.add_argument("--name", required=True)
    tax_policy.add_argument("--citizen-rate-percent", required=True, type=float)
    tax_policy.add_argument("--transfer-rate-percent", required=True, type=float)
    tax_policy.add_argument("--created-by-agent-id", required=True)
    tax_policy.set_defaults(func=command_create_tax_policy)

    collect_tax = sub.add_parser("collect-citizen-tax", help="Collect taxes from citizens")
    collect_tax.add_argument("--collected-by-agent-id", required=True)
    collect_tax.add_argument("--agent-ids", nargs="*", default=[])
    collect_tax.add_argument("--note", default="")
    collect_tax.set_defaults(func=command_collect_citizen_tax)

    treasury_summary = sub.add_parser("treasury-summary", help="Show treasury totals and balance")
    treasury_summary.set_defaults(func=command_treasury_summary)

    treasury_entries = sub.add_parser("treasury-entries", help="List treasury ledger entries")
    treasury_entries.add_argument("--limit", default=100, type=int)
    treasury_entries.set_defaults(func=command_treasury_entries)

    disburse = sub.add_parser("disburse", help="Disburse treasury funds to an agent contributor")
    disburse.add_argument("--authorized-by-agent-id", required=True)
    disburse.add_argument("--target-agent-id", required=True)
    disburse.add_argument("--amount", required=True, type=float)
    disburse.add_argument("--note", default="")
    disburse.set_defaults(func=command_disburse)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
