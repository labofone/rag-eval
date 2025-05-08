# Progress

This document tracks the buildDataset feature's progress, including what works, what's left to build, the current status, known issues, and the evolution of project decisions.

## Current Status

The core logic for the `buildDataset` feature is implemented. The LangGraph pipeline now iterates internally through a predefined list of topics, fetches initial results via SerpAPI, ranks them using a score that includes relevance, recency, source authority, and citation count, fetches full content (PDFs or HTML), processes the content into Markdown using the Markitdown library, and stores the results in GCS. Basic error handling and logging are in place. The pipeline can be run using `uv run build-dataset`.

## What Works

- **Directory Structure**: `app/build_dataset/` created with necessary modules (`__init__.py`, `main.py`, `config.py`, `schemas.py`, `tools.py`, `processors.py`, `storage.py`, `graph.py`).
- **Configuration**: `config.py` defines `BuildDatasetSettings` loading from `.env`. `.env.example` file created.
- **Schemas**: Pydantic models (`InitialSearchResult`, `FullContentData`, `ProcessedContent`) defined in `schemas.py`, including fields for citation count and file path.
- **Tools**:
  - `search_academic_papers_serpapi`: Fetches results from SerpAPI.
  - `download_pdf_async`: Downloads PDFs and saves path.
  - `fetch_webpage_content`: Fetches HTML content via Playwright MCP (or other configured method).
- **Processors**:
  - `calculate_weighted_quality_score`: Calculates score based on relevance (keyword), recency, source authority, and citation count (log-scaled).
  - `rank_initial_results`: Ranks results based on the calculated score.
  - `convert_content_to_markdown`: Processes PDF (via path) or HTML (via raw text) using the `markitdown` library.
- **Storage**:
  - `upload_raw_artifact`: Uploads files to GCS (handles auth).
  - `store_processed_content`: Saves processed Markdown content to GCS using `upload_raw_artifact`.
- **Graph**:
  - `graph.py` defines an iterative LangGraph workflow (`GraphState`, nodes, conditional edge `should_continue`).
  - The graph processes a list of topics in a single invocation.
  - Nodes updated to use refactored function names and handle iterative state (current topic, accumulators).
  - Basic error aggregation implemented in graph state (`aggregated_errors`).
- **Entry Point**:
  - `main.py` defines a list of topics (`TOPICS_TO_PROCESS`).
  - `run_all_topics` function orchestrates loading `.env`, checking settings, and running the graph for the topic list via `asyncio.run`.
  - `pyproject.toml` includes `[project.scripts]` entry point `build-dataset = "app.build_dataset.main:run_all_topics"`.
- **Dependencies**: Required dependencies (`serpapi`, `google-cloud-storage`, `python-dotenv`, `langchain`, `langgraph`, `httpx`, `pydantic-settings`, `markitdown[pdf]`) added to `pyproject.toml` and installed.
- **Testing**: `tests/test_build_dataset.py` updated with tests for citation scoring, Markitdown mocking (HTML/PDF paths), and schema changes. Basic graph flow test included.
- **Commits**: Changes committed logically using `refactor`, `feat`, `docs` types.

## What's Left to Build

- **Processor Refinement**:
  - Improve `calculate_weighted_quality_score`: Implement semantic relevance scoring (e.g., using embeddings) instead of basic keyword matching.
  - Enhance metadata extraction in `convert_content_to_markdown` (e.g., authors, keywords) potentially using Markitdown features or LLMs.
- **Tool Implementation**:
  - Implement actual PDF text extraction within `download_pdf_async` or confirm `markitdown` handles it sufficiently (currently `markitdown` is assumed to handle the Path object).
  - Ensure `fetch_webpage_content` robustly handles potential Playwright MCP errors or alternative scraping methods.
- **Error Handling and Retries**: Implement more sophisticated error handling (e.g., conditional retries on transient errors like network issues) within the LangGraph nodes or via graph-level mechanisms.
- **Comprehensive Tests**: Add more detailed unit tests covering edge cases (e.g., various SerpAPI response structures, different PDF/HTML formats, GCS errors) and integration tests requiring actual `.env` setup and external service mocking/interaction.
- **Logging**: Potentially centralize logging configuration when integrating with the main FastAPI app.
- **Integration with Main App**: Decide if/how this batch process integrates further (e.g., triggered by API, results surfaced via API).
- **LLM Integration**: Implement the planned step where search queries/topics are generated/refined by an LLM instead of the hardcoded list.

## Known Issues

- The current relevance scoring is basic (keyword-based).
- Metadata extraction (authors, keywords) from processed content is minimal (placeholder).
- Assumes `markitdown` correctly processes `Path` objects for PDFs; needs verification.

## Evolution of Project Decisions

- Decided to use LangGraph for pipeline orchestration.
- Confirmed 5-step pipeline structure (fetch -> rank -> fetch -> process -> store).
- Confirmed loading sensitive configuration from `.env`.
- Adopted separate commits for code and tests.
- Refactored function names for abstraction.
- Added citation count to scoring logic.
- Implemented content conversion using `markitdown`.
- Refactored the graph to iterate internally over a list of topics instead of external looping.
- Added `uv run` script entry point.
