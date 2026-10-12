# Makefile — shortcuts for machines with make. Without make, run the
# same `uv run ...` commands from backend/ directly; no venv activation needed.

.PHONY: lint format typecheck test check

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .

typecheck:
	cd backend && uv run pyright

test:
	cd backend && uv run pytest

check: lint typecheck test
