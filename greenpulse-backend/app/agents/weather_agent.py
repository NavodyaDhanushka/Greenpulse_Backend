import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, Optional

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..config import settings
from ..db.mongo import weather_data

API_URL = "https://api.open-meteo.com/v1/forecast"
NO_ALERT = "No weather alerts for your plant."

_lock = threading.Lock()
_cache: dict = {"data": None, "fetched_at": 0.0}


# ---------- Alert rules: code decides, the LLM only phrases ----------

_ORDER = ["NONE", "ADVISORY", "WARNING"]


def _alert_rules(raw: dict, placement: Optional[str] = None) -> tuple[str, list[str]]:
    """Deterministic thresholds. Returns (alert_level, reasons)."""
    placement = placement or settings.plant_placement
    mm = raw["rain_expected_mm_24h"]
    prob = raw["rain_probability_max_24h"]
    tmax = raw["temp_max_24h"]
    in_h = raw["rain_expected_in_hours"]
    when = f", around {in_h}h from now" if in_h is not None else ""

    level = "NONE"
    reasons: list[str] = []

    def raise_to(new: str, reason: str):
        nonlocal level
        if _ORDER.index(new) > _ORDER.index(level):
            level = new
        reasons.append(reason)

    # Rain only matters for a plant that is outdoors
    if placement == "outdoor":
        if mm >= 10 and prob >= 60:
            raise_to("WARNING", f"heavy rain expected ({mm} mm, up to {prob}% chance{when})")
        elif mm >= 2 and prob >= 50:
            raise_to("ADVISORY", f"moderate rain expected ({mm} mm, up to {prob}% chance{when})")

    # Heat matters for both
    if tmax >= 35 and placement == "outdoor":
        raise_to("WARNING", f"very hot weather expected (up to {tmax} C)")
    elif tmax >= 32:
        raise_to("ADVISORY", f"hot weather expected (up to {tmax} C), the soil will dry faster")

    return level, reasons


# ---------- LLM summarization ----------

class WeatherSummary(BaseModel):
    summary: str = Field(
        description="One or two plain sentences (max 45 words) with the temperature range and the rain outlook"
    )
    garden_alert: str = Field(
        description="One short sentence of advice based on the alert reasons, or the standard no-alert sentence"
    )


SYSTEM_PROMPT = """You are the Weather Agent of GreenPulse, an indoor plant care system.
You receive the current conditions and a 24-hour forecast (from Open-Meteo) for the plant's
location, whether the plant is kept indoors or outdoors, and a list of alert reasons that
were already decided by fixed rules.

Write two things:
1. summary: one or two plain sentences (max 45 words). ALWAYS state the temperature range and
   the rain outlook with the real numbers (chance, amount, timing). Describe less than 2 mm in
   total as light rain.
2. garden_alert: if the alert reasons are not "none", one short sentence turning those reasons
   into advice for this plant's placement. Mention only what the reasons say. If they are
   "none", write exactly: No weather alerts for your plant.

Rules:
- Use only the numbers given. Never invent values, times or places.
- For an INDOOR plant, rain outside does not water it, so never suggest watering less because
  of rain outside.
- Stay calm and factual."""

HUMAN_PROMPT = """Plant placement: {placement}
Now: {condition}, {temp} C, humidity {hum} %, rain right now {rain_now} mm.
Next 24 h: temperature {tmin} to {tmax} C; rain probability up to {prob} %;
expected rain {mm} mm in total; rain likely in {rain_in}.
Alert reasons: {reasons}

Write the summary and the garden alert."""


@lru_cache(maxsize=1)
def _get_chain():
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
        timeout=20,
        max_retries=1,
    )
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
    )
    return prompt | llm.with_structured_output(WeatherSummary)


