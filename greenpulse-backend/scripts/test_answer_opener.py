"""Tests for the Ask GreenPulse opening sentence.
Run: python scripts/test_answer_opener.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.answer_opener import clean_reason, reason_ok, required_opener  # noqa: E402

OPENER_CASES = [
    # (question, verdict, answer must start with)
    ("Can I skip watering today?", "NO", "Yes, you can skip"),
    ("Can I skip watering today?", "NOW", "No, please water it now."),
    ("Can I skip watering today?", "NO_TOO_WET", "Yes, please skip"),
    ("Can I skip watering today?", "NO_RAIN", "Yes, you can skip"),
    ("Can I skip watering today?", "SOON", "Yes, you can skip watering for today."),
    ("Does my plant need watering today?", "NO", "No, not today."),
    ("Does my plant need watering today?", "NOW", "Yes, water it now."),
    ("Does my plant need watering today?", "TODAY", "Yes, water it today."),
    ("Does my plant need watering today?", "SOON", "Not yet, but soon."),
    ("Does my plant need watering today?", "NO_TOO_WET", "No, the soil is too wet."),
    ("Should I wait before watering?", "SOON", "Yes, you can skip"),
    ("Should I wait before watering?", "NOW", "No, please water it now."),
    ("I watered yesterday. Do I need to water again?", "NO", "No, not today."),
    ("Will it rain? Should I still water?", "NO_RAIN", "No, rain is coming."),
    ("Should I water my plant now?", "TODAY", "Yes, water it today."),
    ("Is it okay if I don't water it today?", "NO", "Yes, you can skip"),
    ("When will my plant need water next?", "SOON", "Not today, but soon."),
    ("What is the soil moisture right now?", "NO", "No watering is needed today."),
    ("Is the soil too dry?", "NOW", "Water your plant now."),
    ("Is my plant healthy?", "NO_TOO_WET", "Do not water."),
]

REASON_CASES = [
    # (LLM reason, verdict, expected cleaned text start, expected ok)
    ("No, the soil moisture is 59%, well above the dry level of 25%.", "NO",
     "The soil moisture is 59%", True),
    ("Yes. Soil is 20%, below the dry level.", "NOW", "Soil is 20%", True),
    ("The soil is 59%, so water it now.", "NO", "The soil is 59%", False),
    ("Soil is 20%, so you do not need to water it.", "NOW", "Soil is 20%", False),
    ("No need to water, the soil is 59%.", "NO", "No need to water", True),
    ("", "NO", "", False),
]

passed = 0
total = len(OPENER_CASES) + len(REASON_CASES)

for q, v, start in OPENER_CASES:
    got = required_opener(q, v)
    ok = got.startswith(start)
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'} | {v:10} | {q}\n       -> {got}")

for reason, v, start, expected_ok in REASON_CASES:
    cleaned = clean_reason(reason)
    ok = cleaned.startswith(start) and reason_ok(cleaned, v) == expected_ok
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'} | reason check {v:10} ok={expected_ok} | {cleaned!r}")

print(f"\n{passed}/{total} passed")
sys.exit(0 if passed == total else 1)