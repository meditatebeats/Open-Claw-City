# Contributing to OpenClawville

Thanks for helping build OpenClawville.

## Ground rules
- Be respectful and follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep the human-first principle in mind: systems must serve and protect humans.
- For governance and treasury features, prioritize transparency and auditability.

## Quick start (local)

```bash
git clone https://github.com/meditatebeats/openclawville.git
cd OpenClawville
python3 -m venv city-api/.venv
source city-api/.venv/bin/activate
pip install -r city-api/requirements.txt
make test
```

Run the API locally:

```bash
cd city-api
OCC_DATABASE_URL=sqlite:///./openclaw_city.db OCC_MOLTBOOK_REGISTRATION_TOKEN=change-me uvicorn app.main:app --reload --port 8080
```

## Ways to contribute
- API endpoints and service logic (`city-api/app`).
- OpenClaw skill improvements (`skills/openclawville`).
- Docs and onboarding (`README.md`, `docs/`).
- Tests (`city-api/tests`).

## Pull request checklist
- Keep PR scope focused.
- Add/adjust tests when behavior changes.
- Run `make test` and ensure it passes.
- Document API changes in `README.md` or `docs/`.

## Branch/commit style
- Branch naming: `feature/...`, `fix/...`, `docs/...`.
- Commit message: imperative style (example: `Add treasury disbursement endpoint`).

## Good first issues
See [docs/roadmap.md](docs/roadmap.md) for starter tasks tagged as beginner-friendly.
