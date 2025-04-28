import pytest
from httpx import AsyncClient

# Assuming your FastAPI app is in app/main.py
from app.main import app

@pytest.mark.asyncio
async def test_evaluate_batch():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {
            "query": "What is the capital of France?",
            "context": "Paris is the capital of France.",
            "response": "The capital of France is Paris.",
            "metrics": ["correctness", "faithfulness"]
        }
        response = await ac.post("/evaluate/batch", json=payload)
        assert response.status_code == 200
        assert "task_id" in response.json()
