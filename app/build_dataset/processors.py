"""
Processors for the buildDataset feature, including ranking initial results
and converting raw content to structured markdown using MarkItDown.
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import re
import math # Import math for log scaling
from pathlib import Path # Import Path
from markitdown import Markitdown

from .schemas import InitialSearchResult, FullContentData, ProcessedContent

logger = logging.getLogger(__name__)

def calculate_weighted_quality_score(result: InitialSearchResult) -> float:
    """
    Calculates a weighted quality score for an initial search result.

    Incorporates relevance (keyword-based), recency, source authority, and citation count.

    Args:
        result: An InitialSearchResult object.

    Returns:
        A float representing the quality score. Higher is better.
    """
    score = 0.0
    # Adjusted weights to include citations
    weights = {
        "relevance": 0.4,        # How well snippet/title matches query (semantic match preferred later)
        "recency": 0.2,          # More recent is better
        "source_authority": 0.1, # Based on source_name (e.g., arxiv.org, reputable journal)
        "citations": 0.3         # Importance of citation count
    }

    # Relevance (simple check: query terms in title/snippet)
    relevance_score = 0.0
    # Safely access nested dictionary for research_topic
    topic = ""
    if result.original_metadata and isinstance(result.original_metadata, dict):
         topic = result.original_metadata.get("research_topic", "").lower()

    if topic:
        if result.title and topic in result.title.lower():
             relevance_score += 0.5
        if result.snippet and topic in result.snippet.lower():
             relevance_score += 0.5
        relevance_score = min(relevance_score, 1.0)
    else:
        logger.warning(f"Research topic missing or inaccessible in original_metadata for relevance scoring: {result.link}")


    # Recency (simple: score decreases with age)
    recency_score = 0.0
    if result.publication_date_str:
        try:
            year_match = re.search(r'\b(\d{4})\b', result.publication_date_str)
            if year_match:
                year = int(year_match.group(1))
                current_year = datetime.now().year
                age = max(0, current_year - year) # Ensure age is not negative
                recency_score = max(0, 1.0 - (age / 10.0)) # 10 years old gets 0 score
            else:
                 logger.warning(f"Could not parse year from date string: {result.publication_date_str}")
                 recency_score = 0.1 # Assign small score if year cannot be parsed
        except Exception as e:
            logger.warning(f"Error parsing date string '{result.publication_date_str}': {e}")
            recency_score = 0.1 # Small score if date parsing fails but string exists
    else:
        recency_score = 0.0 # No date info

    # Source Authority (simple mapping - needs expansion)
    source_authority_score = 0.0
    if result.source_name:
        source_name_lower = result.source_name.lower()
        if "arxiv" in source_name_lower or "acm" in source_name_lower or "ieee" in source_name_lower:
            source_authority_score = 1.0
        elif "researchgate" in source_name_lower or "academia.edu" in source_name_lower:
            source_authority_score = 0.7
        else:
            source_authority_score = 0.3 # Default for unknown sources

    # Citation Score (Logarithmic scaling, capped)
    # Using log10: 10 citations -> ~0.33, 100 -> ~0.66, 1000 -> ~1.0
    citation_score = 0.0
    if result.citation_count is not None and result.citation_count > 0:
        # Add 1 to handle log10(1) = 0 case smoothly, scale by log10(1001) which is approx 3
        # This makes 1 citation have a small score, 1000 citations approach 1.0
        citation_score = min(1.0, math.log10(result.citation_count + 1) / math.log10(1001))
    elif result.citation_count == 0:
         citation_score = 0.0
    else: # None case (citation count unknown)
         citation_score = 0.1 # Assign a small default score if citation count is unknown

    # Combine scores using weights
    score = (relevance_score * weights["relevance"] +
             recency_score * weights["recency"] +
             source_authority_score * weights["source_authority"] +
             citation_score * weights["citations"])

    logger.debug(
        f"Calculated score for '{result.title}': {score:.2f} "
        f"(Rel: {relevance_score:.2f}, Rec: {recency_score:.2f}, Auth: {source_authority_score:.2f}, Cit: {citation_score:.2f})"
    )

    return score

def rank_initial_results(
    results: List[InitialSearchResult],
    top_n: int = 5
) -> List[InitialSearchResult]:
    """
    Ranks initial search results by quality score and selects the top N.

    Args:
        results: A list of InitialSearchResult objects.
        top_n: The number of top results to select.

    Returns:
        A list of the top N InitialSearchResult objects, sorted by score.
    """
    if not results:
        logger.warning("No initial results to rank.")
        return []

    # Calculate score for each result
    scored_results = []
    for result in results:
        # Calculate score and add it to the object
        result.quality_score = calculate_weighted_quality_score(result)
        scored_results.append(result)


    # Sort by score in descending order
    ranked_results = sorted(scored_results, key=lambda x: x.quality_score if x.quality_score is not None else -1, reverse=True)

    logger.info(f"Ranked {len(results)} results. Top {min(top_n, len(ranked_results))} selected.")

    # Return top N
    return ranked_results[:top_n]

def convert_content_to_markdown(
    full_content_data: FullContentData
) -> Optional[ProcessedContent]:
    """
    Converts raw content (from HTML string or PDF file path) into structured markdown
    using the Markitdown library.

    Args:
        full_content_data: A FullContentData object containing either raw_content (HTML)
                           or file_path (PDF).

    Returns:
        A ProcessedContent object, or None if processing fails or Markitdown is unavailable.
    """

    structured_markdown = None
    input_source_description = "" # For logging

    try:
        # Instantiate the converter
        converter = Markitdown(enable_plugins=False)

        if full_content_data.file_path and full_content_data.content_type == "pdf":
            input_source_description = f"PDF file: {full_content_data.file_path}"
            logger.info(f"Processing {input_source_description}")
            structured_markdown = converter.convert(full_content_data.file_path)

        elif full_content_data.raw_content and full_content_data.content_type == "html":
            input_source_description = f"HTML raw content from: {full_content_data.source_url}"
            logger.info(f"Processing {input_source_description}")
            # Assuming Markitdown().convert can handle raw HTML string
            structured_markdown = converter.convert(full_content_data.raw_content)
        else:
            logger.warning(f"No suitable content (PDF path or HTML raw_content) found for URL: {full_content_data.source_url}")
            return None

        if not structured_markdown:
             logger.error(f"Markitdown conversion returned empty result for {input_source_description}")
             return None

        # --- Metadata Extraction (Placeholder) ---
        # Markitdown might extract some metadata, or we might need other tools/LLMs.
        # For now, populate primarily from original metadata.
        title = full_content_data.original_metadata.title
        authors = None # Placeholder
        publication_date = full_content_data.original_metadata.publication_date_str
        abstract = full_content_data.original_metadata.snippet # Use snippet as abstract placeholder
        keywords = None # Placeholder

        processed_content = ProcessedContent(
            source_url=full_content_data.source_url,
            original_metadata=full_content_data.original_metadata,
            title=title,
            authors=authors,
            publication_date=publication_date,
            abstract=abstract,
            keywords=keywords,
            full_text_markdown=structured_markdown.text_content
        )
        logger.info(f"Successfully processed content using Markitdown for URL: {full_content_data.source_url}")
        return processed_content

    except Exception as e:
        logger.exception(f"Error processing content with Markitdown for {input_source_description}: {e}")
        return None

# Example usage (for testing purposes)
# if __name__ == "__main__":
#     # Example of ranking
#     sample_results = [
#         InitialSearchResult(
#             link="http://example.com/paper1",
#             title="Recent Advances in RAG Evaluation",
#             snippet="This paper discusses new methods for evaluating RAG pipelines.",
#             source_name="arxiv.org",
#             publication_date_str="2024",
#             citation_count=150,
#             original_metadata={"research_topic": "RAG evaluation"} # Add research_topic for relevance scoring
#         ),
#         InitialSearchResult(
#             link="http://example.com/paper2",
#             title="Old RAG Paper",
#             snippet="An early paper on Retrieval Augmented Generation.",
#             source_name="Some Conference",
#             publication_date_str="2019",
#             citation_count=5,
#             original_metadata={"research_topic": "RAG evaluation"}
#         ),
#         InitialSearchResult(
#             link="http://example.com/blogpost",
#             title="Evaluating RAG: A Quick Guide",
#             snippet="A simple guide to RAG evaluation metrics.",
#             source_name="Medium Blog",
#             publication_date_str="2023-10-01",
#             citation_count=None, # Unknown citations
#             original_metadata={"research_topic": "RAG evaluation"}
#         ),
#     ]
#     ranked = rank_initial_results(sample_results, top_n=2)
#     print("Ranked Results:")
#     for r in ranked:
#         print(f"- {r.title} (Score: {r.quality_score:.2f})")

#     # Example of processing (requires dummy FullContentData and Markitdown installed)
#     # if Markitdown:
#     #     dummy_html_content = FullContentData(
#     #         source_url="http://example.com/dummy_html",
#     #         original_metadata=sample_results[0], # Use one of the sample results
#     #         raw_content="<html><body><h1>Test Title HTML</h1><p>Some content here.</p></body></html>",
#     #         content_type="html",
#     #         download_successful=True
#     #     )
#     #     processed_html = convert_content_to_markdown(dummy_html_content)
#     #     if processed_html:
#     #         print("\nProcessed HTML Content:")
#     #         print(f"Title: {processed_html.title}")
#     #         print(f"Markdown:\n{processed_html.full_text_markdown[:500]}...")
#     #     else:
#     #         print("\nHTML processing failed.")

#         # Create a dummy PDF file for testing
#         # dummy_pdf_path = Path("./dummy_test.pdf")
#         # try:
#         #     # You'd need a library like reportlab to create a real PDF
#         #     # For simplicity, just create an empty file for the test structure
#         #     dummy_pdf_path.touch()
#         #     dummy_pdf_content = FullContentData(
#         #         source_url="http://example.com/dummy_pdf",
#         #         original_metadata=sample_results[1],
#         #         file_path=dummy_pdf_path, # Provide the file path
#         #         raw_content=None, # Raw content is None for PDF path input
#         #         content_type="pdf",
#         #         download_successful=True
#         #     )
#         #     processed_pdf = convert_content_to_markdown(dummy_pdf_content)
#         #     if processed_pdf:
#         #         print("\nProcessed PDF Content:")
#         #         print(f"Title: {processed_pdf.title}")
#         #         print(f"Markdown:\n{processed_pdf.full_text_markdown[:500]}...")
#         #     else:
#         #         print("\nPDF processing failed.")
#         # finally:
#         #      if dummy_pdf_path.exists():
#         #          dummy_pdf_path.unlink() # Clean up dummy file
