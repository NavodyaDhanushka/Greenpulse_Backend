import random

from ..db.mongo import ai_responses
from .validation import DAMP_BELOW, DRY_BELOW, WET_ABOVE, rule_baseline

_STATIC_QUOTES = [
    "A little water, a little patience, and the leaves will remember.",
    "Even in quiet rooms, green things keep their own slow hours.",
    "Tend the soil gently, and the plant will answer in leaves.",
    "Care is a small, steady rain.",
    "What we water in silence grows in its own time.",
    "Where light is kind and water is measured, roots rest easy.",
]


def get_fallback_quote():
    """A quote from a recent good AI response in MongoDB, or from the built-in list."""
    try:
        docs = list(
            ai_responses.find(
                {"source": "care-agent", "quote": {"$nin": [None, ""]}}, {"quote": 1}
            )
            .sort("timestamp", -1)
            .limit(10)
        )
        if docs:
            return random.choice(docs)["quote"], "cached-ai"
    except Exception as e:
        print(f"Could not read a cached quote: {e}")
    return random.choice(_STATIC_QUOTES), "static"


def estimate_soil_trend(history):
    """Soil moisture change in % per hour (least squares), or None if there is too little data."""
    pts = [
        (h["received_at"], float(h["soil_moisture"]))
        for h in history
        if h.get("received_at") is not None
    ]
    if len(pts) < 3:
        return None
    pts.sort(key=lambda p: p[0])
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 3600 for t, _ in pts]
    ys = [v for _, v in pts]
    if xs[-1] < 0.05:                      # less than about 3 minutes of data
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def hours_until_dry(soil: float, slope):
    if slope is None or slope >= -0.05:
        return None
    hours = (soil - DRY_BELOW) / (-slope)
    if hours <= 0 or hours > 72:
        return None
    return hours


def rule_based_care(reading: dict, history: list) -> dict:
    soil = float(reading["soil_moisture"])
    temp = float(reading["temperature"])
    urgency = rule_baseline(soil)
    slope = estimate_soil_trend(history)
    hours = hours_until_dry(soil, slope)

    if soil > WET_ABOVE:
        urgency, watering = "LOW", False
        message = f"Soil moisture is {soil:.0f}%, which is very wet. Do not water; let the soil dry out."
        condition = "The soil is very wet."
    elif urgency == "HIGH":
        watering = True
        message = f"Soil moisture is {soil:.0f}%, which is dry. Please water your plant now."
        condition = "The plant is dry and needs water."
    elif urgency == "MEDIUM":
        watering = False
        message = f"Soil moisture is {soil:.0f}% and getting dry. Plan to water soon."
        condition = "The soil is getting dry."
    else:
        watering = False
        message = f"Soil moisture is {soil:.0f}% and your plant is doing fine."
        condition = "The plant is in good condition."

    if hours is not None and urgency != "HIGH":
        message += f" At the current rate it will reach the dry level in about {hours:.0f} hours."
    if temp >= 32 and urgency != "LOW":
        message += f" It is {temp:.0f}\u00b0C, so the soil will dry faster."

    reasoning = f"Rule-based fallback because the AI service was unavailable. Soil moisture {soil:.0f}%"
    if slope is not None:
        reasoning += f", trend {slope:+.1f}% per hour"
    reasoning += "."

    quote, quote_source = get_fallback_quote()
    return {
        "urgency": urgency,
        "watering_needed": watering,
        "care_message": message,
        "quote": quote,
        "quote_source": quote_source,
        "plant_condition": condition,
        "reasoning": reasoning,
        "predicted_hours_until_dry": round(hours, 1) if hours is not None else None,
    }