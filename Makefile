.PHONY: up up-all down test lint seed logs

up:
	docker compose --profile core up -d --build

up-all:
	docker compose --profile core --profile mlops --profile obs up -d --build

down:
	docker compose --profile core --profile mlops --profile obs down

test:
	cd aegis_ai && uv run pytest -v
	cd erp_core && uv run python manage.py test

lint:
	cd aegis_ai && uv run ruff check . && uv run ruff format --check .
	cd erp_core && uv run ruff check . && uv run ruff format --check .

seed:
	docker compose exec erp python manage.py seed_data

logs:
	docker compose logs -f --tail=100
