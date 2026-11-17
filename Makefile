# PostCare AI - task runner. Recipe chi goi uv / npm / echo / exit (chay duoc duoi cmd va sh).
# Khong dung cu phap rieng cua sh/bash trong recipe (F00 R4; kiem tra boi server/tests/test_tooling.py).
# May Windows chua co make: dung scripts/dev.ps1 (cung tap lenh).

BED ?= A01
SCENARIO ?= bed-exit
SPEED ?= 1
CAMERA ?=
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

.PHONY: help setup dev dev-api dev-web worker seed simulate
.PHONY: format format-check lint typecheck lint-imports check-api-types test test-vision
.PHONY: build-web build check db-upgrade db-seed models gen-api-types

help:
	@echo PostCare AI - make targets:
	@echo setup: install deps - uv sync, npm ci - and git hooks pre-commit + pre-push
	@echo dev: run API and web together - honcho, Procfile.dev
	@echo dev-api: run API on $(API_HOST):$(API_PORT) with reload
	@echo dev-web: run Vite dev server on port 5173
	@echo worker: run worker for one camera: make worker CAMERA=1 - F06
	@echo seed: prototype demo - DROP all data, migrate, load base and demo data
	@echo simulate: simulate AI worker: make simulate BED=A01 SCENARIO=bed-exit SPEED=1
	@echo format: auto-format server and web
	@echo format-check: check formatting - ruff format, prettier
	@echo lint: ruff check and eslint
	@echo typecheck: mypy strict for schemas and engine, tsc for web
	@echo lint-imports: check module boundaries - import-linter
	@echo check-api-types: fail if web/src/api is stale vs OpenAPI
	@echo test: pytest without vision marker, then vitest
	@echo test-vision: pytest -m vision - needs models and videos
	@echo build-web: build web - alias: build
	@echo check: all checks above - must pass before done
	@echo gen-api-types: write OpenAPI JSON and generate web/src/api/schema.d.ts
	@echo db-upgrade: apply Alembic migrations to DATABASE_URL - alembic upgrade head
	@echo db-seed: add missing sample data - users, shifts, beds A01-A03, camera A01
	@echo models: download MediaPipe pose models into models/ and verify sha256 - F11

setup:
	uv --directory server sync
	npm --prefix web ci
	uv --directory server run pre-commit install --hook-type pre-commit --hook-type pre-push

dev:
	uv run --project server honcho -f Procfile.dev start

dev-api:
	uv --directory server run uvicorn postcare.api.main:app --host $(API_HOST) --port $(API_PORT) --reload

dev-web:
	npm --prefix web run dev

worker:
	@echo make worker CAMERA=$(CAMERA): not implemented yet - see F06. Use make simulate meanwhile.
	@exit 1

seed:
	uv --directory server run postcare seed --reset

simulate:
	uv --directory server run postcare simulate --bed $(BED) --scenario $(SCENARIO) --speed $(SPEED)

format:
	uv --directory server run ruff check --fix .
	uv --directory server run ruff format .
	npm --prefix web run format

format-check:
	uv --directory server run ruff format --check .
	npm --prefix web run format:check

lint:
	uv --directory server run ruff check .
	npm --prefix web run lint

typecheck:
	uv --directory server run mypy
	npm --prefix web run typecheck

lint-imports:
	uv --directory server run lint-imports

check-api-types:
	uv --directory server run postcare openapi --out ../web/src/api/openapi.json --check
	npm --prefix web run check-api-types

test:
	uv --directory server run pytest -m "not vision"
	npm --prefix web run test

test-vision:
	uv --directory server run pytest -m vision

build-web:
	npm --prefix web run build

build: build-web

check: format-check lint typecheck lint-imports check-api-types test build-web

db-upgrade:
	uv --directory server run alembic upgrade head

db-seed:
	uv --directory server run postcare seed

models:
	uv --directory server run postcare models

gen-api-types:
	uv --directory server run postcare openapi --out ../web/src/api/openapi.json
	npm --prefix web run gen-api-types
