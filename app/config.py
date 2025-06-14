"""Application configuration settings.

This module defines the application's configuration settings.
"""

from pydantic import RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings and configuration.

    Attributes:
        REDIS_URL: Redis connection URL
        RAGAS_THRESHOLD: Threshold for RAG evaluation metrics
        API_KEY: Optional API key for authentication

    """

    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379")  # Explicitly construct RedisDsn
    RAGAS_THRESHOLD: float = 0.7
    API_KEY: str | None = None  # Make API_KEY optional

    class Config:
        """Configuration for settings loading.

        Attributes:
            env_file: Path to environment variable file

        """

        env_file = ".env"


settings = Settings()
