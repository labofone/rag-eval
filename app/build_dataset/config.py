"""
Configuration for the buildDataset feature.
Loads settings from a .env file in the project root.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Determine project root: app/build_dataset/config.py -> app/build_dataset -> app -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

class BuildDatasetSettings(BaseSettings):
    """
    Settings for the dataset building process.
    Reads values from environment variables or a .env file.
    """
    SERPAPI_API_KEY: Optional[str] = None
    GCS_BUCKET_NAME: Optional[str] = None
    GCS_PROJECT: Optional[str] = None # Optional: if not using Application Default Credentials (ADC)
    # GCS_SERVICE_ACCOUNT_FILE: Optional[str] = None # Optional: path to service account key file for GCS

    PLAYWRIGHT_MCP_URL: Optional[str] = "http://localhost:8070/extract" # Default, can be overridden by .env
    
    TOP_N_RESULTS_TO_FETCH: int = 5
    MAX_RETRIES_PER_STEP: int = 2

    # model_config allows pydantic to load from .env file
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding='utf-8',
        extra='ignore' # Ignore extra fields in .env not defined in the model
    )

settings = BuildDatasetSettings()

# Example of how to access a setting:
# from app.build_dataset.config import settings
# api_key = settings.SERPAPI_API_KEY
