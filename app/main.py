from fastapi import FastAPI
from app.api.call_handler import router as call_router

app = FastAPI(title="KRPH Voicebot")

app.include_router(call_router)

@app.get("/health")
async def health():
    return {"status": "ok"}