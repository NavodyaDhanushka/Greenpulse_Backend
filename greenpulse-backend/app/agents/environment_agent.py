from functools import lru_cache
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..config import settings


class EnvironmentAssessment(BaseModel):
    urgency: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        description="How urgently the plant needs care, judged from the sensors only"
    )
    watering_needed: bool = Field(description="True if the plant should be watered now")
    plant_condition: str = Field(description="One short sentence describing the plant's current condition")
    reasoning: str = Field(description="Two sentences max: which readings and trends led to this decision")
    care_message: str = Field(description="A friendly, specific instruction for the owner, one or two sentences")


SYSTEM_PROMPT = """You are the Environment Agent of GreenPulse, an indoor plant care system.
You receive recent readings from a capacitive soil moisture sensor (0-100 %, higher = wetter)
and a DHT22 temperature/humidity sensor. You judge the plant from these sensors ONLY.

Guidelines:
- Soil moisture below 25 % is dry: urgency HIGH and watering_needed true. From 25 % to 40 % urgency is MEDIUM (plan to water soon) and watering_needed is false. Above 40 % urgency is LOW.
- A falling soil moisture trend, high temperature (above 30 C) or low humidity (below 40 %) make the plant dry out faster. They may raise urgency from LOW to MEDIUM, but never to HIGH unless the soil moisture is below 25 %.
- Very high soil moisture (above 80 %) means do NOT water; mention overwatering risk.
- Base your answer only on the data given. If there is little history, say so briefly.
- Do not invent weather or plant species."""

HUMAN_PROMPT = """Device: {device_id}
Readings analysed: {count} (oldest to newest)

Latest: soil {soil_now}%, temperature {temp_now} C, humidity {hum_now}%
Soil moisture trend over this window: {soil_trend}
Average temperature: {temp_avg} C, average humidity: {hum_avg}%

Assess the plant's current condition."""


def build_summary(readings_newest_first: list[dict]) -> dict:
    readings = list(reversed(readings_newest_first))  # oldest first
    latest = readings[-1]
    soil = [r["soil_moisture"] for r in readings]
    temp = [r["temperature"] for r in readings]
    hum = [r["humidity"] for r in readings]

    if len(soil) < 2:
        trend = "not enough history yet"
    else:
        change = soil[-1] - soil[0]
        if abs(change) < 2:
            trend = f"stable ({soil[0]:.0f}% -> {soil[-1]:.0f}%)"
        elif change < 0:
            trend = f"falling ({soil[0]:.0f}% -> {soil[-1]:.0f}%)"
        else:
            trend = f"rising ({soil[0]:.0f}% -> {soil[-1]:.0f}%)"

    return {
        "device_id": latest["device_id"],
        "count": len(readings),
        "soil_now": latest["soil_moisture"],
        "temp_now": latest["temperature"],
        "hum_now": latest["humidity"],
        "soil_trend": trend,
        "temp_avg": round(sum(temp) / len(temp), 1),
        "hum_avg": round(sum(hum) / len(hum), 1),
    }


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
    return prompt | llm.with_structured_output(EnvironmentAssessment)


def assess_environment(readings_newest_first: list[dict]) -> EnvironmentAssessment:
    return _get_chain().invoke(build_summary(readings_newest_first))