"""
Functions for storing processed dataset content in Google Cloud Storage.
"""
from typing import List, Optional
from pathlib import Path
import logging
from google.cloud import storage
from google.oauth2 import service_account # Optional, if using service account JSON
import re # Import re for sanitizing URLs

from .config import settings
from .schemas import ProcessedContent

logger = logging.getLogger(__name__)

def upload_raw_artifact(
    bucket_name: str,
    source_file_path: Path,
    destination_blob_name: str
) -> Optional[str]:
    """
    Uploads a raw artifact (file) to a storage backend, initially GCS.

    Args:
        bucket_name: The name of the GCS bucket (or equivalent for other backends).
        source_file_path: The local path to the file to upload.
        destination_blob_name: The desired path/name of the blob in the bucket.

    Returns:
        The public URL of the uploaded blob, or None if upload fails.
    """
    if not settings.GCS_BUCKET_NAME: # This check remains specific to GCS for now
        logger.error("GCS_BUCKET_NAME is not configured. Cannot upload artifact.")
        return None

    try:
        # Initialize GCS client
        # Prioritize service account file if specified, otherwise use ADC
        if settings.GCS_SERVICE_ACCOUNT_FILE and Path(settings.GCS_SERVICE_ACCOUNT_FILE).exists():
            credentials = service_account.Credentials.from_service_account_file(
                settings.GCS_SERVICE_ACCOUNT_FILE
            )
            client = storage.Client(project=settings.GCS_PROJECT, credentials=credentials)
            logger.info("Using service account credentials for GCS.")
        elif settings.GCS_PROJECT:
             # Use ADC with specified project
             client = storage.Client(project=settings.GCS_PROJECT)
             logger.info(f"Using Application Default Credentials with project '{settings.GCS_PROJECT}' for GCS.")
        else:
            # Use ADC without explicit project (relies on environment variable GOOGLE_CLOUD_PROJECT)
            client = storage.Client()
            logger.info("Using Application Default Credentials for GCS.")


        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        logger.info(f"Uploading {source_file_path} to gs://{bucket_name}/{destination_blob_name}")
        blob.upload_from_filename(source_file_path)

        # Make the blob publicly readable (optional, depending on use case)
        # blob.make_public()

        # Construct the public URL (this format works for publicly readable objects)
        # If not public, you might generate a signed URL instead.
        public_url = f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"

        logger.info(f"File uploaded successfully. Public URL: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Error uploading file {source_file_path} to GCS bucket {bucket_name}: {e}")
        return None

def store_processed_content(
    processed_data: List[ProcessedContent],
    base_path: str = "research_dataset/phase1"
) -> List[ProcessedContent]:
    """
    Stores a list of ProcessedContent objects in GCS.

    Each item's markdown content is saved as a separate file.

    Args:
        processed_data: A list of ProcessedContent objects.
        base_path: The base path within the GCS bucket to store the data.

    Returns:
        The list of ProcessedContent objects with updated gcs_storage_link fields.
    """
    if not processed_data:
        logger.warning("No processed data to store.")
        return []

    updated_processed_data = []
    temp_dir = Path("./temp_gcs_uploads") # Use a temporary local directory

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)

        for item in processed_data:
            # Create a unique blob name based on source URL or title
            # Sanitize URL to create a valid file path
            # Replace non-alphanumeric characters with underscores
            sanitized_url = re.sub(r'[^a-zA-Z0-9_\-.]', '_', str(item.source_url))
            # Ensure it's not too long and is unique
            blob_name = f"{base_path}/{sanitized_url[:100]}_{hash(item.source_url)}.md"

            temp_file_path = temp_dir / f"{hash(item.source_url)}.md"

            try:
                with open(temp_file_path, "w", encoding="utf-8") as f:
                    f.write(item.full_text_markdown)

                gcs_link = upload_raw_artifact( # Updated function call
                    settings.GCS_BUCKET_NAME,
                    temp_file_path,
                    blob_name
                )

                if gcs_link:
                    item.gcs_storage_link = gcs_link
                    updated_processed_data.append(item)
                else:
                    logger.error(f"Failed to upload processed content for URL: {item.source_url}")
                    # Optionally, append the item without a link or add an error flag
                    updated_processed_data.append(item) # Keep the item even if upload failed

            except Exception as e:
                logger.error(f"Error preparing or uploading content for URL {item.source_url}: {e}")
                updated_processed_data.append(item) # Keep the item even if error

    finally:
        # Clean up temporary files
        for f in temp_dir.iterdir():
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {f}: {e}")
        try:
            temp_dir.rmdir()
        except OSError as e:
             logger.warning(f"Failed to remove temporary directory {temp_dir}: {e}. It might not be empty.")


    return updated_processed_data

# Example usage (for testing purposes)
# if __name__ == "__main__":
#     import asyncio
#     # Ensure .env is loaded if running directly for testing
#     # from dotenv import load_dotenv
#     # from pathlib import Path
#     # PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
#     # load_dotenv(PROJECT_ROOT / ".env")

#     # Create dummy ProcessedContent
#     dummy_processed_content = [
#         ProcessedContent(
#             source_url="http://example.com/dummy_paper_1",
#             original_metadata=InitialSearchResult(link="http://example.com/dummy_paper_1"),
#             title="Dummy Paper 1",
#             full_text_markdown="# Dummy Paper 1\n\nThis is some dummy content for testing GCS upload."
#         ),
#         ProcessedContent(
#             source_url="http://example.com/dummy_paper_2",
#             original_metadata=InitialSearchResult(link="http://example.com/dummy_paper_2"),
#             title="Dummy Paper 2",
#             full_text_markdown="# Dummy Paper 2\n\nMore dummy content."
#         ),
#     ]

#     # Ensure GCS_BUCKET_NAME is set in your .env for this to work
#     if settings.GCS_BUCKET_NAME:
#         print(f"Attempting to store dummy data in GCS bucket: {settings.GCS_BUCKET_NAME}")
#         stored_data = store_processed_content(dummy_processed_content)
#         print("\nStored Data Results:")
#         for item in stored_data:
#             print(f"- URL: {item.source_url}, GCS Link: {item.gcs_storage_link}")
#     else:
#         print("GCS_BUCKET_NAME not found in .env. Skipping GCS storage test.")
