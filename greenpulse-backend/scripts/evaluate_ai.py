import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.care_agent import run_care_agent
from app.agents.environment_agent import assess_environment
from app.config import settings
from app.services.validation import rule_baseline, validate_care

RUNS = 5

WEATHER = {
    "summary": "partly cloudy, 25 to 31 C, up to 60% chance of light rain (2 mm) in about 8 hours.",
    "alert_level": "NONE", "garden_alert": "No weather alerts for your plant.",
    "rain_expected_in_hours": 8, "rain_probability_max_24h": 60, "rain_expected_mm_24h": 2.0,
    "temperature": 28, "humidity": 80, "temp_min_24h": 25, "temp_max_24h": 31, "rain_now_mm": 0.0,
}

# (name, soil readings oldest -> newest, temperature, humidity)
CASES = [
    ("Very dry",            [14, 12, 10], 28, 55),
    ("Dry",                 [30, 26, 22], 29, 45),
    ("Getting dry",         [38, 35, 32], 27, 60),
    ("Hot, getting dry",    [44, 41, 38], 34, 35),
    ("Fine, stable",        [55, 55, 55], 26, 65),
    ("Wet",                 [66, 68, 70], 25, 70),
    ("Waterlogged",         [90, 91, 92], 24, 80),
]

print(f"Placement: {settings.plant_placement} | {RUNS} runs per case\n")
print(f"{'Case':<20}{'Soil':>5}  {'Rules':<8}{'AI urgencies':<42}{'Valid':>6}")

total = passed = agreed = 0
for name, trend, temp, hum in CASES:
    history = [
        {"device_id": "eval", "soil_moisture": s, "temperature": temp, "humidity": hum}
        for s in reversed(trend)           # newest first
    ]
    reading = history[0]
    soil = reading["soil_moisture"]
    baseline = rule_baseline(soil)
    urgencies, ok = [], 0

    for _ in range(RUNS):
        try:
            env = assess_environment(history)
            final = run_care_agent(env, reading, WEATHER, None)
            report = validate_care(final, env, reading, WEATHER, history, settings.plant_placement)
        except Exception as e:
            urgencies.append("ERROR")
            print(f"   error: {e!r}")
            continue
        urgencies.append(final.urgency)
        total += 1
        if report["passed"]:
            ok += 1
            passed += 1
        else:
            print(f"   rejected: {report['errors']}")
            print(f"   message : {final.care_message}")
        if final.urgency == baseline:
            agreed += 1

    # one row per case, printed after all the runs of that case
    print(f"{name:<20}{soil:>5}  {baseline:<8}{', '.join(urgencies):<42}{ok}/{RUNS}")

print(f"\nValidation passed: {passed}/{total}")
print(f"Agreement with threshold rules: {agreed}/{total}")