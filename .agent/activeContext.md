# Active Context

This document tracks the current work focus, recent changes, next steps, active decisions, important patterns, and learnings.

## Current Work Focus

Integrating Ragas evaluation metrics and implementing asynchronous task processing with Celery and Redis.

## Recent Changes

- Created `app/celery.py` for Celery configuration.
- Created `app/tasks/evaluation.py` for Ragas evaluation tasks.
- Created `app/routers/evaluate.py` and `app/routers/result.py` for the evaluation and result endpoints.
- Created `app/config/settings.py` for application settings, including the API key.
- Updated `app/main.py` to include the new routers and use the authentication from `app/dependencies.py`.
- Moved API key validation logic to `app/dependencies.py`.
- Modified `app/config/settings.py` to load the API key from environment variables for enhanced security.
- Implemented Redis result storage and retrieval for evaluation tasks.

## Next Steps

- Add more comprehensive tests for all endpoints and functionality.

## Active Decisions and Considerations

- metrics selection for different evaluation scenarios: the selection should be agentic, supporting natural language queries that mix different choice criteria.
- How to best structure the asynchronous evaluation tasks.
- how to optimize the batch processing.
- Securely storing and managing API keys.
- Determining appropriate expiration times for cached results in Redis.
- Ensuring comprehensive test coverage for new and existing features.

## Important Patterns and Preferences
