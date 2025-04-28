from fastapi import APIRouter
from celery.result import AsyncResult
from app.celery import celery_app

router = APIRouter()

@router.get("/{task_id}")
async def get_result(task_id: str):
    task = AsyncResult(task_id, app=celery_app)
    if not task.ready():
        return {"status": "processing"}
    return task.result
