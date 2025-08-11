.PHONY: help install dev-install test coverage lint format type-check run clean docker-up docker-down

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -r requirements.txt

dev-install: ## Install development dependencies
	pip install -r requirements.txt
	pre-commit install

test: ## Run tests
	pytest

coverage: ## Run tests with coverage
	pytest --cov=app --cov-report=html --cov-report=term

lint: ## Run linter (ruff)
	ruff check app tests

format: ## Format code with black
	black app tests

type-check: ## Run type checking with mypy
	mypy app

run: ## Run the development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run Celery worker (Phase 2)
	celery -A app.workers.tasks worker --loglevel=info

flower: ## Run Flower for Celery monitoring (Phase 2)
	celery -A app.workers.tasks flower

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	rm -rf storage/uploads/* storage/converted/*
	touch storage/uploads/.gitkeep storage/converted/.gitkeep

docker-up: ## Start Docker services
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f

migrate: ## Run database migrations (Phase 2+)
	alembic upgrade head

migrate-create: ## Create a new migration (Phase 2+)
	alembic revision --autogenerate -m "$(message)"