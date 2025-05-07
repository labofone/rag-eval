"""
Main entry point for triggering the dataset build process.
Orchestrates the data collection pipeline using LangGraph.
"""
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv # Needed for loading .env in __main__

from .graph import build_data_collection_graph, GraphState
from .config import settings

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Compile graph once on import
dataset_graph = build_data_collection_graph()

async def run_build_dataset_pipeline(topic: str) -> GraphState:
    """
    Runs the full data collection and processing pipeline for a given research topic.
    """
    logger.info(f"Starting dataset build pipeline for topic: {topic}")
    initial_input = GraphState(research_topic=topic, current_retry_count=0, error_messages=[]) # Initialize error_messages
    
    # LangGraph invoke is synchronous by default, but nodes can be async.
    # If using async nodes, the graph itself needs to be invoked within an async context.
    # Our nodes (fetch_full) are async, so we need to run the graph with await.
    final_state = await dataset_graph.invoke(initial_input)

    if final_state.get("error_messages"):
        logger.error(f"Pipeline for topic '{topic}' encountered errors:")
        for err in final_state["error_messages"]:
            logger.error(f"- {err}")
    else:
        logger.info(f"Pipeline for topic '{topic}' completed successfully.")
        if final_state.get("gcs_storage_links"):
            logger.info("Stored data at:")
            for link in final_state["gcs_storage_links"]:
                logger.info(f"- {link}")
        else:
             logger.warning("Pipeline completed but no GCS storage links were generated.")

    return final_state

if __name__ == "__main__":
    # Example usage:
    # Ensure that the .env file is in the project root and contains necessary API keys.
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
    elif not settings.GCS_BUCKET_NAME:
         logger.error("GCS_BUCKET_NAME is not set. Cannot run pipeline.")
    else:
        test_topic = "Reference-free RAG evaluation metrics"
        print(f"Starting dataset build pipeline for topic: {test_topic}")
        # Run the async pipeline
        asyncio.run(run_build_dataset_pipeline(test_topic))
