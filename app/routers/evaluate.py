from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from app.tasks.evaluation import evaluate_rag_pipeline
from app.config import settings

router = APIRouter()

class EvaluationPayload(BaseModel):
    query: str
    context: str
    response: str
    metrics: List[str]

class BatchEvaluationResponse(BaseModel):
    task_id: str

@router.post("/batch", response_model=BatchEvaluationResponse, summary="Evaluate RAG pipeline in batch")
async def evaluate_batch(payload: EvaluationPayload):
    """
    Receives a batch of data for RAG pipeline evaluation.

    Args:
        payload (EvaluationPayload): The evaluation payload containing query, context, response, and metrics.

    Returns:
        dict: A dictionary containing the task ID of the evaluation job.
    """
    task = evaluate_rag_pipeline.delay(
        query=payload.query,
        context=payload.context,
        response=payload.response,
        metrics_list=payload.metrics
    )
    return {"task_id": task.id}
