import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prediction import predict_from_points

T0 = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)


def series(v0, v1, hours, t0=T0, step_min=5, noise=0.0):
    n = int(hours * 60 / step_min) + 1
    pts = []
    for i in range(n):
        value = v0 + (v1 - v0) * i / (n - 1)
        if noise:
            value += noise if i % 2 == 0 else -noise
        pts.append((t0 + timedelta(minutes=i * step_min), value))
    return pts


results = []


def check(name, condition, detail=""):
    results.append(condition)
    print(("PASS" if condition else "FAIL"), "-", name, "" if condition else detail)


r = predict_from_points(series(60, 40, 4))
check("falling 5%/h: dry in about 3 hours",
      r["trend"] == "falling" and abs(r["hours_until_dry"] - 3.0) < 0.2 and r["confidence"] == "high", r)

r = predict_from_points(series(55, 55, 3))
check("flat soil is stable, no dry time",
      r["trend"] == "stable" and r["hours_until_dry"] is None, r)

r = predict_from_points(series(50, 55, 3))
check("rising soil is reported as rising", r["trend"] == "rising", r)

seg1 = series(50, 30, 3)
seg2 = series(70, 66, 1, t0=T0 + timedelta(hours=3, minutes=5))
r = predict_from_points(seg1 + seg2)
check("watering event restarts the fit",
      r["watered_recently"] and 9.5 <= r["hours_until_dry"] <= 11.0, r)

r = predict_from_points(series(60, 59, 0.2, step_min=5))
check("too little data is reported as unavailable", r["available"] is False, r)

r = predict_from_points(series(60, 58.8, 4))
check("very slow drying gives no dry time (over 72 h)",
      r["trend"] == "falling" and r["hours_until_dry"] is None, r)

r = predict_from_points(series(24, 20, 2))
check("already below the dry level: 0 hours", r["hours_until_dry"] == 0.0, r)

r = predict_from_points(series(60, 40, 4, noise=1.0))
check("noisy readings still give a sensible estimate",
      2.5 <= r["hours_until_dry"] <= 3.5, r)

r = predict_from_points([])
check("no readings", r["available"] is False, r)

print(f"\n{sum(results)}/{len(results)} checks passed")