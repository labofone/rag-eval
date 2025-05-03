# Progress

This document tracks the project's progress, including what works, what's left to build, the current status, known issues, and the evolution of project decisions.

## Current Status

The base FastAPI application is set up with authentication, integrated with Celery and Redis for asynchronous tasks, and includes endpoints for batch evaluation and result retrieval.

## What Works

- Implementation of API key authentication using `app/dependencies.py` and `app/config/settings.py`.
- Created `app/celery.py` for Celery configuration.
- Created `app/tasks/evaluation.py` for Ragas evaluation tasks.
- Created `app/routers/evaluate.py` and `app/routers/result.py` for the evaluation and result endpoints.
- Created `app/config/settings.py` for application settings, including the API key.
- Updated `app/main.py` to include the new routers and use the authentication from `app/dependencies.py`.
- Implemented data validation using pydantic for the `/evaluate/batch` endpoint.
- Added documentation for the `/evaluate/batch` and `/results/{task_id}` endpoints.
- Added `pytest` and `httpx` to the `dev` dependencies.
- Created initial test files (`tests/test_evaluate.py` and `tests/test_result.py`) with test cases for the `/evaluate/batch` and `/results/{task_id}` endpoints.
- Implemented Redis result storage and retrieval for evaluation tasks.
- Implemented agentic evaluation metric selection with a new /metrics/recommend endpoint.

## What's Left to Build

- Refine Ragas evaluation logic.
- Enhance security for API key management.
- Add more comprehensive tests for all endpoints and functionality, including the new /metrics/recommend endpoint.

## Known Issues

- None at this time.
- The API key should be read from environment variable.
