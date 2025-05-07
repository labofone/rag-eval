"""
LangGraph definition for the buildDataset data collection pipeline.
Defines the state, nodes, and workflow for fetching, processing, and storing data.
"""
from typing import List, Dict, TypedDict, Optional, Any
import logging

from langgraph.graph import StateGraph, END

from .config import settings
from .schemas import InitialSearchResult, FullContentData, ProcessedContent
from .tools import search_academic_papers_serpapi, download_pdf_async, fetch_webpage_content_playwright_mcp
from .processors import rank_initial_results, process_raw_content_with_markitdown
from .storage import store_processed_content

logger = logging.getLogger(__name__)

# Define the state for the LangGraph
class GraphState(TypedDict):
    """
    Represents the state of the data collection pipeline.
    """
    research_topic: str
    initial_search_results: Optional[List[InitialSearchResult]] = None
    ranked_initial_results: Optional[List[InitialSearchResult]] = None
    top_n_selected_for_full_fetch: Optional[List[InitialSearchResult]] = None
    fetched_full_content: Optional[List[FullContentData]] = None
    processed_structured_data: Optional[List[ProcessedContent]] = None
    gcs_storage_links: Optional[List[str]] = None # Store URLs as strings
    error_messages: Optional[List[str]] = None
    current_retry_count: int # Track retries for nodes

# --- Node Implementations ---

def node_fetch_initial_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to fetch initial search results using SerpAPI.
    """
    logger.info("Executing node: fetch_initial_results")
    topic = state.get("research_topic")
    if not topic:
        logger.error("Research topic is missing from state.")
        return {"error_messages": ["Research topic is missing."]}

    # Use the SerpAPI tool
    # Note: search_academic_papers_serpapi returns List[Dict], need to convert to List[InitialSearchResult]
    raw_results = search_academic_papers_serpapi(topic, num_results=settings.TOP_N_RESULTS_TO_FETCH * 2) # Fetch more than needed for ranking

    initial_results = []
    for res in raw_results:
        try:
            # Attempt to parse relevant fields and create InitialSearchResult objects
            # This parsing logic might need refinement based on actual SerpAPI response structure
            initial_results.append(InitialSearchResult(
                link=res.get("link"), # Assuming 'link' is always present and valid URL
                title=res.get("title"),
                snippet=res.get("snippet"),
                source_name=res.get("source"), # Assuming 'source' field exists
                publication_date_str=res.get("publication_date"), # Assuming 'publication_date' field exists
                raw_serpapi_data=res,
                # quality_score will be calculated in the next step
            ))
        except Exception as e:
            logger.warning(f"Failed to parse SerpAPI result item: {res}. Error: {e}")
            # Optionally, add to error_messages or skip

    logger.info(f"Fetched {len(initial_results)} initial results.")
    return {"initial_search_results": initial_results}

def node_rank_initial_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to rank initial search results and select top N.
    """
    logger.info("Executing node: rank_initial_results")
    initial_results = state.get("initial_search_results")
    topic = state.get("research_topic") # Need topic for relevance scoring in calculate_weighted_quality_score

    if not initial_results:
        logger.warning("No initial results to rank.")
        return {"ranked_initial_results": [], "top_n_selected_for_full_fetch": []}

    # Add research_topic to each result for ranking calculation
    for res in initial_results:
        # Pydantic models are immutable by default, might need to create a new instance or configure mutability
        # For simplicity here, assuming we can add/modify attributes or pass necessary data
        # A better approach might be to pass topic directly to calculate_weighted_quality_score
        # Let's pass topic directly to the ranking function
        pass # No need to modify the objects if ranking function takes topic

    # Use the ranking processor
    # Pass topic to the ranking function if needed for relevance calculation
    # Modify rank_initial_results or calculate_weighted_quality_score to accept topic
    # For now, assuming calculate_weighted_quality_score can access topic via result.original_metadata if needed
    ranked_results = rank_initial_results(initial_results, top_n=settings.TOP_N_RESULTS_TO_FETCH)

    logger.info(f"Selected {len(ranked_results)} top results after ranking.")
    return {"ranked_initial_results": ranked_results, "top_n_selected_for_full_fetch": ranked_results} # Top N are also the ones selected for full fetch

