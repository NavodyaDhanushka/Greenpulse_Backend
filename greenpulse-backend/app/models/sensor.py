from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class SensorData(BaseModel):
    # Unknown fields are ignored; both snake_case and camelCase names are accepted
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    device_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("device_id", "deviceId"),
    )
    soil_moisture: float = Field(
        ge=0, le=100,   # percent
        validation_alias=AliasChoices("soil_moisture", "soilMoisture"),
    )
    temperature: float = Field(ge=-40, le=80)    # DHT22 range
    humidity: float = Field(ge=0, le=100)        # percent
    timestamp: Optional[datetime] = None         # the ESP32 doesn't send one; received_at is used

    # Classification computed on the device itself (optional)
    soil_status: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("soil_status", "soilStatus"),
    )
    watering_priority: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("watering_priority", "wateringPriority"),
    )

    @field_validator("soil_status", "watering_priority", mode="before")
    @classmethod
    def _normalise(cls, v):
        # "moist " -> "MOIST"; blank -> None. Any value is accepted.
        return v.strip().upper() if isinstance(v, str) and v.strip() else None