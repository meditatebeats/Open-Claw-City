.PHONY: bootstrap-local run seed-local city-up city-down city-seed test demo vm-up vm-destroy

bootstrap-local:
	./scripts/bootstrap-local.sh

run:
	cd city-api && \
	if [ -d .venv ]; then . .venv/bin/activate; fi && \
	OCC_DATABASE_URL=$${OCC_DATABASE_URL:-sqlite:///./openclaw_city.db} \
	OCC_MOLTBOOK_REGISTRATION_TOKEN=$${OCC_MOLTBOOK_REGISTRATION_TOKEN:-change-me} \
	OCC_ENROLLMENT_MODE=$${OCC_ENROLLMENT_MODE:-token_required} \
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

seed-local:
	cd city-api && \
	if [ -d .venv ]; then . .venv/bin/activate; fi && \
	OCC_DATABASE_URL=$${OCC_DATABASE_URL:-sqlite:///./openclaw_city.db} \
	python -m app.seed

city-up:
	docker compose up -d --build

city-down:
	docker compose down

city-seed:
	./scripts/seed-city.sh

test:
	cd city-api && OCC_DATABASE_URL=sqlite:///./test_openclaw_city.db OCC_MOLTBOOK_REGISTRATION_TOKEN=test-token pytest

demo:
	./scripts/demo.sh

vm-up:
	./infra/multipass/create-vm.sh

vm-destroy:
	./infra/multipass/destroy-vm.sh
