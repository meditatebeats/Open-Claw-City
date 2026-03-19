#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  jq \
  python3 \
  python3-pip \
  python3-venv \
  docker.io \
  docker-compose-v2

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt-get install -y nodejs
else
  NODE_MAJOR="$(node -v | tr -d 'v' | cut -d. -f1)"
  if [ "${NODE_MAJOR}" -lt 22 ]; then
    curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
    sudo apt-get install -y nodejs
  fi
fi

if ! command -v openclaw >/dev/null 2>&1; then
  sudo npm install -g openclaw@latest
fi

sudo usermod -aG docker "${USER}" || true

cd "${PROJECT_ROOT}/city-api"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cat <<MSG
Bootstrap complete.

Next steps inside the VM:
1. openclaw setup
2. openclaw channels login
3. openclaw gateway
4. cd ${PROJECT_ROOT} && ./scripts/run-city.sh
5. ./scripts/install-openclaw-skill.sh

Note: if Docker group access fails, run: newgrp docker
MSG
