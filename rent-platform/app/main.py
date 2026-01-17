from fastapi import FastAPI

app = FastAPI(title="Rent Platform")

@app.get("/")
async def root():
    return {"status": "ok", "service": "rent-platform"}