"""
Processors for the buildDataset feature, including ranking initial results
and converting raw content to structured markdown using MarkItDown.
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import re
import math # Import math for log scaling

from .schemas import InitialSearchResult, FullContentData, ProcessedContent
# Assuming MarkItDown is available or we'll use a wrapper
# from markitdown import MarkItDownConverter # Placeholder

logger = logging.getLogger(__name__)

def calculate_weighted_quality_score(result: InitialSearchResult) -> float:
    """
    Calculates a weighted quality score for an initial search result.

    This is a placeholder implementation based on the plan.
    Weights and criteria should be refined based on data analysis.

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
    # This is a very basic relevance score. A more advanced approach
    # would involve vector embeddings or keyword extraction.
    relevance_score = 0.0
    if result.title and result.original_metadata.research_topic.lower() in result.title.lower():
         relevance_score += 0.5
    if result.snippet and result.original_metadata.research_topic.lower() in result.snippet.lower():
         relevance_score += 0.5
    # Normalize to 0-1 (basic)
    relevance_score = min(relevance_score, 1.0)

    # Recency (simple: score decreases with age)
    recency_score = 0.0
    if result.publication_date_str:
        try:
            # Attempt to parse date string. This is highly dependent on SerpAPI format.
            # Need to inspect actual SerpAPI results to implement robust parsing.
            # Placeholder: Assume a simple year extraction or similar.
            year_match = re.search(r'\b(\d{4})\b', result.publication_date_str)
            if year_match:
                year = int(year_match.group(1))
                current_year = datetime.now().year
                age = current_year - year
                # Simple inverse relationship with age, capped
                recency_score = max(0, 1.0 - (age / 10.0)) # 10 years old gets 0 score
            else:
                 logger.warning(f"Could not parse year from date string: {result.publication_date_str}")
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
    # Using log10: 10 citations -> 0.33, 100 -> 0.66, 1000 -> 1.0
    citation_score = 0.0
    if result.citation_count is not None and result.citation_count > 0:
        # Add 1 to handle log10(1) = 0 case smoothly, scale by log10(1001) which is approx 3
        # This makes 1 citation have a small score, 1000 citations approach 1.0
        citation_score = min(1.0, math.log10(result.citation_count + 1) / math.log10(1001))
    elif result.citation_count == 0:
         citation_score = 0.0
    else: # None case
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
    for result in results:
        result.quality_score = calculate_weighted_quality_score(result)

    # Sort by score in descending order
    ranked_results = sorted(results, key=lambda x: x.quality_score if x.quality_score is not None else -1, reverse=True)

    logger.info(f"Ranked {len(results)} results. Top {min(top_n, len(results))} selected.")

    # Return top N
    return ranked_results[:top_n]

def convert_content_to_markdown(
    full_content_data: FullContentData
) -> Optional[ProcessedContent]:
    """
    Converts raw content (HTML/PDF text) into structured markdown, initially using MarkItDown.

    Args:
        full_content_data: A FullContentData object containing raw content.

    Returns:
        A ProcessedContent object, or None if processing fails.
    """
    if not full_content_data.raw_content:
        logger.warning(f"No raw content provided for processing URL: {full_content_data.source_url}")
        return None

    try:
        # Placeholder for MarkItDown integration
        # This part needs the actual MarkItDown library or a wrapper.
        # Assuming MarkItDownConverter takes raw text and returns markdown.
        # converter = MarkItDownConverter() # Example instantiation
        # structured_markdown = converter.convert(full_content_data.raw_content)

        # For now, a simple placeholder: just return the raw content as markdown
        structured_markdown = f"# Content from {full_content_data.source_url}\n\n" + full_content_data.raw_content[:2000] + "...\n\n[Full content truncated for example]" # Truncate for example

        # Attempt to extract title, authors, etc. from the raw content or metadata
        # This is a complex task and might require more sophisticated parsing or an LLM.
        # For now, populate from original metadata.
        title = full_content_data.original_metadata.title
        authors = None # MarkItDown might help extract this, or need custom logic
        publication_date = full_content_data.original_metadata.publication_date_str
        abstract = full_content_data.original_metadata.snippet # Use snippet as abstract placeholder
        keywords = None # Could potentially extract from content

        processed_content = ProcessedContent(
            source_url=full_content_data.source_url,
            original_metadata=full_content_data.original_metadata,
            title=title,
            authors=authors,
            publication_date=publication_date,
            abstract=abstract,
            keywords=keywords,
            full_text_markdown=structured_markdown
        )
        logger.info(f"Successfully processed content for URL: {full_content_data.source_url}")
        return processed_content

    except Exception as e:
        logger.error(f"Error processing content for URL {full_content_data.source_url}: {e}")
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
#             original_metadata={"research_topic": "RAG evaluation"} # Add research_topic for relevance scoring
#         ),
#         InitialSearchResult(
#             link="http://example.com/paper2",
#             title="Old RAG Paper",
#             snippet="An early paper on Retrieval Augmented Generation.",
#             source_name="Some Conference",
#             publication_date_str="2019",
#             original_metadata={"research_topic": "RAG evaluation"}
#         ),
#         InitialSearchResult(
#             link="http://example.com/blogpost",
#             title="Evaluating RAG: A Quick Guide",
#             snippet="A simple guide to RAG evaluation metrics.",
#             source_name="Medium Blog",
#             publication_date_str="2023-10-01",
#             original_metadata={"research_topic": "RAG evaluation"}
#         ),
#     ]
#     ranked = rank_initial_results(sample_results, top_n=2)
#     print("Ranked Results:")
#     for r in ranked:
#         print(f"- {r.title} (Score: {r.quality_score:.2f})")

#     # Example of processing (requires dummy FullContentData)
#     # dummy_full_content = FullContentData(
#     #     source_url="http://example.com/dummy",
#     #     original_metadata=sample_results[0], # Use one of the sample results
#     #     raw_content="<html><body><h1>Test Title</h1><p>Some content here.</p></body></html>",
#     #     content_type="html"
#     # )
#     # processed = convert_content_to_markdown(dummy_full_content) # Updated function name here
#     # if processed:
#     #     print("\nProcessed Content:")
#     #     print(f"Title: {processed.title}")
#     #     print(f"Markdown:\n{processed.full_text_markdown[:500]}...")
