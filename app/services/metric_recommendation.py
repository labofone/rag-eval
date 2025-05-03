import json
from typing import List, Tuple, Optional
from redis import Redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)
redis = Redis.from_url(settings.REDIS_URL)

RULES = {
    "factual": ["faithfulness", "answer_correctness"],
    "speed": ["latency@k", "tokens_per_second"],
    "diversity": ["diversity@k", "semantic_variety"]
}

def get_rule_based_metrics(query: str, use_case: Optional[str] = None) -> Tuple[List[str], float]:
    metrics = []
    for keyword, keyword_metrics in RULES.items():
        if keyword in query.lower():
            metrics.extend(keyword_metrics)
    if use_case and use_case in RULES:
        metrics.extend(RULES[use_case])
    confidence = min(1.0, len(metrics) * 0.33)
    return list(set(metrics)), confidence

async def get_llm_recommendation(query: str) -> List[str]:
    # Placeholder for LLM integration
    return []

async def get_metric_recommendations(request: dict) -> dict:
    try:
        cache_key = f"metric_rec:{hash(json.dumps(request))}"
        if cached := redis.get(cache_key):
            return json.loads(cached)
        
        metrics, confidence = get_rule_based_metrics(request['query'], request.get('use_case'))
        
        if confidence < 0.7:
            llm_metrics = await get_llm_recommendation(request['query'])
            metrics = list(set(metrics + llm_metrics))
            confidence = 0.8
        
        response = {
            "recommended_metrics": metrics,
            "reasoning": f"Recommended metrics for: {request['query']}",
            "confidence": confidence,
            "fallback_metrics": ["answer_relevance", "retrieval_recall"]
        }
        
        redis.set(cache_key, json.dumps(response), ex=86400)
        return response
        
    except Exception as e:
        logger.error(f"Metric recommendation failed: {str(e)}")
        return {
            "recommended_metrics": ["answer_relevance"],
            "reasoning": "Default fallback metrics",
            "confidence": 0.1
        }
