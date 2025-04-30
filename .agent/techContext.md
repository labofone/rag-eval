# Technical Context

This document details the technologies used, development setup, technical constraints, dependencies, and tool usage patterns for the project.

## Technologies and dependencies

- Python 3.12
- FastAPI
- Ragas
- Celery
- Redis
- Uvicorn
- pytest (dev)
- httpx (dev)

## Development Setup

- use **uv** for dependency, package, and virtual environment management.
- use **pytest** for testing.
- use **ruff** for linting.
- use **pydantic** for data validation.
- use **make** (when necessary) for high level commands.
- use **docker** for deployment.
- use **nox** (when necessary) for automation.
- use **built-in FastAPI docs features** for API endpoints and usage documentation .
- use **markdown files** (initially the root README.md) for project documentation.

## Technical Constraints

- Limited computational resources for LLM-based evaluation.
- Latency in external API calls for evaluation.
- Ensuring data security and privacy.

## Tool Usage Patterns

- `write_to_file`: Used to create new files (e.g., `main.py`, `requirements.txt`) and update existing ones.
- `replace_in_file`: Used to modify specific sections of existing files.
- `execute_command`: Used to run shell commands (e.g., creating and activating the virtual environment, installing dependencies).
