from fastapi import APIRouter
from celery.result import AsyncResult
from app.celery import celery_app

router = APIRouter()

@router.get("/{task_id}", summary="Retrieve evaluation result by task ID")
async def get_result(task_id: str):
    """
    Retrieves the evaluation result for a given task ID.

    Args:
        task_id (str): The ID of the evaluation task.

    Returns:
        dict: The evaluation result if the task is complete, otherwise the status of the task.
    """
    task = AsyncResult(task_id, app=celery_app)
    if not task.ready():
        return {"status": "processing"}
    return task.result
