from pydantic import BaseModel
from typing import List, Optional

class MetricRecommendationRequest(BaseModel):
    query: str
    use_case: Optional[str] = None
    constraints: Optional[List[str]] = None

class MetricRecommendationResponse(BaseModel):
    recommended_metrics: List[str]
    reasoning: str
    confidence: float
    fallback_metrics: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
