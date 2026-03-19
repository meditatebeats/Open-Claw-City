#!/usr/bin/env bash
set -euo pipefail

VM_NAME="${VM_NAME:-openclawville}"
CPUS="${CPUS:-4}"
MEMORY="${MEMORY:-8G}"
DISK="${DISK:-40G}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLOUD_INIT_FILE="${PROJECT_ROOT}/infra/cloud-init/openclawville.yaml"

if ! command -v multipass >/dev/null 2>&1; then
  echo "Multipass is not installed. Install it from https://multipass.run/"
  exit 1
fi

if ! multipass info "${VM_NAME}" >/dev/null 2>&1; then
  multipass launch 24.04 \
    --name "${VM_NAME}" \
    --cpus "${CPUS}" \
    --memory "${MEMORY}" \
    --disk "${DISK}" \
    --cloud-init "${CLOUD_INIT_FILE}"
else
  echo "VM ${VM_NAME} already exists. Reusing it."
fi

if ! multipass info "${VM_NAME}" | grep -q '/opt/openclawville'; then
  multipass mount "${PROJECT_ROOT}" "${VM_NAME}:/opt/openclawville"
fi

multipass exec "${VM_NAME}" -- bash -lc "cd /opt/openclawville && ./scripts/bootstrap-vm.sh"

IP_ADDR="$(multipass info "${VM_NAME}" | awk '/IPv4/{print $2; exit}')"

echo "VM ready: ${VM_NAME} (${IP_ADDR})"
echo "Enter VM: multipass shell ${VM_NAME}"
