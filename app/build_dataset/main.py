"""
Main entry point for triggering the dataset build process.
Orchestrates the data collection pipeline using LangGraph for a predefined list of topics.
"""
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import List # Import List

from .graph import build_data_collection_graph, GraphState
from .config import settings

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Placeholder list of topics to process
TOPICS_TO_PROCESS: List[str] = [
    "Reference-free RAG evaluation metrics",
    "Techniques for evaluating RAG faithfulness",
    "Assessing RAG relevance without ground truth",
    "LLM hallucination detection in RAG",
    "Evaluating RAG context augmentation effectiveness",
    # Add more topics as needed
]

# Compile graph once on import
dataset_graph = build_data_collection_graph()

async def run_build_dataset_pipeline(topics: List[str]) -> GraphState:
    """
    Runs the full data collection and processing pipeline for a list of research topics.

    Args:
        topics: A list of research topic strings.

    Returns:
        The final graph state after processing all topics.
    """
    logger.info(f"Starting dataset build pipeline for {len(topics)} topics.")
    # Initialize state with the list of topics and empty accumulators
    initial_input = GraphState(
        research_topics=topics,
        current_topic_index=-1, # Will be incremented to 0 by prepare_next_topic
        current_topic=None,
        initial_search_results=None,
        ranked_initial_results=None,
        top_n_selected_for_full_fetch=None,
        fetched_full_content=None,
        processed_structured_data=None,
        all_processed_data=[],
        all_gcs_links=[],
        aggregated_errors=[]
    )

    # Invoke the graph once; it will iterate internally
    final_state = await dataset_graph.invoke(initial_input)

    # Log final summary
    total_processed = len(final_state.get("all_processed_data", []))
    total_links = len(final_state.get("all_gcs_links", []))
    total_errors = len(final_state.get("aggregated_errors", []))

    logger.info(f"Pipeline finished processing {len(topics)} topics.")
    logger.info(f"Total items processed and structured: {total_processed}")
    logger.info(f"Total items successfully stored with links: {total_links}")
    logger.info(f"Total errors encountered: {total_errors}")

    if total_errors > 0:
        logger.error("Errors occurred during pipeline execution:")
        for i, err in enumerate(final_state["aggregated_errors"]):
            logger.error(f"  Error {i+1}: {err}")
    else:
        logger.info("Pipeline completed successfully with no errors.")

    return final_state

def run_all_topics():
    """
    Loads environment, checks settings, and runs the pipeline for all predefined topics.
    This function serves as the entry point for the script runner (e.g., `uv run build-dataset`).
    """
    logger.info("--- Starting Build Dataset Script ---")
    # Load .env file from project root
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        logger.info(f"Loaded environment variables from {dotenv_path}")
    else:
        logger.warning(f".env file not found at {dotenv_path}. Ensure environment variables are set.")

    # Check for required settings before running
    if not settings.SERPAPI_API_KEY:
        logger.error("SERPAPI_API_KEY is not set. Cannot run pipeline.")
        return # Exit if required keys are missing
    if not settings.GCS_BUCKET_NAME:
         logger.error("GCS_BUCKET_NAME is not set. Cannot run pipeline.")
         return # Exit if required keys are missing

    logger.info(f"Processing {len(TOPICS_TO_PROCESS)} topics...")
    try:
        # Run the async pipeline for the list of topics
        asyncio.run(run_build_dataset_pipeline(TOPICS_TO_PROCESS))
    except Exception as e:
        logger.exception(f"An unexpected error occurred during the main pipeline execution: {e}")

    logger.info("--- Build Dataset Script Finished ---")


if __name__ == "__main__":
    run_all_topics()
