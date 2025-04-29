import pytest
import time
from httpx import AsyncClient
from redis import Redis
from app.config.settings import settings

from app.main import app

# Initialize Redis client for test cleanup
redis_client = Redis.from_url(settings.REDIS_URL)

@pytest.fixture(autouse=True)
def cleanup_redis():
    """Fixture to clean up Redis before each test."""
    redis_client.flushdb()
    yield
    redis_client.flushdb()

@pytest.mark.asyncio
async def test_get_result_processing():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Submit a task
        payload = {
            "query": "Test query",
            "context": "Test context",
            "response": "Test response",
            "metrics": ["relevancy"]
        }
        submit_response = await ac.post("/evaluate/batch", json=payload)
        assert submit_response.status_code == 200
        task_id = submit_response.json()["task_id"]

        # Immediately try to retrieve the result - should be processing
        result_response = await ac.get(f"/results/{task_id}")
        assert result_response.status_code == 202
        assert result_response.json() == {"detail": "Task is still processing"}

@pytest.mark.asyncio
async def test_get_result_completed():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Submit a task
        payload = {
            "query": "What is the capital of Germany?",
            "context": "Berlin is the capital of Germany.",
            "response": "The capital of Germany is Berlin.",
            "metrics": ["answer_relevancy", "faithfulness", "context_relevancy"]
        }
        submit_response = await ac.post("/evaluate/batch", json=payload)
        assert submit_response.status_code == 200
        task_id = submit_response.json()["task_id"]

        # Wait for the task to complete (adjust time as needed for your Celery worker)
        # In a real test suite, you might poll the Celery task status or use mocks
        time.sleep(5) # Adjust this sleep time based on how long your task takes

        # Retrieve the result - should be completed and stored in Redis
        result_response = await ac.get(f"/results/{task_id}")
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert result_data["task_id"] == task_id
        assert result_data["status"] == "completed"
        assert "metrics" in result_data
        assert isinstance(result_data["metrics"], dict)
        # Check for expected metrics keys (assuming these are always returned by ragas)
        assert "answer_relevancy" in result_data["metrics"]
        assert "faithfulness" in result_data["metrics"]
        assert "context_relevancy" in result_data["metrics"]


@pytest.mark.asyncio
async def test_get_result_not_found():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Try to retrieve a result for a non-existent task ID
        non_existent_task_id = "non-existent-task-id"
        result_response = await ac.get(f"/results/{non_existent_task_id}")
        assert result_response.status_code == 404
        assert result_response.json() == {"detail": "Result not found in cache (may have expired)"}

# TODO: Add a test case for task failure if possible with Celery testing setup
# This might require mocking the Celery task to force a failure state.
