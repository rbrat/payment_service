from fastapi import FastAPI

from app.api.v1.payments import router as payments_router

app = FastAPI(title="Payment Processing Service", version="1.0.0")
app.include_router(payments_router)
