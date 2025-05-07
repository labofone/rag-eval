# Progress

This document tracks the buildDataset feature's progress, including what works, what's left to build, the current status, known issues, and the evolution of project decisions.

## Current Status

The initial code structure for the `buildDataset` feature has been created, including the LangGraph pipeline definition and basic unit tests. The core components for data fetching, ranking, processing, and storage are outlined with placeholder logic.

## What Works

- Created the `app/build_dataset/` directory and the following initial files:
  - `__init__.py`: Marks the directory as a Python package.
  - `main.py`: Contains the entry point `run_build_dataset_pipeline` to invoke the LangGraph, with basic logging and `.env` loading logic.
  - `config.py`: Defines `BuildDatasetSettings` using `pydantic-settings` to load configuration (SerpAPI key, GCS bucket, MCP URL, etc.) from a root `.env` file.
  - `schemas.py`: Defines Pydantic models (`InitialSearchResult`, `FullContentData`, `ProcessedContent`) for data structures used in the pipeline.
  - `tools.py`: Contains placeholder functions/wrappers for `search_academic_papers_serpapi`, `download_pdf_async`, and `fetch_webpage_content_playwright_mcp`. Includes basic error handling and logging.
  - `processors.py`: Contains placeholder functions for `calculate_weighted_quality_score` (weighted average logic outlined) and `process_raw_content_with_markitdown` (MarkItDown integration placeholder).
  - `storage.py`: Contains placeholder functions for `upload_to_gcs` and `store_processed_content` (GCS interaction outlined).
  - `graph.py`: Defines the `GraphState` and the sequential LangGraph workflow with nodes corresponding to the 5 pipeline steps (fetch initial, rank, fetch full, process, store).
- Created the test file `tests/test_build_dataset.py` with initial unit tests covering:
  - Schema validation.
  - Basic functionality of processors (ranking logic with mocked scoring, processing placeholder with mocked converter).
  - Basic functionality of tools (SerpAPI, PDF download, MCP wrapper) using mocking.
  - Basic LangGraph flow using mocked nodes.
- Committed the initial code files (`app/build_dataset/`) and the initial test file (`tests/test_build_dataset.py`) in separate commits following the version control guidelines, including referencing issue #10 in commit messages.

## What's Left to Build

- **Configuration**: The `.env` file in the project root needs to be created by the user with actual values for `SERPAPI_API_KEY`, `GCS_BUCKET_NAME`, and optionally `PLAYWRIGHT_MCP_URL`.
- **Dependencies**: The necessary Python packages (`serpapi`, `google-cloud-storage`, `python-dotenv`, `langchain`, `langgraph`, `httpx`, `pydantic-settings`, and potentially PDF reading/MarkItDown libraries) need to be installed.
- **Tool Implementation**:
  - Full implementation of `download_pdf_async` to extract text content from downloaded PDFs (requires a PDF parsing library).
  - Full integration with MarkItDown in `process_raw_content_with_markitdown`.
  - Setup and configuration of the Playwright MCP server if needed for web scraping.
- **Processor Refinement**: Refine the `calculate_weighted_quality_score` logic based on the actual structure of SerpAPI results and desired ranking criteria.
- **Comprehensive Tests**: Add more detailed and comprehensive tests, especially for error handling, edge cases, and integration points between components.
- **Error Handling and Retries**: Implement more robust error handling and retry logic within the LangGraph nodes.
- **Logging**: Enhance logging throughout the pipeline for better monitoring and debugging.
- **Integration with Main App**: Integrate the `run_build_dataset_pipeline` function into the main application workflow (e.g., via a CLI command or an internal API endpoint).

## Known Issues

- None at this time.

## Evolution of Project Decisions

- Decided to use LangGraph for pipeline orchestration due to its control over stateful workflows.
- Confirmed the 5-step pipeline structure: fetch initial -> rank -> fetch full -> process -> store.
- Confirmed loading sensitive configuration from a root `.env` file.
- Adopted separate commits for code and tests as per version control guidelines.
