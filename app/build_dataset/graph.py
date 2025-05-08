"""
LangGraph definition for the buildDataset data collection pipeline.
Defines the state, nodes, and workflow for fetching, processing, and storing data.
"""
from typing import List, Dict, TypedDict, Optional, Any
import logging
from pathlib import Path # Added for temp_pdf_dir

from langgraph.graph import StateGraph, END

from .config import settings
from .schemas import InitialSearchResult, FullContentData, ProcessedContent
from .tools import search_academic_papers_serpapi, download_pdf_async, fetch_webpage_content # UPDATED
from .processors import rank_initial_results, convert_content_to_markdown # UPDATED
from .storage import store_processed_content # No change here, internal storage uses refactored name

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
    current_retry_count: int = 0 # Track retries for nodes, default to 0

# --- Node Implementations ---

def node_fetch_initial_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to fetch initial search results using SerpAPI.
    """
    logger.info("Executing node: fetch_initial_results")
    topic = state.get("research_topic")
    if not topic:
        logger.error("Research topic is missing from state.")
        return {"error_messages": (state.get("error_messages", []) or []) + ["Research topic is missing."]}

    # Use the SerpAPI tool
    raw_results = search_academic_papers_serpapi(topic, num_results=settings.TOP_N_RESULTS_TO_FETCH * 2)

    initial_results = []
    for res in raw_results:
        try:
            # Ensure link is valid before creating the object
            link = res.get("link")
            if not link:
                logger.warning(f"Skipping result due to missing link: {res.get('title')}")
                continue

            initial_results.append(InitialSearchResult(
                link=link,
                title=res.get("title"),
                snippet=res.get("snippet"),
                source_name=res.get("source"),
                publication_date_str=res.get("publication_date"),
                raw_serpapi_data=res,
                original_metadata={"research_topic": topic} # Store topic for later use in ranking
            ))
        except Exception as e: # Catch potential Pydantic validation errors too
            logger.warning(f"Failed to parse SerpAPI result item: {res}. Error: {e}")

    logger.info(f"Fetched {len(initial_results)} initial results.")
    return {"initial_search_results": initial_results}

def node_rank_initial_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to rank initial search results and select top N.
    """
    logger.info("Executing node: rank_initial_results")
    initial_results = state.get("initial_search_results")

    if not initial_results:
        logger.warning("No initial results to rank.")
        return {"ranked_initial_results": [], "top_n_selected_for_full_fetch": []}

    # rank_initial_results internally calls calculate_weighted_quality_score,
    # which now uses result.original_metadata.research_topic
    ranked_results = rank_initial_results(initial_results, top_n=settings.TOP_N_RESULTS_TO_FETCH)

    logger.info(f"Selected {len(ranked_results)} top results after ranking.")
    return {"ranked_initial_results": ranked_results, "top_n_selected_for_full_fetch": ranked_results}

