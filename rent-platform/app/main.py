from fastapi import FastAPI
from app.config import settings

app = FastAPI(title="Rent Platform")

@app.get("/")
async def root():
    return {"ok": True, "env": settings.ENV}

@app.get("/health")
async def health():
    return {"status": "healthy"}