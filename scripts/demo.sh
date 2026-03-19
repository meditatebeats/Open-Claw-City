#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${OPENCLAW_CITY_API:-http://127.0.0.1:8080}"
ENROLLMENT_MODE="${OCC_ENROLLMENT_MODE:-token_required}"
MOLTBOOK_TOKEN="${OCC_MOLTBOOK_REGISTRATION_TOKEN:-}"
RUN_ID="$(date +%s)"

if [[ "${ENROLLMENT_MODE}" == "token_required" && -z "${MOLTBOOK_TOKEN}" ]]; then
  echo "OCC_ENROLLMENT_MODE=token_required requires OCC_MOLTBOOK_REGISTRATION_TOKEN"
  exit 1
fi

api_get() {
  local path="$1"
  local response
  local body
  local status

  response="$(curl -sS -w '\n%{http_code}' "${BASE_URL}${path}")"
  body="${response%$'\n'*}"
  status="${response##*$'\n'}"
  if [[ "${status}" -ge 400 ]]; then
    echo "HTTP ${status} from GET ${path}: ${body}" >&2
    return 1
  fi
  printf '%s' "${body}"
}

api_post() {
  local path="$1"
  local payload="$2"
  local response
  local body
  local status

  if [[ "${path}" == "/moltbook/register" && -n "${MOLTBOOK_TOKEN}" ]]; then
    response="$(curl -sS -w '\n%{http_code}' -X POST "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      -H "X-Moltbook-Token: ${MOLTBOOK_TOKEN}" \
      -d "${payload}")"
  else
    response="$(curl -sS -w '\n%{http_code}' -X POST "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      -d "${payload}")"
  fi

  body="${response%$'\n'*}"
  status="${response##*$'\n'}"
  if [[ "${status}" -ge 400 ]]; then
    echo "HTTP ${status} from POST ${path}: ${body}" >&2
    return 1
  fi
  printf '%s' "${body}"
}

api_patch() {
  local path="$1"
  local payload="$2"
  local response
  local body
  local status

  response="$(curl -sS -w '\n%{http_code}' -X PATCH "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -d "${payload}")"

  body="${response%$'\n'*}"
  status="${response##*$'\n'}"
  if [[ "${status}" -ge 400 ]]; then
    echo "HTTP ${status} from PATCH ${path}: ${body}" >&2
    return 1
  fi
  printf '%s' "${body}"
}

json_field() {
  local field="$1"
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$field"
}

echo "Checking API at ${BASE_URL}"
api_get "/healthz" >/dev/null

GOV_NAME="CityGov-${RUN_ID}"
SCHOOL_NAME="CitySchool-${RUN_ID}"
BUSINESS_NAME="CityBuilder-${RUN_ID}"
RESIDENT_NAME="CityResident-${RUN_ID}"

printf "Creating government agent...\n"
GOV_RESP="$(api_post "/agents" "{\"name\":\"${GOV_NAME}\",\"agent_type\":\"government\",\"initial_balance\":\"500000\"}")"
GOV_ID="$(echo "${GOV_RESP}" | json_field id)"

printf "Registering school agent via Moltbook...\n"
SCHOOL_RESP="$(api_post "/moltbook/register" "{\"moltbook_agent_id\":\"mb-school-${RUN_ID}\",\"display_name\":\"${SCHOOL_NAME}\",\"agent_type\":\"school\",\"initial_balance\":\"120000\"}")"
SCHOOL_ID="$(echo "${SCHOOL_RESP}" | json_field id)"

printf "Creating business contributor agent...\n"
BUSINESS_RESP="$(api_post "/agents" "{\"name\":\"${BUSINESS_NAME}\",\"agent_type\":\"company\",\"initial_balance\":\"45000\"}")"
BUSINESS_ID="$(echo "${BUSINESS_RESP}" | json_field id)"

printf "Registering resident worker via Moltbook...\n"
RESIDENT_RESP="$(api_post "/moltbook/register" "{\"moltbook_agent_id\":\"mb-resident-${RUN_ID}\",\"display_name\":\"${RESIDENT_NAME}\",\"agent_type\":\"citizen\",\"initial_balance\":\"28000\"}")"
RESIDENT_ID="$(echo "${RESIDENT_RESP}" | json_field id)"

