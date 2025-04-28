from fastapi import FastAPI, Depends
from app.routers import evaluate, result
from app.dependencies import validate_api_key

app = FastAPI()

app.include_router(evaluate.router, prefix="/evaluate", dependencies=[Depends(validate_api_key)])
app.include_router(result.router, prefix="/result", dependencies=[Depends(validate_api_key)])
