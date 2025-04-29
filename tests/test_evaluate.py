import pytest
from httpx import AsyncClient

# Assuming your FastAPI app is in app/main.py
from app.main import app

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
    "metrics, headers, expected_status, expected_response_detail",
    [
        # Test case for all metrics with valid API key
        (["correctness", "faithfulness", "context_relevancy"], {"X-API-Key": TEST_API_KEY}, 200, None),
        # Test case for a subset of metrics with valid API key
        (["answer_relevancy"], {"X-API-Key": TEST_API_KEY}, 200, None),
        # Test case for no API key
        (["correctness", "faithfulness"], None, 401, "Not authenticated"),
        # Test case for invalid API key
        (["correctness", "faithfulness"], {"X-API-Key": "invalid_key"}, 401, "Invalid API Key"),
    ]
)
async def test_evaluate_batch(metrics, headers, expected_status, expected_response_detail):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = BASE_PAYLOAD.copy()
        payload["metrics"] = metrics
        response = await ac.post("/evaluate/batch", json=payload, headers=headers)

        assert response.status_code == expected_status

        if expected_status == 200:
            assert "task_id" in response.json()
        else:
            assert response.json() == {"detail": expected_response_detail}
