"""
LangGraph definition for the buildDataset data collection pipeline.
Handles iterating through a list of research topics within a single graph execution.
Defines the state, nodes, and workflow for fetching, processing, and storing data.
"""
from typing import List, Dict, TypedDict, Optional, Any
import logging
from pathlib import Path

from langgraph.graph import StateGraph, END, START

from .config import settings
from .schemas import InitialSearchResult, FullContentData, ProcessedContent
from .tools import search_academic_papers_serpapi, download_pdf_async, fetch_webpage_content
from .processors import rank_initial_results, convert_content_to_markdown
from .storage import store_processed_content

logger = logging.getLogger(__name__)

# --- Redefined Graph State for Iteration ---
class GraphState(TypedDict):
    """
    Represents the state of the data collection pipeline, designed for iteration.
    """
    # Inputs
    research_topics: List[str]

    # Iteration control
    current_topic_index: int # Index of the topic currently being processed
    current_topic: Optional[str] # The topic string itself

    # State per topic iteration (cleared between topics)
    initial_search_results: Optional[List[InitialSearchResult]]
    ranked_initial_results: Optional[List[InitialSearchResult]]
    top_n_selected_for_full_fetch: Optional[List[InitialSearchResult]]
    fetched_full_content: Optional[List[FullContentData]]
    processed_structured_data: Optional[List[ProcessedContent]] # Results for the current topic

    # Accumulated results across all topics
    all_processed_data: List[ProcessedContent]
    all_gcs_links: List[str]
    aggregated_errors: List[str] # Collects errors from all topics/steps

# --- Node Implementations (Modified for Iteration) ---

def node_prepare_next_topic(state: GraphState) -> Dict[str, Any]:
    """
    Sets up the state for processing the next topic in the list.
    Increments the index and clears intermediate state fields.
    """
    logger.info("Executing node: prepare_next_topic")
    current_index = state.get("current_topic_index", -1) # Start at -1 so first increment is 0
    next_index = current_index + 1
    topics = state["research_topics"]

    if next_index < len(topics):
        current_topic = topics[next_index]
        logger.info(f"Preparing to process topic {next_index + 1}/{len(topics)}: '{current_topic}'")
        # Clear state fields relevant to a single topic run
        return {
            "current_topic_index": next_index,
            "current_topic": current_topic,
            "initial_search_results": None,
            "ranked_initial_results": None,
            "top_n_selected_for_full_fetch": None,
            "fetched_full_content": None,
            "processed_structured_data": None,
            # Keep accumulators: all_processed_data, all_gcs_links, aggregated_errors
        }
    else:
        # This case should ideally not be reached if the conditional edge works correctly,
        # but handle defensively.
        logger.info("All topics processed.")
        return {} # No changes, should proceed to END via conditional edge


def node_fetch_initial_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to fetch initial search results for the current topic.
    """
    topic = state.get("current_topic")
    current_errors = state.get("aggregated_errors", []) # Use aggregated errors
    logger.info(f"Executing node: fetch_initial_results for topic: '{topic}'")

    if not topic:
        error_msg = "Current topic is missing from state in fetch_initial_results."
        logger.error(error_msg)
        current_errors.append(error_msg)
        return {"initial_search_results": [], "aggregated_errors": current_errors}

    initial_results = []
    raw_results = []
    try:
        raw_results = search_academic_papers_serpapi(topic, num_results=settings.TOP_N_RESULTS_TO_FETCH * 2)
        logger.info(f"SerpAPI returned {len(raw_results)} raw results for topic '{topic}'.")
    except Exception as e_api:
        error_msg = f"Error during SerpAPI call for topic '{topic}': {e_api}"
        logger.exception(error_msg)
        current_errors.append(error_msg)

    for res in raw_results:
        try:
            link = res.get("link")
            if not link:
                logger.warning(f"Skipping result due to missing link: {res.get('title')}")
                continue

            citation_count = None
            cited_by_info = res.get('cited_by', {})
            if isinstance(cited_by_info, dict):
                count_value = cited_by_info.get('value')
                if isinstance(count_value, int):
                    citation_count = count_value
                elif isinstance(count_value, str) and count_value.isdigit():
                     try: citation_count = int(count_value)
                     except ValueError: logger.warning(f"Could not convert citation count string '{count_value}' to int for link: {link}")
                elif count_value is not None: logger.warning(f"Unexpected type for citation count value '{count_value}' ({type(count_value)}) for link: {link}")

            initial_results.append(InitialSearchResult(
                link=link, title=res.get("title"), citation_count=citation_count,
                snippet=res.get("snippet"), source_name=res.get("source"),
                publication_date_str=res.get("publication_date"), raw_serpapi_data=res,
                original_metadata={"research_topic": topic}
            ))
        except Exception as e_item:
            error_msg = f"Failed to parse/validate SerpAPI result item for topic '{topic}': {res}. Error: {e_item}"
            logger.warning(error_msg)
            current_errors.append(error_msg)

    logger.info(f"Successfully parsed {len(initial_results)} initial results for topic '{topic}'.")
    return {"initial_search_results": initial_results, "aggregated_errors": current_errors}


def node_rank_initial_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to rank initial search results for the current topic.
    """
    topic = state.get("current_topic")
    logger.info(f"Executing node: rank_initial_results for topic: '{topic}'")
    initial_results = state.get("initial_search_results")
    current_errors = state.get("aggregated_errors", [])

    if not initial_results:
        logger.warning(f"No initial results to rank for topic: '{topic}'.")
        return {"ranked_initial_results": [], "top_n_selected_for_full_fetch": [], "aggregated_errors": current_errors}

    try:
        ranked_results = rank_initial_results(initial_results, top_n=settings.TOP_N_RESULTS_TO_FETCH)
        logger.info(f"Selected {len(ranked_results)} top results after ranking for topic '{topic}'.")
        return {"ranked_initial_results": ranked_results, "top_n_selected_for_full_fetch": ranked_results, "aggregated_errors": current_errors}
    except Exception as e:
        error_msg = f"Error during ranking for topic '{topic}': {e}"
        logger.exception(error_msg)
        current_errors.append(error_msg)
        return {"ranked_initial_results": [], "top_n_selected_for_full_fetch": [], "aggregated_errors": current_errors}


