from fastapi import APIRouter, Depends
from app.schemas.metric import MetricRecommendationRequest, MetricRecommendationResponse
from app.services.metric_recommendation import get_metric_recommendations
from typing import Optional

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.post("/recommend", response_model=MetricRecommendationResponse)
async def recommend_metrics(request: MetricRecommendationRequest):
    """Endpoint for getting recommended evaluation metrics based on natural language query"""
    return await get_metric_recommendations(request)
