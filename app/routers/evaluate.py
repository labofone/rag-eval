"""Evaluation router.

This module defines the FastAPI router for evaluation endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.tasks.evaluation import evaluate_rag_pipeline

router = APIRouter()


class EvaluationPayload(BaseModel):
    """Data model for RAG pipeline evaluation request.

    Attributes:
        query: The user query to evaluate
        context: The context retrieved by the RAG system
        response: The generated response to evaluate
        metrics: List of evaluation metrics to apply

    """

    query: str
    context: str
    response: str
    metrics: list[str]


class BatchEvaluationResponse(BaseModel):
    """Response model for batch evaluation requests.

    Attributes:
        task_id: The ID of the created evaluation task

    """

    task_id: str


@router.post("/batch", response_model=BatchEvaluationResponse, summary="Evaluate RAG pipeline in batch")
async def evaluate_batch(payload: EvaluationPayload) -> BatchEvaluationResponse:
    """Receives a batch of data for RAG pipeline evaluation.

    Args:
        payload (EvaluationPayload): The evaluation payload containing query, context, response, and metrics.

    Returns:
        dict: A dictionary containing the task ID of the evaluation job.

    """
    task = evaluate_rag_pipeline.delay(
        query=payload.query, context=payload.context, response=payload.response, metrics_list=payload.metrics
    )
    return BatchEvaluationResponse(task_id=task.id)