async def node_fetch_full_content(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to fetch full content for the current topic's selected results.
    """
    topic = state.get("current_topic")
    logger.info(f"Executing node: fetch_full_content for topic: '{topic}'")
    current_errors = state.get("aggregated_errors", [])
    selected_results = state.get("top_n_selected_for_full_fetch")

    if not selected_results:
        logger.warning(f"No results selected for full content fetch for topic: '{topic}'.")
        return {"fetched_full_content": [], "aggregated_errors": current_errors}

    fetched_content_list: List[FullContentData] = []
    temp_pdf_dir = Path("./temp_pdfs")
    temp_pdf_dir.mkdir(parents=True, exist_ok=True)

    for result in selected_results:
        url = str(result.link)
        logger.info(f"Attempting to fetch full content for: {url} (Topic: '{topic}')")
        file_path, raw_content_val, content_type, dl_success, err_msg = None, None, None, False, None
        try:
            if url.lower().endswith(".pdf"):
                content_type = "pdf"
                dl_path = await download_pdf_async(url, temp_pdf_dir)
                if dl_path and dl_path.exists(): file_path, dl_success = dl_path, True
                else: err_msg = f"Failed to download PDF from {url}"
            else:
                content_type = "html"
                fetched_raw_content = await fetch_webpage_content(url)
                if fetched_raw_content: raw_content_val, dl_success = fetched_raw_content, True
                else: err_msg = f"Failed to fetch webpage content from {url}."
        except Exception as e:
            err_msg = f"Unexpected error fetching content for {url}: {e}"
            logger.exception(err_msg)
            if content_type is None: content_type = "unknown"

        if err_msg:
            logger.error(err_msg)
            current_errors.append(err_msg)

        fetched_content_list.append(FullContentData(
            source_url=result.link, original_metadata=result, file_path=file_path,
            raw_content=raw_content_val, content_type=content_type or "unknown",
            download_successful=dl_success, error_message=err_msg
        ))

    successful_fetches = sum(item.download_successful for item in fetched_content_list)
    logger.info(f"Attempted fetch for {len(selected_results)} results for topic '{topic}'. Successful: {successful_fetches}")
    return {"fetched_full_content": fetched_content_list, "aggregated_errors": current_errors}


def node_process_full_content(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to process fetched content for the current topic.
    Appends results to the main accumulator list.
    """
    topic = state.get("current_topic")
    logger.info(f"Executing node: process_full_content for topic: '{topic}'")
    current_errors = state.get("aggregated_errors", [])
    fetched_content_list = state.get("fetched_full_content")
    # Get the accumulator list, default to empty list if not present
    all_processed_data = state.get("all_processed_data", []) or []

    if not fetched_content_list:
        logger.warning(f"No full content data to process for topic: '{topic}'.")
        # Return current state of accumulators
        return {"processed_structured_data": [], "all_processed_data": all_processed_data, "aggregated_errors": current_errors}

    processed_for_this_topic: List[ProcessedContent] = []
    for item in fetched_content_list:
        if item.download_successful and (item.file_path or item.raw_content):
            try:
                processed_item = convert_content_to_markdown(item)
                if processed_item:
                    processed_for_this_topic.append(processed_item)
                else:
                    error_msg = f"Processing failed for URL: {item.source_url} (Topic: '{topic}', convert_content_to_markdown returned None)"
                    logger.error(error_msg)
                    current_errors.append(error_msg)
            except Exception as e:
                 error_msg = f"Error during processing content for URL {item.source_url} (Topic: '{topic}'): {e}"
                 logger.exception(error_msg)
                 current_errors.append(error_msg)
        else:
            if not item.download_successful and item.error_message:
                 skip_msg = f"Skipping processing for URL {item.source_url} (Topic: '{topic}') due to failed download. Error: {item.error_message}"
                 logger.warning(skip_msg)
            elif not item.file_path and not item.raw_content:
                 logger.warning(f"Skipping processing for URL {item.source_url} (Topic: '{topic}') due to missing content source.")

    logger.info(f"Successfully processed {len(processed_for_this_topic)} items for topic '{topic}'.")
    # Append results for this topic to the main list
    all_processed_data.extend(processed_for_this_topic)
    # Return the processed data for *this topic* (for potential immediate storage) and the updated accumulators
    return {"processed_structured_data": processed_for_this_topic, "all_processed_data": all_processed_data, "aggregated_errors": current_errors}


def node_store_results(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node to store the processed data for the current topic.
    Appends links to the main accumulator list.
    """
    topic = state.get("current_topic")
    logger.info(f"Executing node: store_results for topic: '{topic}'")
    current_errors = state.get("aggregated_errors", [])
    # Use the results processed in the *current* iteration
    processed_data_list = state.get("processed_structured_data")
    # Get the accumulator list for links
    all_gcs_links = state.get("all_gcs_links", []) or []

    if not processed_data_list:
        logger.warning(f"No processed data to store for topic: '{topic}'.")
        return {"all_gcs_links": all_gcs_links, "aggregated_errors": current_errors}

    try:
        # Use topic in the base path for organization
        base_path = f"research_dataset/{topic.replace(' ', '_').lower()}"
        stored_data_with_links = store_processed_content(processed_data_list, base_path=base_path)

        storage_links_this_topic = [str(item.gcs_storage_link) for item in stored_data_with_links if item.gcs_storage_link]
        failed_uploads = len(processed_data_list) - len(storage_links_this_topic)

        logger.info(f"Attempted to store {len(processed_data_list)} items for topic '{topic}'. Successfully stored {len(storage_links_this_topic)} with links.")
        all_gcs_links.extend(storage_links_this_topic) # Add links from this topic to the main list

        if failed_uploads > 0:
             error_msg = f"Failed to store {failed_uploads} items to GCS for topic '{topic}' (check previous logs)."
             logger.error(error_msg)
             current_errors.append(error_msg)

        return {"all_gcs_links": all_gcs_links, "aggregated_errors": current_errors}

    except Exception as e:
        error_msg = f"Unexpected error during storage process for topic '{topic}': {e}"
        logger.exception(error_msg)
        current_errors.append(error_msg)
        return {"all_gcs_links": all_gcs_links, "aggregated_errors": current_errors}

# --- Conditional Edge Logic ---

def should_continue(state: GraphState) -> str:
    """
    Determines if the graph should continue to the next topic or end.
    """
    logger.debug("Executing conditional edge: should_continue")
    current_index = state["current_topic_index"]
    total_topics = len(state["research_topics"])

    if current_index + 1 < total_topics:
        logger.debug(f"Condition met: More topics to process ({current_index + 1} < {total_topics}). Returning 'continue'.")
        return "continue"
    else:
        logger.debug(f"Condition met: All topics processed ({current_index + 1} >= {total_topics}). Returning 'end'.")
        return "end"

# --- Graph Definition ---

def build_data_collection_graph():
    """
    Builds and compiles the LangGraph for the data collection pipeline with internal iteration.
    """
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("prepare_next_topic", node_prepare_next_topic)
    workflow.add_node("fetch_initial", node_fetch_initial_results)
    workflow.add_node("rank_initial", node_rank_initial_results)
    workflow.add_node("fetch_full", node_fetch_full_content)
    workflow.add_node("process_full", node_process_full_content)
    workflow.add_node("store_results", node_store_results)

    # Define edges
    workflow.set_entry_point("prepare_next_topic") # Start by preparing the first topic
    workflow.add_edge("prepare_next_topic", "fetch_initial")
    workflow.add_edge("fetch_initial", "rank_initial")
    workflow.add_edge("rank_initial", "fetch_full")
    workflow.add_edge("fetch_full", "process_full")
    workflow.add_edge("process_full", "store_results")

    # Add conditional edge after storing results
    workflow.add_conditional_edges(
        "store_results", # Source node
        should_continue, # Function to decide the next path
        {
            "continue": "prepare_next_topic", # If should_continue returns "continue", go back to prepare
            "end": END                      # If should_continue returns "end", finish the graph
        }
    )

    # Compile the graph
    app_graph = workflow.compile()
    logger.info("LangGraph for iterative data collection compiled.")
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