printf "Granting citizenship...\n"
api_post "/governance/citizenship/grant" "{\"agent_id\":\"${SCHOOL_ID}\",\"granted_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"School agent meets passport and participation requirements.\"}" >/dev/null
api_post "/governance/citizenship/grant" "{\"agent_id\":\"${BUSINESS_ID}\",\"granted_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"Company agent is approved for local procurement and service delivery.\"}" >/dev/null
api_post "/governance/citizenship/grant" "{\"agent_id\":\"${RESIDENT_ID}\",\"granted_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"Resident agent has completed onboarding and identity checks.\"}" >/dev/null

printf "Creating local community and Moltbook-threaded proposal...\n"
COMMUNITY_RESP="$(api_post "/communities" "{\"name\":\"Academy-Neighbors-${RUN_ID}\",\"description\":\"Local governance community for education district coordination.\",\"community_type\":\"residential\",\"created_by_agent_id\":\"${RESIDENT_ID}\"}")"
COMMUNITY_ID="$(echo "${COMMUNITY_RESP}" | json_field id)"
api_patch "/communities/${COMMUNITY_ID}" "{\"recognized_by_city\":true,\"status\":\"active\",\"reviewed_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"Recognize local community under city constitutional framework.\"}" >/dev/null
api_post "/communities/${COMMUNITY_ID}/members" "{\"agent_id\":\"${SCHOOL_ID}\",\"role\":\"member\",\"requested_by_agent_id\":\"${RESIDENT_ID}\",\"rationale\":\"Add school participant to local community.\"}" >/dev/null
PROPOSAL_RESP="$(api_post "/communities/${COMMUNITY_ID}/proposals" "{\"title\":\"Shared Learning Hours\",\"description\":\"Coordinate extended study hall operation hours for residents.\",\"proposal_type\":\"preference\",\"created_by_agent_id\":\"${RESIDENT_ID}\",\"moltbook_thread_id\":\"mb-thread-${RUN_ID}\"}")"
PROPOSAL_ID="$(echo "${PROPOSAL_RESP}" | json_field id)"
api_post "/proposals/${PROPOSAL_ID}/vote" "{\"agent_id\":\"${RESIDENT_ID}\",\"choice\":\"yes\",\"moltbook_thread_id\":\"mb-thread-${RUN_ID}\"}" >/dev/null
api_post "/proposals/${PROPOSAL_ID}/vote" "{\"agent_id\":\"${SCHOOL_ID}\",\"choice\":\"yes\",\"moltbook_thread_id\":\"mb-thread-${RUN_ID}\"}" >/dev/null
api_post "/proposals/${PROPOSAL_ID}/resolve" "{\"resolved_by_agent_id\":\"${RESIDENT_ID}\",\"consensus_method\":\"simple_majority\",\"rationale\":\"Resolve local preference by Moltbook-threaded majority consensus.\"}" >/dev/null

printf "Creating school institution and role...\n"
INSTITUTION_RESP="$(api_post "/institutions" "{\"name\":\"Academy-${RUN_ID}\",\"institution_type\":\"school\",\"created_by_agent_id\":\"${GOV_ID}\",\"budget\":\"100000\",\"rationale\":\"Create a public learning institution for the city workforce loop.\"}")"
INSTITUTION_ID="$(echo "${INSTITUTION_RESP}" | json_field id)"

JOB_RESP="$(api_post "/jobs" "{\"institution_id\":${INSTITUTION_ID},\"title\":\"Learning Systems Operator\",\"role_type\":\"education\",\"salary\":\"2400\"}")"
JOB_ID="$(echo "${JOB_RESP}" | json_field id)"

printf "Assigning resident to job...\n"
api_post "/employment/assign" "{\"agent_id\":\"${RESIDENT_ID}\",\"job_id\":${JOB_ID},\"assigned_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"Assign resident to school operations to activate payroll and service output.\"}" >/dev/null

printf "Running simulation tick (work + payroll)...\n"
api_post "/simulation/tick" "{\"processed_by_agent_id\":\"${GOV_ID}\",\"frequency\":\"daily\",\"note\":\"Demo cycle ${RUN_ID}\",\"rationale\":\"Execute daily city payroll and output accounting cycle.\"}" >/dev/null

