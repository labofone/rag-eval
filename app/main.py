"""Main FastAPI application entrypoint.

This module creates and configures the FastAPI application instance,
including API routers and dependency injections.
"""

from fastapi import Depends, FastAPI

from app.dependencies import validate_api_key
from app.routers import evaluate, result

app = FastAPI()

app.include_router(evaluate.router, prefix="/evaluate", dependencies=[Depends(validate_api_key)])
app.include_router(result.router, prefix="/result", dependencies=[Depends(validate_api_key)])
