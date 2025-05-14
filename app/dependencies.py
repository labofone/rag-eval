"""Dependency injection and validation functions.

This module contains dependency injection functions for the application, including
API key validation and security configurations.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key")


def validate_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Validate the provided API key against the configured value.

    Args:
        api_key: The API key extracted from the request headers.

    Returns:
        str: The validated API key.

    Raises:
        HTTPException: If the API key is invalid or missing.

    """
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key
