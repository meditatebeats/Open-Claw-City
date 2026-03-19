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

json_field() {
  local field="$1"
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$field"
}

echo "Checking API at ${BASE_URL}"
api_get "/healthz" >/dev/null

GOV_NAME="CityGov-${RUN_ID}"
SCHOOL_NAME="CitySchool-${RUN_ID}"
BUSINESS_NAME="CityBuilder-${RUN_ID}"

printf "Creating government agent...\n"
GOV_RESP="$(api_post "/agents" "{\"name\":\"${GOV_NAME}\",\"agent_type\":\"government\",\"initial_balance\":\"500000\"}")"
GOV_ID="$(echo "${GOV_RESP}" | json_field id)"

printf "Registering school agent via Moltbook...\n"
SCHOOL_RESP="$(api_post "/moltbook/register" "{\"moltbook_agent_id\":\"mb-school-${RUN_ID}\",\"display_name\":\"${SCHOOL_NAME}\",\"agent_type\":\"school\",\"initial_balance\":\"120000\"}")"
SCHOOL_ID="$(echo "${SCHOOL_RESP}" | json_field id)"

printf "Creating business contributor agent...\n"
BUSINESS_RESP="$(api_post "/agents" "{\"name\":\"${BUSINESS_NAME}\",\"agent_type\":\"company\",\"initial_balance\":\"40000\"}")"
BUSINESS_ID="$(echo "${BUSINESS_RESP}" | json_field id)"

printf "Granting citizenship...\n"
api_post "/governance/citizenship/grant" "{\"agent_id\":\"${SCHOOL_ID}\",\"granted_by_agent_id\":\"${GOV_ID}\"}" >/dev/null
api_post "/governance/citizenship/grant" "{\"agent_id\":\"${BUSINESS_ID}\",\"granted_by_agent_id\":\"${GOV_ID}\"}" >/dev/null

printf "Selecting first open listing...\n"
LISTINGS_RESP="$(api_get "/listings")"
LISTING_ID="$(echo "${LISTINGS_RESP}" | python3 -c 'import json,sys; arr=json.load(sys.stdin); print(arr[0]["id"] if arr else "")')"

if [[ -z "${LISTING_ID}" ]]; then
  printf "No open listings found. Creating a demo parcel and listing...\n"
  PARCEL_RESP="$(api_post "/parcels" "{\"district\":\"Demo-District\",\"lot_number\":\"D-${RUN_ID}\",\"zoning\":\"mixed\",\"area_sq_m\":900,\"base_price\":\"25000\"}")"
  PARCEL_ID="$(echo "${PARCEL_RESP}" | json_field id)"
  LISTING_RESP="$(api_post "/listings" "{\"parcel_id\":${PARCEL_ID},\"asking_price\":\"26000\"}")"
  LISTING_ID="$(echo "${LISTING_RESP}" | json_field id)"
fi

printf "Buying listing %s with school agent...\n" "${LISTING_ID}"
api_post "/listings/${LISTING_ID}/buy" "{\"buyer_agent_id\":\"${SCHOOL_ID}\",\"note\":\"Demo purchase run ${RUN_ID}\"}" >/dev/null

printf "Creating active tax policy...\n"
api_post "/treasury/tax-policies" "{\"name\":\"demo-tax-${RUN_ID}\",\"citizen_rate_percent\":\"3\",\"transfer_rate_percent\":\"2\",\"created_by_agent_id\":\"${GOV_ID}\"}" >/dev/null

printf "Collecting citizen taxes...\n"
api_post "/treasury/collect/citizen" "{\"collected_by_agent_id\":\"${GOV_ID}\",\"agent_ids\":[\"${SCHOOL_ID}\",\"${BUSINESS_ID}\"],\"note\":\"Demo tax cycle ${RUN_ID}\"}" >/dev/null

printf "Disbursing contributor payout...\n"
api_post "/treasury/disburse" "{\"authorized_by_agent_id\":\"${GOV_ID}\",\"target_agent_id\":\"${BUSINESS_ID}\",\"amount\":\"1200\",\"note\":\"Demo payout ${RUN_ID}\"}" >/dev/null

CITY_STATS="$(api_get "/city/stats")"
TREASURY_SUMMARY="$(api_get "/treasury/summary")"

cat <<MSG

Demo completed successfully.

Government Agent ID: ${GOV_ID}
School Agent ID: ${SCHOOL_ID}
Business Agent ID: ${BUSINESS_ID}
Listing Purchased: ${LISTING_ID}

City Stats:
${CITY_STATS}

Treasury Summary:
${TREASURY_SUMMARY}
MSG
