from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .db.mongo import ai_responses, notification_logs, sensor_readings, weather_data
from .services.orchestrator import breaker
from .services.prediction import predict_watering

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

DEVICE_ONLINE_SECONDS = 180   # online = sent a reading in the last 3 minutes (use about 3x the publish interval)
MAX_HISTORY_POINTS = 240


def _utc(dt):
    """MongoDB returns naive UTC datetimes; make them explicit so browsers read them correctly."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _latest(collection, query=None):
    return collection.find_one(query or {}, {"_id": 0}, sort=[("timestamp", -1)])


@router.get("/devices")
def devices():
    return sorted(sensor_readings.distinct("device_id"))


@router.get("/snapshot")
def snapshot(device_id: Optional[str] = None, hours: int = Query(6, ge=1, le=24)):
    if not device_id:
        newest = sensor_readings.find_one({}, {"device_id": 1}, sort=[("received_at", -1)])
        if newest is None:
            raise HTTPException(status_code=404, detail="No readings found")
        device_id = newest["device_id"]

    latest = sensor_readings.find_one({"device_id": device_id}, {"_id": 0}, sort=[("received_at", -1)])
    if latest is None:
        raise HTTPException(status_code=404, detail=f"No readings for {device_id}")

    now = datetime.now(timezone.utc)
    last_seen = _utc(latest["received_at"])
    latest["received_at"] = last_seen.isoformat()
    seconds = (now - last_seen).total_seconds()

    rows = list(
        sensor_readings.find(
            {"device_id": device_id, "received_at": {"$gte": now - timedelta(hours=hours)}},
            {"_id": 0, "received_at": 1, "soil_moisture": 1, "temperature": 1, "humidity": 1},
        ).sort("received_at", 1)
    )
    if len(rows) > MAX_HISTORY_POINTS:
        step = -(-len(rows) // MAX_HISTORY_POINTS)
        thinned = rows[::step]
        if thinned[-1] is not rows[-1]:
            thinned.append(rows[-1])
        rows = thinned
    history = [
        {
            "t": _utc(r["received_at"]).isoformat(),
            "soil_moisture": r["soil_moisture"],
            "temperature": r["temperature"],
            "humidity": r["humidity"],
        }
        for r in rows
    ]

    return {
        "device_id": device_id,
        "server_time": now.isoformat(),
        "device": {
            "last_seen": last_seen.isoformat(),
            "seconds_since_last": round(seconds, 1),
            "online": seconds <= DEVICE_ONLINE_SECONDS,
        },
        "backend": {"status": "degraded" if breaker.is_open() else "online"},
        "latest": latest,
        "history": history,
        "care": _latest(ai_responses, {"device_id": device_id}),
        "weather": _latest(weather_data),
        "notifications": _latest(notification_logs),
        "prediction": predict_watering(device_id),
    }