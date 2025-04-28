import pytest
from httpx import AsyncClient

# Assuming your FastAPI app is in app/main.py
from app.main import app

@pytest.mark.asyncio
async def test_get_result():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # First, submit an evaluation task to get a task_id
        payload = {
            "query": "What is the capital of Germany?",
            "context": "Berlin is the capital of Germany.",
            "response": "The capital of Germany is Berlin.",
            "metrics": ["relevancy"]
        }
        submit_response = await ac.post("/evaluate/batch", json=payload)
        assert submit_response.status_code == 200
        task_id = submit_response.json()["task_id"]

        # Then, retrieve the result using the task_id
        result_response = await ac.get(f"/results/{task_id}")
        assert result_response.status_code == 200
        # The actual result structure will depend on the Celery task output,
        # but we can at least check for a status or the result itself.
        # TODO: Add more specific assertions based on expected result structure
