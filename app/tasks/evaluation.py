"""Celery tasks for RAG pipeline evaluation.

This module provides asynchronous tasks for evaluating RAG pipeline results using Ragas metrics.
"""

from datetime import UTC, datetime, timedelta  # Added UTC
import json

from celery import Task
from pydantic import BaseModel
from ragas import evaluate  # type: ignore[import-untyped]
from ragas.metrics import answer_relevancy, context_relevancy, faithfulness  # type: ignore[import-untyped]
from redis import Redis

from app.celery import celery_app
from app.config import settings  # Changed import path
from app.schemas.result import EvaluationResult

# Initialize Redis client
redis_client = Redis.from_url(str(settings.REDIS_URL))  # Added str()


class EvaluationTaskPayload(BaseModel):
    """Schema for RAG evaluation task input.

    Attributes:
        query: User query that was passed to the RAG system
        context: Context retrieved by the RAG system
        response: Generated response to evaluate
        metrics_list: List of metric names to evaluate

    """

    query: str
    context: str
    response: str
    metrics_list: list[str]


@celery_app.task(bind=True)  # Bind task to self
def evaluate_rag_pipeline(  # Added type hints
    self: Task, payload: EvaluationTaskPayload, simulate_failure: bool = False
) -> str:
    """Run RAG pipeline evaluation using specified metrics.

    Args:
        self: The Celery task instance
        payload: Request payload containing query, context, response and metrics to evaluate
        simulate_failure: If True, raises an error (used for testing)

    Returns:
        str: The task ID for retrieving the evaluation results

    Raises:
        ValueError: When simulate_failure is True

    """
    """Evaluate RAG pipeline output using requested metrics.

    Args:
        self: The Celery task instance
        payload: The evaluation task payload containing query, context, response and metrics
        simulate_failure: If True, raises an error to simulate task failure

    Returns:
        str: The ID of the task which can be used to retrieve results

    Raises:
        ValueError: If simulate_failure is True

    """
    if simulate_failure:
        raise ValueError

    # Map metric names to Ragas metric objects
    ragas_metrics = []
    if "answer_relevancy" in payload.metrics_list:
        ragas_metrics.append(answer_relevancy)
    if "faithfulness" in payload.metrics_list:
        ragas_metrics.append(faithfulness)
    if "context_relevancy" in payload.metrics_list:
        ragas_metrics.append(context_relevancy)
    # Add other metrics here as they are supported

    # Perform Ragas evaluation
    result = evaluate(
        payload.response,
        metrics=ragas_metrics,
        data={"query": [payload.query], "context": [payload.context], "response": [payload.response]},
    )

    # Store result in Redis
    task_id = self.request.id  # Use self.request.id
    evaluation_result = EvaluationResult(
        task_id=task_id,
        metrics=result.to_pandas().iloc[0].to_dict(),
        created_at=datetime.now(UTC),  # Changed to datetime.now(UTC)
    )
    redis_client.setex(
        task_id,
        timedelta(hours=1),  # Store results for 1 hour
        json.dumps(evaluation_result.model_dump(), default=str),
    )

    return task_id
