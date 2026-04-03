from fastapi import FastAPI
from app.api import api_router

app = FastAPI(
    title="Async Payment Processing Service",
    description="Microservice for asynchronous payment processing",
    version="0.1.0",
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
