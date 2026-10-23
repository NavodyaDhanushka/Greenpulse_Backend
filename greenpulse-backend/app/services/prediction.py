import math
from datetime import datetime, timedelta, timezone

from ..db.mongo import sensor_readings
from .validation import DRY_BELOW

WINDOW_HOURS = 6        # how far back to look for readings
MAX_POINTS = 300        # thin out very dense data before fitting
WATERING_JUMP = 8.0     # a rise of this many points between two readings = the plant was watered
MIN_POINTS = 5
MIN_SPAN_HOURS = 0.25   # at least 15 minutes of data
FLAT_SLOPE = 0.05       # % per hour; a slower change counts as stable
MAX_HOURS = 72          # do not predict further ahead than this


def _utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _confidence(n, span, r2, trending):
    if n >= 30 and span >= 1.0 and (r2 >= 0.7 or not trending):
        return "high"
    if n >= 10 and span >= 0.5 and (r2 >= 0.4 or not trending):
        return "medium"
    return "low"


def predict_from_points(points):
    """points: list of (datetime, soil_moisture). Pure function, no database access."""
    pts = sorted(((_utc(t), float(v)) for t, v in points), key=lambda p: p[0])
    if not pts:
        return {"available": False, "reason": "no readings in the last %d hours" % WINDOW_HOURS}

    # Only use the data since the last watering (a sudden rise in soil moisture)
    start = 0
    for i in range(1, len(pts)):
        if pts[i][1] - pts[i - 1][1] >= WATERING_JUMP:
            start = i
    watered_recently = start > 0
    pts = pts[start:]

    last_time, last_value = pts[-1]
    span = (pts[-1][0] - pts[0][0]).total_seconds() / 3600
    base = {
        "available": False,
        "soil_moisture": last_value,
        "points_used": len(pts),
        "window_hours": round(span, 1),
        "watered_recently": watered_recently,
    }
    if len(pts) < MIN_POINTS or span < MIN_SPAN_HOURS:
        return {**base, "reason": "not enough data since the last watering"}

    if len(pts) > MAX_POINTS:
        step = math.ceil(len(pts) / MAX_POINTS)
        thinned = pts[::step]
        if thinned[-1] != pts[-1]:
            thinned.append(pts[-1])
        pts = thinned

    # Least-squares line through (hours since first reading, soil moisture)
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 3600 for t, _ in pts]
    ys = [v for _, v in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return {**base, "reason": "readings do not span any time"}
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    fitted_now = intercept + slope * xs[-1]

    result = {
        **base,
        "available": True,
        "slope_pct_per_hour": round(slope, 2),
        "r_squared": round(r2, 2),
        "fitted_soil_moisture": round(fitted_now, 1),
        "hours_until_dry": None,
        "dry_at": None,
    }

    if slope > -FLAT_SLOPE:
        result["trend"] = "rising" if slope > FLAT_SLOPE else "stable"
        result["confidence"] = _confidence(n, span, r2, trending=False)
        return result

    result["trend"] = "falling"
    result["confidence"] = _confidence(n, span, r2, trending=True)
    hours = max(0.0, (fitted_now - DRY_BELOW) / (-slope))
    if hours <= MAX_HOURS:
        result["hours_until_dry"] = round(hours, 1)
        result["dry_at"] = (last_time + timedelta(hours=hours)).isoformat()
    else:
        result["note"] = "more than %d hours" % MAX_HOURS
    return result


def predict_watering(device_id: str) -> dict:
    """Prediction from the stored readings of one device. Never raises."""
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
        docs = list(
            sensor_readings.find(
                {"device_id": device_id, "received_at": {"$gte": since}},
                {"_id": 0, "soil_moisture": 1, "received_at": 1},
            ).sort("received_at", 1)
        )
        result = predict_from_points([(d["received_at"], d["soil_moisture"]) for d in docs])
    except Exception as e:
        print(f"Prediction failed: {e!r}")
        return {"available": False, "reason": "prediction failed", "device_id": device_id}
    result["device_id"] = device_id
    return result