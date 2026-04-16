# Makefile

.PHONY: lint format typecheck test

lint:
	cd backend && ruff check app/

format:
	cd backend && ruff format app/

typecheck:
	cd backend && mypy app/

test:
	cd backend && pytest

check: lint typecheck test
