from contextlib import asynccontextmanager
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from .dashboard_api import router as dashboard_router

from .db.mongo import init_db, close_db, sensor_readings, ai_responses
from .models.sensor import SensorData
from .mqtt.client import start_mqtt, stop_mqtt
from .services.sensor_service import process_sensor_data
from .services.ask import build_answer
from .services.prediction import predict_watering

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_mqtt()
    yield
    stop_mqtt()
    close_db()


app = FastAPI(title="GreenPulse Backend", lifespan=lifespan)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {"message": "GreenPulse Backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/sensors")
def receive_sensor_data(data: SensorData):
    """Manual test endpoint: same path as an MQTT message."""
    saved = process_sensor_data(data.model_dump())
    if saved is None:
        raise HTTPException(status_code=500, detail="Failed to save reading")
    return {"status": "success", "data": saved}


@app.get("/api/sensors/latest")
def latest_reading(device_id: Optional[str] = None):
    query = {"device_id": device_id} if device_id else {}
    doc = sensor_readings.find_one(query, {"_id": 0}, sort=[("received_at", -1)])
    if doc is None:
        raise HTTPException(status_code=404, detail="No readings found")
    return doc


@app.get("/api/sensors/history")
def reading_history(
    device_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    query = {"device_id": device_id} if device_id else {}
    cursor = sensor_readings.find(query, {"_id": 0}).sort("received_at", -1).limit(limit)
    return list(cursor)

@app.get("/api/ai/quality")
def ai_quality(limit: int = Query(200, ge=1, le=2000)):
    """Summary of how the AI agents have performed on the last `limit` responses."""
    docs = list(ai_responses.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
    if not docs:
        raise HTTPException(status_code=404, detail="No AI responses stored yet")

    by_source: dict = {}
    for d in docs:
        key = d.get("source", "unknown")
        by_source[key] = by_source.get(key, 0) + 1

    checked = [d for d in docs if "agrees_with_rules" in d]
    agree = sum(1 for d in checked if d["agrees_with_rules"])
    rejected = sum(1 for d in docs if (d.get("validation") or {}).get("rejected_errors"))
    degraded = sum(1 for d in docs if d.get("degraded"))
    latencies = [d["latency_seconds"] for d in docs if isinstance(d.get("latency_seconds"), (int, float))]

    return {
        "responses_analysed": len(docs),
        "by_source": by_source,
        "degraded_responses": degraded,
        "responses_with_rejected_output": rejected,
        "agreement_with_threshold_rules": f"{agree}/{len(checked)}" if checked else None,
        "average_latency_seconds": round(sum(latencies) / len(latencies), 1) if latencies else None,
    }

@app.get("/api/predict/watering")
def watering_prediction(device_id: Optional[str] = None):
    """Watering prediction from the stored readings (defaults to the newest device)."""
    if not device_id:
        newest = sensor_readings.find_one({}, {"device_id": 1}, sort=[("received_at", -1)])
        if newest is None:
            raise HTTPException(status_code=404, detail="No readings found")
        device_id = newest["device_id"]
    return predict_watering(device_id)


class AskBody(BaseModel):
    question: str = "Does my plant need watering today?"
    device_id: Optional[str] = None


@app.post("/api/ask")
def ask(body: AskBody):
    return build_answer(body.question, body.device_id)