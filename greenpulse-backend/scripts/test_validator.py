import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.validation import validate_care


def check(name, soil, urgency, watering, message, expect_pass):
    out = NS(
        urgency=urgency,
        watering_needed=watering,
        care_message=message,
        reasoning="Based on the sensor readings.",
        quote="Care is a small, steady rain.",
    )
    reading = {"soil_moisture": soil, "temperature": 26, "humidity": 60}
    r = validate_care(out, None, reading, None, [], "indoor")
    ok = r["passed"] == expect_pass
    print(("PASS" if ok else "FAIL"), "-", name, "" if ok else r["errors"])
    return ok


CASES = [
    # (name, soil, urgency, watering_needed, message, should_pass)
    ("says doesn't need watering", 55, "LOW", False,
     "Your plant is thriving and doesn't need watering right now. Enjoy its beauty!", True),
    ("says doesn't need any water", 55, "LOW", False,
     "Your plant is doing well and doesn't need any water right now.", True),
    ("says without needing to water", 55, "LOW", False,
     "Your plant is well-hydrated. Enjoy its beauty without needing to water for now!", True),
    ("says skip watering today", 70, "LOW", False,
     "The soil is moist, so skip watering today and check again tomorrow.", True),
    ("dry soil, water now", 20, "HIGH", True,
     "The soil is dry. Please water your plant now.", True),
    ("water now but watering_needed false", 55, "LOW", False,
     "Please water your plant right now to keep it healthy.", False),
    ("no need to water but watering_needed true", 20, "HIGH", True,
     "There is no need to water your plant today.", False),
    ("doesn't need water but watering_needed true", 20, "HIGH", True,
     "Your plant doesn't need any water right now.", False),
    ("HIGH urgency but watering_needed false", 20, "HIGH", False,
     "The soil is dry, keep watching it.", False),
    ("LOW urgency on very dry soil", 10, "LOW", False,
     "All good.", False),
    ("watering a waterlogged plant", 92, "LOW", True,
     "Give it some water now.", False),
]

results = [check(*c) for c in CASES]
print(f"\n{sum(results)}/{len(results)} checks passed")