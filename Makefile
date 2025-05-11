.PHONY: init install format lint test run build update clean

init:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	$(MAKE) install

install:
	uv pip install -e ".[dev]"
	uv run pre-commit install

format:
	uv run ruff format .

lint:
	uv run ruff check . --fix
	uv run mypy .

test:
	uv run pytest -v --cov=app --cov-report=term-missing

run:
	uv run uvicorn app.main:app --reload

build:
	docker build -t rag-eval .

update:
	uv pip install -e ".[dev]"

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache .coverage .coverage.*
	rm -rf dist build
	rm -rf *.egg-info
