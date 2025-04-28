from ragas.metrics import answer_relevancy, faithfulness, context_relevancy
from ragas import evaluate
from app.celery import celery_app

@celery_app.task
def evaluate_rag_pipeline(context, response):
    return evaluate(
        response,
        metrics=[
            answer_relevancy,
            faithfulness,
            context_relevancy
        ],
        data={
            'context': [context],
            'response': [response]
        }
    )
