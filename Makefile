.PHONY: city-up city-down city-seed test vm-up vm-destroy

city-up:
	docker compose up -d --build

city-down:
	docker compose down

city-seed:
	./scripts/seed-city.sh

test:
	cd city-api && OCC_DATABASE_URL=sqlite:///./test_openclaw_city.db OCC_MOLTBOOK_REGISTRATION_TOKEN=test-token pytest

vm-up:
	./infra/multipass/create-vm.sh

vm-destroy:
	./infra/multipass/destroy-vm.sh
