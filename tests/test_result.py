import pytest
import time
from httpx import AsyncClient
from redis import Redis
from app.config.settings import settings

from app.main import app

# Initialize Redis client for test cleanup
redis_client = Redis.from_url(settings.REDIS_URL)

# Placeholder API Key for testing
TEST_API_KEY = "test_api_key"

# Base payload for evaluation tests
BASE_PAYLOAD = {
    "query": "Test query",
    "context": "Test context",
    "response": "Test response",
}


@pytest.fixture(autouse=True)
def cleanup_redis():
    """Fixture to clean up Redis before each test."""
    redis_client.flushdb()
    yield
    redis_client.flushdb()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_id_scenario, headers, expected_status, expected_response_detail",
    [
        # Test case for a task that is still processing
        ("processing", {"X-API-Key": TEST_API_KEY}, 202, "Task is still processing"),
        # Test case for a non-existent task ID
        ("non-existent", {"X-API-Key": TEST_API_KEY}, 404, "Result not found in cache (may have expired)"),
        # Test case for no API key
        ("any", None, 401, "Not authenticated"),
        # Test case for invalid API key
        ("any", {"X-API-Key": "invalid_key"}, 401, "Invalid API Key"),
    ]
)
async def test_get_result_scenarios(task_id_scenario, headers, expected_status, expected_response_detail):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        task_id = "some-task-id" # Default task ID

        if task_id_scenario == "processing":
            # Submit a task to get a real task_id for the processing scenario
            payload = BASE_PAYLOAD.copy()
            payload["metrics"] = ["relevancy"] # Use a quick metric
            submit_response = await ac.post("/evaluate/batch", json=payload, headers=headers)
            assert submit_response.status_code == 200
            task_id = submit_response.json()["task_id"]
            # Do not wait for the task to complete

        elif task_id_scenario == "non-existent":
             task_id = "non-existent-task-id" # Use a non-existent ID

        # For "any" scenario, the default task_id is fine as authentication fails before checking task status

        result_response = await ac.get(f"/results/{task_id}", headers=headers)

        assert result_response.status_code == expected_status
        assert result_response.json() == {"detail": expected_response_detail}


@pytest.mark.asyncio
async def test_get_result_completed():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Submit a task
        payload = BASE_PAYLOAD.copy()
        payload["metrics"] = ["answer_relevancy", "faithfulness", "context_relevancy"]
        headers = {"X-API-Key": TEST_API_KEY}
        submit_response = await ac.post("/evaluate/batch", json=payload, headers=headers)
        assert submit_response.status_code == 200
        task_id = submit_response.json()["task_id"]

        # Wait for the task to complete (adjust time as needed for your Celery worker)
        # In a more comprehensive test , poll the Celery task status or use mocks
        time.sleep(5) # Adjust this sleep time based on how long task takes

        # Retrieve the result - should be completed and stored in Redis
        result_response = await ac.get(f"/results/{task_id}", headers=headers)
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["task_id"] == task_id
        # The status field is not part of the EvaluationResult schema, remove this assertion
        # assert result_data["status"] == "completed"
        assert "metrics" in result_data
        assert isinstance(result_data["metrics"], dict)
        # Check for expected metrics keys (assuming these are always returned by ragas)
        assert "answer_relevancy" in result_data["metrics"]
        assert "faithfulness" in result_data["metrics"]
        assert "context_relevancy" in result_data["metrics"]


# TODO: Add a test case for task failure if possible with Celery testing setup
# This might require mocking the Celery task to force a failure state.
