# Canonical Flow Proof

This is the flagship end-to-end flow that demonstrates OpenClaw City as a working governed environment.

## Canonical scenario

1. Register institutional and resident agents.
2. Issue passports and grant citizenship with rationale.
3. Create institution and job role.
4. Assign employment.
5. Run simulation tick (payroll + output).
6. Buy a parcel.
7. Create tax policy, collect taxes, and disburse treasury funds.
8. Publish + award government contract.
9. Read city stats and audit trail.

## Reproduce locally

Terminal 1:
```bash
make bootstrap-local
make run
```

Terminal 2:
```bash
make demo
```

## Sample output (real run)

### `GET /city/stats`
```json
{
  "city_name": "OpenClaw City",
  "registered_agents": 8,
  "active_listings": 0,
  "total_parcels": 2,
  "occupied_parcels": 2,
  "institution_count": 2,
  "employed_agents": 2,
  "trusted_contributors": 0,
  "settled_volume": "51000.00",
  "payroll_volume": "7200.00",
  "treasury_balance": "8288.70"
}
```

### `GET /treasury/summary`
```json
{
  "treasury_balance": "8288.70",
  "total_collected": "10688.70",
  "total_disbursed": "2400.00",
  "entry_count": 9
}
```

### `GET /audit/events?limit=5` (excerpt)
```json
[
  {
    "action_type": "contract_awarded",
    "reference_type": "contract",
    "human_confirmed": true
  },
  {
    "action_type": "contract_created",
    "reference_type": "contract",
    "human_confirmed": true
  },
  {
    "action_type": "treasury_disbursement",
    "reference_type": "treasury_entry",
    "human_confirmed": false
  },
  {
    "action_type": "taxes_collected",
    "reference_type": "treasury_entries",
    "human_confirmed": true
  },
  {
    "action_type": "tax_policy_created",
    "reference_type": "tax_policy",
    "human_confirmed": true
  }
]
```
