from datetime import datetime, timezone
from pydantic import ValidationError

from ..db.mongo import sensor_readings
from ..models.sensor import SensorData


def process_sensor_data(raw: dict):
    try:
        reading = SensorData.model_validate(raw)
    except ValidationError as e:
        print("Invalid sensor data rejected:")
        print(e)
        return None

    document = reading.model_dump()
    document["received_at"] = datetime.now(timezone.utc)

    try:
        sensor_readings.insert_one(document)
    except Exception as e:
        print(f"Failed to save reading: {e}")
        return None

    print(
        f"Saved: {reading.device_id} | soil {reading.soil_moisture}% | "
        f"{reading.temperature}°C | hum {reading.humidity}%"
    )
    document.pop("_id", None)   # insert_one adds an ObjectId; remove it
    return document

def get_recent_readings(device_id: str, limit: int = 10) -> list[dict]:
    """Newest first."""
    cursor = (
        sensor_readings.find({"device_id": device_id}, {"_id": 0})
        .sort("received_at", -1)
        .limit(limit)
    )
    return list(cursor)