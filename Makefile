.PHONY: up down logs migrate revision seed test-api test-web e2e

up:         ## Build and start db, api, web
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f api web
migrate:
	docker compose exec api alembic upgrade head
revision:   ## make revision m="add businesses"
	docker compose exec api alembic revision --autogenerate -m "$(m)"
seed:
	docker compose exec api python -m app.seed
test-api:   ## Pytest incl. PostGIS integration tests
	docker compose exec api pytest -q
test-web:
	cd frontend && npm run lint && npm run typecheck
e2e:
	cd frontend && npx playwright test
