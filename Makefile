# Basic commands of the project. Run `make help` to list them.
# Every command uses the versions pinned in uv.lock (--frozen: never re-resolve silently).

.DEFAULT_GOAL := help
SHELL := /bin/bash
UV := uv run --frozen

SERVE_IMAGE ?= credit-risk:serve
TRAIN_IMAGE ?= credit-risk:train
# Extra flags for `docker build`, e.g. on a machine behind a TLS-inspecting proxy:
#   DOCKER_BUILD_FLAGS="--network host --secret id=extra_ca,src=/path/to/ca.pem"
DOCKER_BUILD_FLAGS ?=
# Loads .env into the environment of a recipe line (the Python settings read it from there).
LOAD_ENV := set -a && . ./.env && set +a

.PHONY: help install lint format test build test-image up down test-integration clean audit check data publish test-data migrate ingest snapshot diff-cover notebooks train advance replay rollback

help: ## List the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install: ## Create the environment from uv.lock, install the git hooks and create .env if missing
	uv sync --frozen --all-groups
	$(UV) pre-commit install
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example (local development values)"; fi

lint: ## Check style, formatting, types and that uv.lock matches pyproject.toml
	uv lock --check
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) mypy

format: ## Fix what can be fixed automatically (lint fixes and formatting)
	$(UV) ruff check --fix .
	$(UV) ruff format .

test: ## Run the unit tests with branch coverage (no Docker needed)
	$(UV) pytest tests/unit --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=0

SOURCE := data/raw/accepted_2007_to_2018Q4.csv.gz
# Schema migrations (D-048): dbmate from its official image, pinned by version and digest.
DBMATE_IMAGE := amacneil/dbmate:2.38.2@sha256:fb4fe7cabfe98cf864d63ce083867f3c303a8c1a022fcd69081439425706e909
# The URL travels as an environment variable, never on the command line (no password in `ps`).
DATABASE_URL = postgres://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@127.0.0.1:$${POSTGRES_PORT:-5432}/$${POSTGRES_DB}?sslmode=disable

data: ## Download the Lending Club file from Kaggle if missing (needs KAGGLE_API_TOKEN); its hash is checked on use
	@if [ ! -f $(SOURCE) ]; then mkdir -p data/raw && $(UV) kaggle datasets download wordsforthewise/lending-club -f accepted_2007_to_2018Q4.csv.gz -p data/raw; fi

publish: data ## Simulator: publish every monthly delivery up to PERIOD (YYYY-MM) into data/landing
	@test -n "$(PERIOD)" || { echo "usage: make publish PERIOD=YYYY-MM"; exit 1; }
	$(UV) python -m credit_risk.simulator --until $(PERIOD)

migrate: up ## Apply the pending schema migrations (db/migrations) to the database in .env
	$(LOAD_ENV) && DATABASE_URL="$(DATABASE_URL)" docker run --rm --network host -e DATABASE_URL \
		-v "$(CURDIR)/db:/db:ro" $(DBMATE_IMAGE) --migrations-dir /db/migrations --no-dump-schema up

ingest: migrate ## Load the deliveries of PERIOD (YYYY-MM) into raw and clean (run 'make publish' first)
	@test -n "$(PERIOD)" || { echo "usage: make ingest PERIOD=YYYY-MM"; exit 1; }
	$(LOAD_ENV) && $(UV) python -m credit_risk.ingest load $(PERIOD)

snapshot: migrate ## Build the training set version at T (YYYY-MM) from clean (D-058); prints its hash
	@test -n "$(T)" || { echo "usage: make snapshot T=YYYY-MM"; exit 1; }
	$(LOAD_ENV) && $(UV) python -m credit_risk.snapshot build $(T)

train: up ## Train, register and try to promote the PD and LGD models on the training set version at T (YYYY-MM)
	@test -n "$(T)" || { echo "usage: make train T=YYYY-MM"; exit 1; }
	$(LOAD_ENV) && $(UV) python -m credit_risk.pipeline $(T)

advance: data migrate ## Simulated clock: publish the next month and run the monthly flow for it (D-107)
	$(LOAD_ENV) && $(UV) prefect deployment run advance/advance --watch

replay: data migrate ## Simulated clock: advance month by month until TO (YYYY-MM), e.g. make replay TO=2014-12
	@test -n "$(TO)" || { echo "usage: make replay TO=YYYY-MM"; exit 1; }
	$(LOAD_ENV) && $(UV) prefect deployment run replay/replay --param until=$(TO) --watch

rollback: up ## Put back the champion before the current one of MODEL (pd or lgd) (D-090)
	@test -n "$(MODEL)" || { echo "usage: make rollback MODEL=pd|lgd"; exit 1; }
	$(LOAD_ENV) && $(UV) python -m credit_risk.registry rollback $(MODEL)

test-data: data ## Run the tests that need the real data file (not in CI)
	$(UV) pytest -m data

notebooks: ## Run the audit notebook top to bottom; fails if its outputs differ from the committed ones (D-065)
	$(UV) --group notebooks jupyter nbconvert --to notebook --execute --inplace notebooks/00_data_audit.ipynb
	git diff --exit-code --stat -- reports/data_audit ':(exclude)*.png'

build: ## Build the two application images, serve and train (D-078)
	docker build $(DOCKER_BUILD_FLAGS) --target serve -t $(SERVE_IMAGE) .
	docker build $(DOCKER_BUILD_FLAGS) --target train --build-arg CREDIT_RISK_COMMIT=$$(git rev-parse HEAD) -t $(TRAIN_IMAGE) .

test-image: ## Run the unit tests inside an image with the package installed as in production
	docker build $(DOCKER_BUILD_FLAGS) --target test -t credit-risk:test .
	docker run --rm credit-risk:test

up: ## Start the services (Postgres, MLflow, Prefect, its worker and the clock) and wait until they are healthy (run 'make build' first)
	@test -f .env || { echo ".env missing: run 'make install' or copy .env.example"; exit 1; }
	docker compose up -d --wait

down: ## Stop the services; the data stays in the volume (use 'docker compose down -v' to wipe it)
	docker compose down

test-integration: up ## Tests that need Docker (run 'make build' first), destructive last; coverage of unit + integration at least 85% (D-064)
	$(UV) coverage erase
	$(UV) pytest tests/unit --cov --cov-report= --cov-fail-under=0
	$(LOAD_ENV) && SERVE_IMAGE=$(SERVE_IMAGE) TRAIN_IMAGE=$(TRAIN_IMAGE) $(UV) pytest -m "integration and not destructive" --cov --cov-append --cov-report=xml --cov-fail-under=0
	$(LOAD_ENV) && $(UV) pytest -m destructive
	$(UV) coverage report

diff-cover: ## At least 90% of the lines changed against origin/main are covered (D-064; run after test-integration)
	$(UV) diff-cover coverage.xml --compare-branch=origin/main --fail-under=90

clean: ## Remove caches and build outputs
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage coverage.xml htmlcov build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

audit: ## Check every locked dependency (all groups) against known vulnerabilities
	uv export --frozen --all-groups --no-emit-project --format requirements-txt > .audit-requirements.txt
	$(UV) pip-audit --strict --disable-pip --require-hashes -r .audit-requirements.txt; status=$$?; rm -f .audit-requirements.txt; exit $$status

check: lint test build test-image test-integration diff-cover ## Everything CI runs on a pull request, in one command
