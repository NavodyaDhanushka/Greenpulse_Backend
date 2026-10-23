import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.weather_agent import summarize_weather

rain = {"condition": "rain", "temperature": 26, "humidity": 85, "rain_now_mm": 0.0,
        "temp_min_24h": 24, "temp_max_24h": 29, "rain_probability_max_24h": 90,
        "rain_expected_mm_24h": 18.0, "rain_expected_in_hours": 3}
heat = {"condition": "clear sky", "temperature": 34, "humidity": 40, "rain_now_mm": 0.0,
        "temp_min_24h": 28, "temp_max_24h": 36, "rain_probability_max_24h": 5,
        "rain_expected_mm_24h": 0.0, "rain_expected_in_hours": None}

cases = {
    "Outdoor plant, heavy rain": (rain, "outdoor"),
    "Indoor plant, same heavy rain": (rain, "indoor"),
    "Indoor plant, heatwave": (heat, "indoor"),
    "Outdoor plant, heatwave": (heat, "outdoor"),
}

for name, (raw, placement) in cases.items():
    out = summarize_weather(raw, placement)
    print(f"\n=== {name} ===")
    print("Summary:", out["summary"])
    print("Alert  :", out["alert_level"], "-", out["garden_alert"])