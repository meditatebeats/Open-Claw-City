# Public Repo Guidance

A public repo is good for credibility and ecosystem adoption, but only if secrets stay out of Git.

## Safe to publish
- API/service code
- skill definitions (`SKILL.md`)
- deployment scripts
- architecture/policy docs

## Never publish
- OpenClaw auth/session files
- API keys, tokens, private signing keys
- production `.env` files
- database dumps with private data

## Required controls before pushing
1. Keep `.env` ignored and use `.env.example` only.
2. Rotate any token that was ever committed by mistake.
3. Add branch protection and required reviews.
4. Store production secrets in VM/cloud secret manager.

## For selling virtual real estate
Public code is usually a positive signal (trust + auditability). Scarcity and ownership should come from your live registry + transaction ledger, not from code secrecy.
