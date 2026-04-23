.PHONY: install test lint format check

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