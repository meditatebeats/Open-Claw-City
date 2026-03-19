#!/usr/bin/env bash
set -euo pipefail

echo "scripts/install-openclaw-skill.sh is deprecated; using install-openclawville-skill.sh"
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install-openclawville-skill.sh"
