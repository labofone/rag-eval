from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any

class EvaluationResult(BaseModel):
    task_id: str
    metrics: Dict[str, float]
    created_at: datetime
    status: str = "completed"
