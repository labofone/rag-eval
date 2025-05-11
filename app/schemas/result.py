from datetime import datetime

from pydantic import BaseModel


class EvaluationResult(BaseModel):
    task_id: str
    metrics: dict[str, float]
    created_at: datetime
    status: str = "completed"
