from datetime import datetime, timezone


def basic_care_decision(reading: dict) -> dict:
    soil = reading["soil_moisture"]

    if soil < 25:
        urgency, message = "HIGH", "Soil is very dry. Water your plant now."
    elif soil < 40:
        urgency, message = "MEDIUM", "Soil is getting dry. Plan to water soon."
    else:
        urgency, message = "LOW", "Your plant is doing fine."

    return {
        "device_id": reading["device_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "urgency": urgency,
        "care_message": message,
        "soil_moisture": soil,
    }