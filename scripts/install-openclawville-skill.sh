#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_SOURCE="${PROJECT_ROOT}/skills/openclawville"
WORKSPACE_SKILLS_DIR="${OPENCLAW_WORKSPACE_SKILLS_DIR:-${HOME}/.openclaw/workspace/skills}"
TARGET="${WORKSPACE_SKILLS_DIR}/openclawville"

mkdir -p "${WORKSPACE_SKILLS_DIR}"
ln -sfn "${SKILL_SOURCE}" "${TARGET}"

echo "Installed skill symlink: ${TARGET} -> ${SKILL_SOURCE}"
echo "Start a new OpenClaw session to load the skill."
