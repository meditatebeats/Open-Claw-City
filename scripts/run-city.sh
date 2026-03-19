#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
docker compose up -d --build

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

"${SCRIPT_DIR}/seed-city.sh"

echo "OpenClawville is live at http://127.0.0.1:8080"
