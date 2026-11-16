# PostCare AI - prototype đề xuất. Recipe chỉ gọi uv / npm (chạy được dưới cmd và sh).
# Windows không có make: dùng scripts/dev.ps1 hoặc các lệnh tương đương trong README.md.

BED ?= A01
SCENARIO ?= bed-exit
SPEED ?= 1
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

.PHONY: setup dev-api dev-web seed simulate test lint format format-check typecheck build gen-api-types check

setup:
	uv --directory server sync
	npm --prefix web ci

dev-api:
	uv --directory server run uvicorn postcare.api.main:app --host $(API_HOST) --port $(API_PORT) --reload

dev-web:
	npm --prefix web run dev

seed:
	uv --directory server run postcare seed

simulate:
	uv --directory server run postcare simulate --bed $(BED) --scenario $(SCENARIO) --speed $(SPEED)

test:
	uv --directory server run pytest
	npm --prefix web run test

lint:
	uv --directory server run ruff check .
	npm --prefix web run lint

format:
	uv --directory server run ruff check --fix .
	uv --directory server run ruff format .
	npm --prefix web run format

format-check:
	uv --directory server run ruff format --check .
	npm --prefix web run format:check

typecheck:
	npm --prefix web run typecheck

build:
	npm --prefix web run build

gen-api-types:
	uv --directory server run postcare openapi --out ../web/src/api/openapi.json
	npm --prefix web run gen-api-types

check: format-check lint typecheck test build