async def node_fetch_full_content(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to fetch the full content for the top N selected results.
    Handles both PDF downloads and webpage scraping via MCP.
    """
    logger.info("Executing node: fetch_full_content")
    selected_results = state.get("top_n_selected_for_full_fetch")
    
    if not selected_results:
        logger.warning("No results selected for full content fetch.")
        return {"fetched_full_content": []}

    fetched_content_list: List[FullContentData] = []
    temp_pdf_dir = Path("./temp_pdfs") # Temporary directory for downloaded PDFs

    # Ensure the temp directory exists
    temp_pdf_dir.mkdir(parents=True, exist_ok=True)

    for result in selected_results:
        url = str(result.link) # Ensure URL is string
        logger.info(f"Attempting to fetch full content for: {url}")
        
        raw_content = None
        content_type = None
        download_successful = False
        error_message = None

        # Simple check for PDF link (can be improved)
        if url.lower().endswith(".pdf"):
            logger.info(f"Detected PDF link: {url}. Attempting direct download.")
            downloaded_path = await download_pdf_async(url, temp_pdf_dir)
            if downloaded_path and downloaded_path.exists():
                try:
                    # Read content from downloaded PDF (requires a PDF reading library like PyMuPDF or pdfminer.six)
                    # This is a placeholder. Actual PDF text extraction is complex.
                    # For now, we'll just store a placeholder indicating success.
                    # A real implementation needs a PDF text extraction step here.
                    raw_content = f"Content from PDF: {downloaded_path.name}" # Placeholder content
                    content_type = "pdf"
                    download_successful = True
                    logger.info(f"Successfully downloaded PDF from {url}. Content will be processed later.")
                except Exception as e:
                    error_message = f"Error reading downloaded PDF {downloaded_path}: {e}"
                    logger.error(error_message)
                    download_successful = False
            else:
                error_message = f"Failed to download PDF from {url}"
                logger.error(error_message)
                download_successful = False
        else:
            logger.info(f"Attempting to fetch webpage content for: {url} via Playwright MCP.")
            # Use the Playwright MCP tool
            raw_content = await fetch_webpage_content_playwright_mcp(url)
            if raw_content:
                content_type = "html" # Assuming MCP returns HTML content
                download_successful = True
                logger.info(f"Successfully fetched webpage content from {url}.")
            else:
                error_message = f"Failed to fetch webpage content from {url} via Playwright MCP."
                logger.error(error_message)
                download_successful = False

        fetched_content_list.append(FullContentData(
            source_url=result.link,
            original_metadata=result,
            raw_content=raw_content if raw_content is not None else "", # Store empty string if fetch failed
            content_type=content_type if content_type is not None else "unknown",
            download_successful=download_successful,
            error_message=error_message
        ))

    # Clean up temporary PDF directory after processing all downloads
    # Note: This cleanup might be better placed after the processing step if processing reads from these files.
    # For this placeholder, it's fine here.
    # try:
    #     for f in temp_pdf_dir.iterdir():
    #         f.unlink()
    #     temp_pdf_dir.rmdir()
    # except OSError as e:
    #      logger.warning(f"Failed to remove temporary PDF directory {temp_pdf_dir}: {e}. It might not be empty.")


    logger.info(f"Attempted to fetch full content for {len(selected_results)} results. Successful: {sum(item.download_successful for item in fetched_content_list)}")
    return {"fetched_full_content": fetched_content_list}

def node_process_full_content(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to process fetched raw content into structured markdown.
    Uses MarkItDown.
    """
    logger.info("Executing node: process_full_content")
    fetched_content_list = state.get("fetched_full_content")

    if not fetched_content_list:
        logger.warning("No full content data to process.")
        return {"processed_structured_data": []}

    processed_data_list: List[ProcessedContent] = []
    for item in fetched_content_list:
        if item.download_successful and item.raw_content:
            processed_item = process_raw_content_with_markitdown(item)
            if processed_item:
                processed_data_list.append(processed_item)
            else:
                logger.error(f"Processing failed for URL: {item.source_url}")
                # Optionally, add to error_messages or handle failure
        else:
            logger.warning(f"Skipping processing for URL {item.source_url} due to failed download or empty content.")
            # Optionally, add a note to error_messages

    logger.info(f"Successfully processed {len(processed_data_list)} items.")
    return {"processed_structured_data": processed_data_list}

def node_store_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to store the processed structured data in Google Cloud Storage.
    """
    logger.info("Executing node: store_results")
    processed_data_list = state.get("processed_structured_data")

    if not processed_data_list:
        logger.warning("No processed data to store.")
        return {"gcs_storage_links": []}

    # Use the storage function
    # store_processed_content returns the list with updated GCS links
    stored_data_with_links = store_processed_content(processed_data_list, base_path="research_dataset/phase1")

    gcs_links = [str(item.gcs_storage_link) for item in stored_data_with_links if item.gcs_storage_link]

    logger.info(f"Attempted to store {len(processed_data_list)} items. Successfully stored {len(gcs_links)}.")
    return {"gcs_storage_links": gcs_links}

# --- Graph Definition ---

def build_data_collection_graph():
    """
    Builds and compiles the LangGraph for the data collection pipeline.
    """
    workflow = StateGraph(GraphState)

    # Add nodes corresponding to the pipeline steps
    workflow.add_node("fetch_initial", node_fetch_initial_results)
    workflow.add_node("rank_initial", node_rank_initial_results)
    workflow.add_node("fetch_full", node_fetch_full_content)
    workflow.add_node("process_full", node_process_full_content)
    workflow.add_node("store_results", node_store_results)

    # Define edges (sequential flow for now)
    workflow.set_entry_point("fetch_initial")
    workflow.add_edge("fetch_initial", "rank_initial")
    workflow.add_edge("rank_initial", "fetch_full")
    workflow.add_edge("fetch_full", "process_full")
    workflow.add_edge("process_full", "store_results")
    workflow.add_edge("store_results", END) # End the graph after storing

    # Compile the graph
    app_graph = workflow.compile()
    logger.info("LangGraph for data collection compiled.")
    return app_graph

# Example of how to visualize the graph (requires graphviz)
# if __name__ == "__main__":
#     graph = build_data_collection_graph()
#     try:
#         # Requires graphviz to be installed (`dot` command in PATH)
#         # and pygraphviz or pydot (`pip install pygraphviz` or `pip install pydot`)
#         print("Attempting to draw graph...")
#         # graph.get_graph().draw("data_collection_graph.png", prog="dot")
#         # print("Graph saved as data_collection_graph.png")
#         # Or display directly if in an environment that supports it
#         # graph.get_graph()
#     except Exception as e:
#         print(f"Could not draw graph: {e}")
#         print("Please ensure graphviz is installed and in your PATH, and install pygraphviz or pydot.")
#         print("You can still run the graph even if visualization fails.")
