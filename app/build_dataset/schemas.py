"""
Pydantic models for structuring data within the buildDataset feature.
"""
from typing import List, Dict, Optional, Any
from pathlib import Path # Import Path
from pydantic import BaseModel, HttpUrl

class InitialSearchResult(BaseModel):
    """
    Schema for individual items fetched during the initial search.
    """
    title: Optional[str] = None
    link: HttpUrl
    snippet: Optional[str] = None
    source_name: Optional[str] = None # e.g., "arxiv.org", "ACM Digital Library"
    publication_date_str: Optional[str] = None # Raw date string from source
    citation_count: Optional[int] = None # Parsed citation count
    # Add other relevant metadata fields from SerpAPI if available
    raw_serpapi_data: Optional[Dict[str, Any]] = None # Store the full SerpAPI result for the item
    quality_score: Optional[float] = None # To be populated during ranking

class FullContentData(BaseModel):
    """
    Schema for data after fetching the full content.
    """
    source_url: HttpUrl
    original_metadata: InitialSearchResult # Metadata from the initial search
    file_path: Optional[Path] = None # Path to downloaded file (e.g., PDF)
    raw_content: Optional[str] = None # The full text content (e.g., from HTML or extracted from PDF)
    content_type: str # e.g., "pdf", "html"
    download_successful: bool = True
    error_message: Optional[str] = None

class ProcessedContent(BaseModel):
    """
    Schema for content after processing with MarkItDown and structuring.
    """
    source_url: HttpUrl
    original_metadata: InitialSearchResult
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None # Potentially parsed/normalized date
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    full_text_markdown: str # The main content converted to Markdown
    # Add more structured fields as needed, e.g.:
    # methodology: Optional[str] = None
    # results: Optional[str] = None
    # conclusion: Optional[str] = None
    # references: Optional[List[HttpUrl]] = None
    gcs_storage_link: Optional[HttpUrl] = None

# LangGraph State Schema (already defined in plan, but good to have here for reference or direct import)
# from typing import TypedDict # Use this if sticking to TypedDict for state

# class GraphState(TypedDict):
#     research_topic: str
#     initial_search_results: Optional[List[InitialSearchResult]] = None
#     ranked_initial_results: Optional[List[InitialSearchResult]] = None
#     top_n_selected_for_full_fetch: Optional[List[InitialSearchResult]] = None
#     fetched_full_content: Optional[List[FullContentData]] = None
#     processed_structured_data: Optional[List[ProcessedContent]] = None
#     gcs_storage_links: Optional[List[HttpUrl]] = None
#     error_messages: Optional[List[str]] = None
#     current_retry_count: int = 0
