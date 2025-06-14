"""Router for retrieving evaluation results.

This module provides endpoints for retrieving RAG evaluation results from Redis storage.
"""

import json

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
from redis import Redis

from app.celery import celery_app
from app.config import settings  # Corrected import
from app.schemas.result import EvaluationResult

router = APIRouter()

# Initialize Redis client
redis_url_str: str = str(settings.REDIS_URL)
redis_client = Redis.from_url(redis_url_str)


@router.get("/{task_id}", summary="Retrieve evaluation result by task ID", response_model=EvaluationResult)
async def get_result(task_id: str) -> EvaluationResult:
    """Retrieve the evaluation result for a given task ID from Redis.

    Args:
        task_id (str): The ID of the evaluation task.

    Returns:
        EvaluationResult: The evaluation result if found in Redis.

    Raises:
        HTTPException: If the task result is not found or still processing.

    """
    # Attempt to fetch result from Redis
    result_data = redis_client.get(task_id)

    if result_data:
        # Deserialize and return the result
        try:
            result_dict = json.loads(result_data)
            return EvaluationResult(**result_dict)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="Failed to decode result from Redis") from e

    # If not in Redis, check Celery task status
    task = AsyncResult(task_id, app=celery_app)

    if task.ready():
        # Task is ready but result not in Redis (e.g., expired or error during storage)
        if task.successful():
            raise HTTPException(status_code=404, detail="Result not found in cache (may have expired)")
        raise HTTPException(status_code=500, detail=f"Task failed: {task.result}")
    # Task is still processing
    raise HTTPException(status_code=202, detail="Task is still processing")
