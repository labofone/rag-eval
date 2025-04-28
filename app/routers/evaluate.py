from fastapi import APIRouter, Depends, HTTPException
from app.tasks.evaluation import evaluate_rag_pipeline
from app.config import settings

router = APIRouter()

@router.post("/batch")
async def evaluate_batch(payload: dict):
    task = evaluate_rag_pipeline.delay(
        context=payload['context'],
        response=payload['response']
    )
    return {"task_id": task.id}
