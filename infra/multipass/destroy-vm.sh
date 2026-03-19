#!/usr/bin/env bash
set -euo pipefail

VM_NAME="${VM_NAME:-openclaw-city}"

if ! command -v multipass >/dev/null 2>&1; then
  echo "Multipass is not installed."
  exit 1
fi

if multipass info "${VM_NAME}" >/dev/null 2>&1; then
  multipass stop "${VM_NAME}" || true
  multipass delete "${VM_NAME}"
  multipass purge
  echo "Destroyed ${VM_NAME}."
else
  echo "VM ${VM_NAME} does not exist."
fi
