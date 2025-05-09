.PHONY: install format lint test run build

install:
	python -m uv pip install -e ".[dev]"
	pre-commit install

format:
	ruff check . --fix
	ruff format .

lint:
	ruff check .
	mypy .

test:
	pytest -v --cov=app --cov-report=term-missing

run:
	uvicorn app.main:app --reload

build:
	docker build -t rag-eval .