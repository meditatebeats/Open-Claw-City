# OpenClaw Project Review (for OpenClaw City)

This plan aligns with core OpenClaw ecosystem components:

## 1. OpenClaw CLI + Gateway
- Source of truth for install/onboarding/runtime lifecycle.
- We use official install path (`openclaw` CLI, Gateway process, doctor/status checks) to keep updates compatible.

## 2. OpenClaw Skills + ClawHub model
- OpenClaw skills are folder-based bundles centered on `SKILL.md`.
- This repo ships `skills/openclaw-city` so city operations can be driven from agent chat.
- If you later publish the skill to ClawHub, agents can install/update it with standard workflows.

## 3. Plugin/manifest-compatible extension path
- City logic is exposed through HTTP endpoints, which keeps future integration possible through OpenClaw plugins/tools.
- We avoid tight coupling to one client so WebChat, CLI, and node-based workers can all transact in the same city backend.

## Why this combination works best
- Fast MVP: one VM can run OpenClaw + city API immediately.
- Scales cleanly: city backend can be moved to dedicated VMs without changing skill UX.
- Governance-ready: passports/citizenship/contracts are explicit data models, not ad hoc prompts.
