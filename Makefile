PYTHON ?= .venv/bin/python

.PHONY: install test lint typecheck check format run migrate docker-up docker-down

install:
	uv sync --locked --extra dev

test:
	$(PYTHON) -m pytest --cov=archguard --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy src

check: lint typecheck test

format:
	$(PYTHON) -m ruff format .

run:
	$(PYTHON) -m uvicorn archguard.api.app:create_app --factory --reload --host 127.0.0.1

migrate:
	$(PYTHON) -m alembic upgrade head

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
