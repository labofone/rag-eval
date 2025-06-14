"""Schemas for RAG evaluation results.

This module defines the Pydantic models used for representing evaluation results.
"""

from datetime import datetime

from pydantic import BaseModel


class EvaluationResult(BaseModel):
    """Schema for RAG evaluation results.

    Attributes:
        task_id: Unique identifier of the evaluation task
        metrics: Dictionary of evaluation metric names to their scores
        created_at: Timestamp of when the result was created
        status: Status of the evaluation task, defaults to "completed"

    """

    task_id: str
    metrics: dict[str, float]
    created_at: datetime
    status: str = "completed"
