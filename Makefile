.PHONY: install test lint format check docker-build docker-up docker-down docker-logs

install:
	uv pip install -e ".[test]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

check: lint test
	@echo "✅ CI-Checks passed"

# --- Docker targets ---

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-up-celery:
	docker compose --profile celery up -d

docker-restart: docker-down docker-up

docker-clean:
	docker compose down -v --rmi local