def summarize_weather(raw: dict, placement: Optional[str] = None) -> dict:
    placement = placement or settings.plant_placement
    level, reasons = _alert_rules(raw, placement)
    in_hours = raw["rain_expected_in_hours"]

    s = _get_chain().invoke(
        {
            "placement": placement,
            "condition": raw["condition"],
            "temp": raw["temperature"],
            "hum": raw["humidity"],
            "rain_now": raw["rain_now_mm"],
            "tmin": raw["temp_min_24h"],
            "tmax": raw["temp_max_24h"],
            "prob": raw["rain_probability_max_24h"],
            "mm": raw["rain_expected_mm_24h"],
            "rain_in": f"about {in_hours}h" if in_hours is not None else "not expected",
            "reasons": "; ".join(reasons) if reasons else "none",
        }
    )
    return {
        "summary": s.summary,
        "garden_alert": s.garden_alert if reasons else NO_ALERT,  # fixed text when no alert
        "alert_level": level,
        "reasons": reasons,
    }


# ---------- Open-Meteo fetching ----------

def _describe(code: int) -> str:
    if code == 0:
        return "clear sky"
    if code in (1, 2, 3):
        return "partly cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67:
        return "rain"
    if 71 <= code <= 77:
        return "snow"
    if 80 <= code <= 82:
        return "rain showers"
    if code >= 95:
        return "thunderstorm"
    return "cloudy"


def _fetch() -> dict:
    resp = httpx.get(
        API_URL,
        params={
            "latitude": settings.plant_latitude,
            "longitude": settings.plant_longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
            "hourly": "precipitation_probability,precipitation,temperature_2m",
            "forecast_days": 2,
            "timezone": "auto",
        },
        timeout=10,
    )
    resp.raise_for_status()
    j = resp.json()

    cur = j["current"]
    hourly = j["hourly"]

    # First forecast hour at or after "now", then the next 24 hours
    now_hour = cur["time"][:13] + ":00"
    start = next((i for i, t in enumerate(hourly["time"]) if t >= now_hour), 0)
    probs = [p or 0 for p in hourly["precipitation_probability"][start:start + 24]]
    mm = [m or 0 for m in hourly["precipitation"][start:start + 24]]
    temps = [t for t in hourly["temperature_2m"][start:start + 24] if t is not None]

    max_prob = max(probs) if probs else 0
    total_mm = round(sum(mm), 1)
    rain_in_hours = next((i for i, p in enumerate(probs) if p >= 50), None)
    condition = _describe(cur["weather_code"])

    raw_summary = (
        f"{condition}, {cur['temperature_2m']} C outside, "
        f"humidity {cur['relative_humidity_2m']}%. "
        f"Next 24h: up to {max_prob}% chance of rain, about {total_mm} mm"
    )
    if rain_in_hours is not None:
        raw_summary += f", rain likely in about {rain_in_hours}h"
    raw_summary += "."

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "condition": condition,
        "temperature": cur["temperature_2m"],
        "humidity": cur["relative_humidity_2m"],
        "rain_now_mm": cur["precipitation"],
        "temp_min_24h": min(temps) if temps else cur["temperature_2m"],
        "temp_max_24h": max(temps) if temps else cur["temperature_2m"],
        "rain_probability_max_24h": max_prob,
        "rain_expected_mm_24h": total_mm,
        "rain_expected_in_hours": rain_in_hours,
        "raw_summary": raw_summary,
    }


# ---------- Public function with caching ----------

def get_weather() -> Optional[dict]:
    """Cached weather. Returns stale data if the API fails, None if there is none."""
    with _lock:
        age = time.monotonic() - _cache["fetched_at"]
        if _cache["data"] is not None and age < settings.weather_cache_seconds:
            return _cache["data"]

        try:
            data = _fetch()
        except Exception as e:
            print(f"Weather Agent failed: {e}")
            return _cache["data"]  # stale or None

        try:
            data.update(summarize_weather(data), summary_source="llm")
        except Exception as e:
            print(f"Weather Agent: LLM summary failed, using plain summary: {e}")
            level, reasons = _alert_rules(data)
            data.update(
                summary=data["raw_summary"],
                garden_alert=("; ".join(reasons).capitalize() + "." if reasons else NO_ALERT),
                alert_level=level,
                reasons=reasons,
                summary_source="rule-based",
            )

        _cache["data"] = data
        _cache["fetched_at"] = time.monotonic()

        try:
            weather_data.insert_one(dict(data))  # copy: insert_one adds _id
        except Exception as e:
            print(f"Failed to save weather: {e}")

        print(f"Weather updated ({data['summary_source']}, {data['alert_level']}): {data['summary']}")
        return data