async def node_fetch_full_content(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to fetch the full content for the top N selected results.
    Handles both PDF downloads and webpage scraping. Stores file path for PDFs,
    raw content for HTML.
    """
    logger.info("Executing node: fetch_full_content")
    selected_results = state.get("top_n_selected_for_full_fetch")

    if not selected_results:
        logger.warning("No results selected for full content fetch.")
        return {"fetched_full_content": []}

    fetched_content_list: List[FullContentData] = []
    temp_pdf_dir = Path("./temp_pdfs")
    temp_pdf_dir.mkdir(parents=True, exist_ok=True)

    for result in selected_results:
        url = str(result.link)
        logger.info(f"Attempting to fetch full content for: {url}")

        # Initialize variables for this iteration
        file_path: Optional[Path] = None
        raw_content: Optional[str] = None
        content_type: Optional[str] = None
        download_successful: bool = False
        error_message: Optional[str] = None
        downloaded_path: Optional[Path] = None # Keep track of downloaded path

        try:
            if url.lower().endswith(".pdf"):
                content_type = "pdf"
                logger.info(f"Detected PDF link: {url}. Attempting direct download.")
                downloaded_path = await download_pdf_async(url, temp_pdf_dir)
                if downloaded_path and downloaded_path.exists():
                    file_path = downloaded_path # Store the path
                    download_successful = True
                    logger.info(f"Successfully downloaded PDF from {url} to {file_path}.")
                    # Raw content remains None, will be processed from file_path later
                else:
                    error_message = f"Failed to download PDF from {url}"
                    logger.error(error_message)
            else:
                content_type = "html"
                logger.info(f"Attempting to fetch webpage content for: {url}.")
                fetched_raw_content = await fetch_webpage_content(url)
                if fetched_raw_content:
                    raw_content = fetched_raw_content # Store the HTML content
                    download_successful = True
                    logger.info(f"Successfully fetched webpage content from {url}.")
                else:
                    error_message = f"Failed to fetch webpage content from {url}."
                    logger.error(error_message)
        except Exception as e:
            error_message = f"Unexpected error fetching content for {url}: {e}"
            logger.exception(error_message) # Log exception details
            download_successful = False
            # Ensure content_type is set if possible, otherwise default
            if content_type is None:
                content_type = "unknown"


        # Append the result, ensuring content_type has a value
        fetched_content_list.append(FullContentData(
            source_url=result.link,
            original_metadata=result,
            file_path=file_path, # Will be Path for PDF, None for HTML/failed
            raw_content=raw_content, # Will be str for HTML, None for PDF/failed
            content_type=content_type if content_type is not None else "unknown",
            download_successful=download_successful,
            error_message=error_message
        ))

    logger.info(f"Attempted to fetch full content for {len(selected_results)} results. Successful: {sum(item.download_successful for item in fetched_content_list)}")
    return {"fetched_full_content": fetched_content_list}

def node_process_full_content(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to process fetched raw content (from file path or raw text)
    into structured markdown using MarkItDown.
    """
    logger.info("Executing node: process_full_content")
    fetched_content_list = state.get("fetched_full_content")

    if not fetched_content_list:
        logger.warning("No full content data to process.")
        return {"processed_structured_data": []}

    processed_data_list: List[ProcessedContent] = []
    for item in fetched_content_list:
        # Process if download was successful AND we have either a file_path (PDF) or raw_content (HTML)
        if item.download_successful and (item.file_path or item.raw_content):
            try:
                # Pass the whole FullContentData object to the processor
                # The processor will decide whether to use file_path or raw_content
                processed_item = convert_content_to_markdown(item)
                if processed_item:
                    processed_data_list.append(processed_item)
                else:
                    logger.error(f"Processing failed for URL: {item.source_url}")
            except Exception as e:
                 logger.exception(f"Error during processing content for URL {item.source_url}: {e}")
        else:
            logger.warning(f"Skipping processing for URL {item.source_url} due to failed download or missing content source (file_path or raw_content). Error: {item.error_message}")

    logger.info(f"Successfully processed {len(processed_data_list)} items.")
    return {"processed_structured_data": processed_data_list}

def node_store_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to store the processed structured data in a storage backend.
    """
    logger.info("Executing node: store_results")
    processed_data_list = state.get("processed_structured_data")

    if not processed_data_list:
        logger.warning("No processed data to store.")
        return {"gcs_storage_links": []} # Field name is still gcs_storage_links for now

    stored_data_with_links = store_processed_content(processed_data_list, base_path="research_dataset/phase1")

    storage_links = [str(item.gcs_storage_link) for item in stored_data_with_links if item.gcs_storage_link]

    logger.info(f"Attempted to store {len(processed_data_list)} items. Successfully stored {len(storage_links)} with links.")
    # The key in the state remains 'gcs_storage_links' as per GraphState definition,
    # even if the underlying storage becomes more generic.
    # If GraphState.gcs_storage_links needs to be more generic, it should be renamed there too.
    return {"gcs_storage_links": storage_links}

# --- Graph Definition ---

def build_data_collection_graph():
    """
    Builds and compiles the LangGraph for the data collection pipeline.
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("fetch_initial", node_fetch_initial_results)
    workflow.add_node("rank_initial", node_rank_initial_results)
    workflow.add_node("fetch_full", node_fetch_full_content)
    workflow.add_node("process_full", node_process_full_content)
    workflow.add_node("store_results", node_store_results)

    workflow.set_entry_point("fetch_initial")
    workflow.add_edge("fetch_initial", "rank_initial")
    workflow.add_edge("rank_initial", "fetch_full")
    workflow.add_edge("fetch_full", "process_full")
    workflow.add_edge("process_full", "store_results")
    workflow.add_edge("store_results", END)

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
#         # from IPython.display import Image, display
#         # display(Image(graph.get_graph().draw_mermaid_png())) # For mermaid visualization
#         # graph.get_graph().draw_png("data_collection_graph.png") # For direct PNG
#         # print("Graph saved as data_collection_graph.png")
#     except Exception as e:
#         print(f"Could not draw graph: {e}")
#         print("Please ensure graphviz is installed and in your PATH, and install pygraphviz or pydot.")