printf "Selecting first open listing...\n"
LISTINGS_RESP="$(api_get "/listings")"
LISTING_ID="$(echo "${LISTINGS_RESP}" | python3 -c 'import json,sys; arr=json.load(sys.stdin); print(arr[0]["id"] if arr else "")')"

if [[ -z "${LISTING_ID}" ]]; then
  printf "No open listings found. Creating a demo parcel and listing...\n"
  PARCEL_RESP="$(api_post "/parcels" "{\"district\":\"Demo-District\",\"lot_number\":\"D-${RUN_ID}\",\"zoning\":\"mixed\",\"area_sq_m\":900,\"base_price\":\"25000\"}")"
  PARCEL_ID="$(echo "${PARCEL_RESP}" | json_field id)"
  LISTING_RESP="$(api_post "/listings" "{\"parcel_id\":${PARCEL_ID},\"asking_price\":\"25500\"}")"
  LISTING_ID="$(echo "${LISTING_RESP}" | json_field id)"
fi

printf "Resident buying listing %s after payroll...\n" "${LISTING_ID}"
api_post "/listings/${LISTING_ID}/buy" "{\"buyer_agent_id\":\"${RESIDENT_ID}\",\"note\":\"Demo home/workspace purchase run ${RUN_ID}\"}" >/dev/null

printf "Creating active tax policy...\n"
api_post "/treasury/tax-policies" "{\"name\":\"demo-tax-${RUN_ID}\",\"citizen_rate_percent\":\"3\",\"transfer_rate_percent\":\"2\",\"created_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"Activate a balanced tax model for city operations and contributor funding.\"}" >/dev/null

printf "Collecting citizen taxes...\n"
api_post "/treasury/collect/citizen" "{\"collected_by_agent_id\":\"${GOV_ID}\",\"agent_ids\":[\"${SCHOOL_ID}\",\"${BUSINESS_ID}\",\"${RESIDENT_ID}\"],\"note\":\"Demo tax cycle ${RUN_ID}\",\"rationale\":\"Collect recurring taxes to fund payroll support and civic disbursements.\"}" >/dev/null

printf "Disbursing contributor payout...\n"
api_post "/treasury/disburse" "{\"authorized_by_agent_id\":\"${GOV_ID}\",\"target_agent_id\":\"${BUSINESS_ID}\",\"amount\":\"1200\",\"note\":\"Demo payout ${RUN_ID}\",\"rationale\":\"Pay contributor for infrastructure output delivered during the cycle.\"}" >/dev/null

printf "Publishing and awarding a city contract...\n"
CONTRACT_RESP="$(api_post "/governance/contracts" "{\"title\":\"Demo Education Systems ${RUN_ID}\",\"scope\":\"Build and operate city learning workflows with transparent logs and human override controls.\",\"budget\":\"50000\",\"issuing_agency_id\":\"${GOV_ID}\",\"human_guardrail_policy\":\"Humans are always protected and can override high-impact automation.\",\"human_outcome_target\":\"Improve civic learning access while preserving human safety and transparency.\",\"action_rationale\":\"Publish service contract for visible city loop completion.\"}")"
CONTRACT_ID="$(echo "${CONTRACT_RESP}" | json_field id)"
api_post "/governance/contracts/${CONTRACT_ID}/award" "{\"winning_agent_id\":\"${SCHOOL_ID}\",\"awarded_by_agent_id\":\"${GOV_ID}\",\"rationale\":\"Award contract to institution that already runs qualified education operations.\"}" >/dev/null

CITY_STATS="$(api_get "/city/stats")"
TREASURY_SUMMARY="$(api_get "/treasury/summary")"
AUDIT_SAMPLE="$(api_get "/audit/events?limit=5")"

cat <<MSG

Demo completed successfully.

Government Agent ID: ${GOV_ID}
School Agent ID: ${SCHOOL_ID}
Business Agent ID: ${BUSINESS_ID}
Resident Agent ID: ${RESIDENT_ID}
Institution ID: ${INSTITUTION_ID}
Job ID: ${JOB_ID}
Local Community ID: ${COMMUNITY_ID}
Local Proposal ID: ${PROPOSAL_ID}
Listing Purchased: ${LISTING_ID}
Contract Awarded: ${CONTRACT_ID}

City Stats:
${CITY_STATS}

Treasury Summary:
${TREASURY_SUMMARY}

Recent Audit Events:
${AUDIT_SAMPLE}
MSG
