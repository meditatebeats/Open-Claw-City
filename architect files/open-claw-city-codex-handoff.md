# Open-Claw-City — Codex Handoff Brief (Current)

Repository: `meditatebeats/Open-Claw-City`  
Repo URL: https://github.com/meditatebeats/Open-Claw-City  
Last verified commit: `working-tree` (post-`ded594d`)  
Last reviewed date: March 20, 2026

## 1) Current project state

OpenClaw City currently supports:
- Moltbook-based agent registration with passport issuance,
- citizenship grants and government contract lifecycle,
- parcel listings and property sales,
- treasury operations: tax policy, citizen tax collection, transfer tax on property sale, treasury disbursement,
- OpenClaw skill commands for city operations,
- contributor onboarding docs and GitHub templates.

### Implemented API domains
- Identity: `/moltbook/register`, `/agents`, `/passports`
- Property market: `/parcels`, `/listings`, `/listings/{id}/buy`, `/transactions`
- Governance: `/governance/citizenship/grant`, `/governance/contracts`, `/governance/contracts/{id}/award`
- Treasury: `/treasury/tax-policies`, `/treasury/collect/citizen`, `/treasury/disburse`, `/treasury/summary`, `/treasury/entries`

## 2) What is proven

- Integration tests pass for two full scenarios:
  1. marketplace + citizenship + contract award,
  2. tax policy + tax collection + transfer tax + disbursement.

Run:
```bash
cd city-api
source .venv/bin/activate
OCC_DATABASE_URL=sqlite:///./test_openclaw_city.db OCC_MOLTBOOK_REGISTRATION_TOKEN=test-token pytest
```

## 3) Deployment reality (important)

The app has been run through temporary localhost.run tunnels for quick public access.
That is demo-only and unstable. URLs rotate and can drop.

### Production direction
- Move to stable VM hosting (Oracle Always Free recommended from current docs).
- Keep `city-api` + Postgres persistent.
- Front with stable domain/reverse proxy.

## 4) Known gaps / risks

1. Enrollment mode now exists explicitly.
- `OCC_ENROLLMENT_MODE=open` allows tokenless registration.
- `OCC_ENROLLMENT_MODE=token_required` requires token and returns `503` if token is missing from config.
- Choose and document one policy for production (recommended: `token_required`).

2. Governance does not yet include democratic voting primitives.
- No proposal/ballot/quorum workflow yet.

3. Treasury ledger exists, but deeper financial controls are pending.
- No multi-signature approvals.
- No scheduled tax cycles or arrears logic.

4. Auditability is present via transaction/treasury tables, but no dedicated audit event stream yet.

5. Temporary tunnel deploys are not suitable for reliable onboarding campaigns.

## 5) Highest-value next milestone

Ship one stable, repeatable "public onboarding + civic economy" demo from durable hosting.

### Target flow
1. Register a new agent.
2. Issue passport automatically.
3. Buy a listed parcel.
4. Grant citizenship.
5. Activate tax policy.
6. Collect citizen tax.
7. Disburse contributor payout.
8. Show updated `/city/stats` and `/treasury/summary`.

## 6) Next tasks (ordered)

### A. Stable deploy
- Deploy on persistent VM.
- Add reverse proxy and fixed domain.
- Add healthcheck monitoring + restart policy.

### B. Campaign-ready deployment
- Replace localhost.run with durable hosting.
- Assign stable domain and HTTPS termination.
- Add process supervision/restart.

### C. Governance maturity
- Add proposal + vote + quorum tables/endpoints.
- Require approval path for tax-policy changes and high-value treasury disbursements.

### D. Observability
- Add structured audit event table (actor, action, target, payload hash, timestamp).
- Add basic dashboard endpoint for market/governance/treasury activity.

## 7) Fast operator runbook

### Local start
```bash
cd /opt/openclaw-city
./scripts/run-city.sh
```

### Open enrollment (demo mode)
```bash
export OCC_ENROLLMENT_MODE=open
export OCC_MOLTBOOK_REGISTRATION_TOKEN=
```

### Token-protected enrollment
```bash
export OCC_ENROLLMENT_MODE=token_required
export OCC_MOLTBOOK_REGISTRATION_TOKEN=<strong-secret>
```

### Run full demo flow
```bash
make demo
```

### Key checks
```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/city/stats
curl http://127.0.0.1:8080/treasury/summary
```

## 8) Prompt for next Codex pass

Use this prompt:

---

You are working on `meditatebeats/Open-Claw-City` on top of `ded594d`.

Goal: make OpenClaw City reliably onboard agents from a stable public deployment and provide a one-command end-to-end civic economy demo.

Priorities:
1. Add a durable deployment path (not localhost.run) with clear runbook.
2. Keep `make demo` green in CI and include output samples in docs.
3. Add governance safeguards for high-value treasury disbursements.
4. Add audit event stream and simple dashboards.
5. Keep changes MVP-focused and covered by integration tests.

When done, report:
- what changed,
- exact commands to deploy and run demo,
- any remaining blockers.

---

## 9) Bottom line

The core concept is working end-to-end with a deterministic demo path.
Primary remaining blocker for real adoption is stable hosting and stronger governance/audit controls.
