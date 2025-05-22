"""Tests for the evaluation endpoints.

This module contains tests for the RAG pipeline evaluation API endpoints,
including authentication and various metric combinations.
"""

from fastapi import status
from httpx import AsyncClient
import pytest

# Placeholder API Key for testing
TEST_API_KEY = "test_api_key"

# Base payload for evaluation tests
BASE_PAYLOAD = {
    "query": "What is the capital of France?",
    "context": "Paris is the capital of France.",
    "response": "The capital of France is Paris.",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metrics", "headers", "expected_status", "expected_response_detail"),
    [
        # Test case for all metrics with valid API key
        (["correctness", "faithfulness", "context_relevancy"], {"X-API-Key": TEST_API_KEY}, status.HTTP_200_OK, None),
        # Test case for a subset of metrics with valid API key
        (["answer_relevancy"], {"X-API-Key": TEST_API_KEY}, status.HTTP_200_OK, None),
        # Test case for no API key
        (["correctness", "faithfulness"], None, status.HTTP_401_UNAUTHORIZED, "Not authenticated"),
        # Test case for invalid API key
        (
            ["correctness", "faithfulness"],
            {"X-API-Key": "invalid_key"},
            status.HTTP_401_UNAUTHORIZED,
            "Invalid API Key",
        ),
    ],
)
async def test_evaluate_batch(
    metrics: list[str],
    headers: dict[str, str] | None,
    expected_status: int,
    expected_response_detail: str | None,
) -> None:
    """Test the batch evaluation endpoint with different metrics and authentication scenarios.

    Args:
        metrics: List of evaluation metrics to request
        headers: Request headers including API key
        expected_status: Expected HTTP status code
        expected_response_detail: Expected error detail message if any

    Test cases:
        - All metrics with valid API key
        - Subset of metrics with valid API key
        - No API key (unauthorized)
        - Invalid API key

    """
    async with AsyncClient(base_url="http://test") as ac:
        payload_data = {
            "query": BASE_PAYLOAD["query"],
            "context": BASE_PAYLOAD["context"],
            "response": BASE_PAYLOAD["response"],
            "metrics": metrics,
        }
        response = await ac.post("/evaluate/batch", json=payload_data, headers=headers)

        assert response.status_code == expected_status

        if expected_status == status.HTTP_200_OK:
            assert "task_id" in response.json()
        else:
            assert response.json() == {"detail": expected_response_detail}
