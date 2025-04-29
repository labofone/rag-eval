import json
from datetime import datetime, timedelta
from redis import Redis
from ragas.metrics import answer_relevancy, faithfulness, context_relevancy
from ragas import evaluate
from app.celery import celery_app
from app.config.settings import settings
from app.schemas.result import EvaluationResult

# Initialize Redis client
redis_client = Redis.from_url(settings.REDIS_URL)

@celery_app.task
def evaluate_rag_pipeline(query, context, response, metrics_list, simulate_failure=False):
    if simulate_failure:
        raise ValueError("Simulated task failure for testing")

    # Map metric names to Ragas metric objects
    ragas_metrics = []
    if "answer_relevancy" in metrics_list:
        ragas_metrics.append(answer_relevancy)
    if "faithfulness" in metrics_list:
        ragas_metrics.append(faithfulness)
    if "context_relevancy" in metrics_list:
        ragas_metrics.append(context_relevancy)
    # Add other metrics here as they are supported

    # Perform Ragas evaluation
    result = evaluate(
        response,
        metrics=ragas_metrics,
        data={
            'query': [query],
            'context': [context],
            'response': [response]
        }
    )

    # Store result in Redis
    task_id = evaluate_rag_pipeline.request.id
    evaluation_result = EvaluationResult(
        task_id=task_id,
        metrics=result.to_pandas().iloc[0].to_dict(),
        created_at=datetime.utcnow()
    )
    redis_client.setex(
        task_id,
        timedelta(hours=1), # Store results for 1 hour
        json.dumps(evaluation_result.model_dump(), default=str)
    )

    return task_id
