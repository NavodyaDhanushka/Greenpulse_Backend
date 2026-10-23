from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "greenpulse"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ai_min_interval_seconds: int = 60

    plant_latitude: float = 6.9271
    plant_longitude: float = 79.8612
    plant_placement: Literal["indoor", "outdoor"] = "indoor"
    weather_cache_seconds: int = 600

    gmail_enabled: bool = True
    notification_cache_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env")

    aws_iot_endpoint: str
    aws_iot_client_id: str = "greenpulse-backend"


settings = Settings()