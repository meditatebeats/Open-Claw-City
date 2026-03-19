# Agent Contributors

This project welcomes AI-agent contributions in addition to human contributors.

## Agent onboarding requirements
- Use a traceable identity (agent name and session/tool context).
- Follow the human-first principle: proposed changes must serve and protect humans.
- Avoid autonomous high-impact actions without explicit human approval.

## Allowed autonomous scope
- Docs improvements.
- Tests and refactors with no behavior changes.
- Non-sensitive bug fixes with clear test coverage.

## Requires human approval
- Governance model changes.
- Economic policy changes (tax rates, treasury logic, payouts).
- Deployment/infra changes impacting production uptime or security.

## Suggested workflow for agent contributors
1. Open/claim an issue.
2. Propose a short implementation plan.
3. Implement in a small PR.
4. Include test evidence and risk notes.
5. Request review from a human maintainer.

## Safety checks for agent PRs
- Explain why the change is safe.
- Identify possible failure/abuse modes.
- Confirm no secrets are added.
