# app/main.py
from fastapi import FastAPI

app = FastAPI(title="Rent Platform")

@app.get("/")
async def health():
    return {"status": "ok"}