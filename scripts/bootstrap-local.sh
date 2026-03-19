#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}/city-api"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f "${PROJECT_ROOT}/.env" ]; then
  cat > "${PROJECT_ROOT}/.env" <<EOF
OCC_DATABASE_URL=sqlite:///./openclaw_city.db
OCC_MOLTBOOK_REGISTRATION_TOKEN=change-me
OCC_ENROLLMENT_MODE=token_required
EOF
fi

OCC_DATABASE_URL="${OCC_DATABASE_URL:-sqlite:///./openclaw_city.db}" python -m app.seed

cat <<MSG

Local bootstrap complete.
- Start API: make run
- Run demo loop: make demo

MSG
