"""Seed a realistic soil-drying history so the watering prediction has data.

The prediction needs several readings spread over time, all AFTER the last
watering (a jump up in soil moisture). This script writes past readings that
start just after a "watering" and fall slowly until now.

It copies the format of your latest real reading (same field names, same
received_at type), and marks every seeded document with demo_seed=True so
they are easy to remove.

Usage (from the backend folder):
  python scripts/seed_demo_history.py --scenario today      # verdict TODAY (dry in ~5 h)
  python scripts/seed_demo_history.py --scenario soon       # verdict SOON  (dry in ~13 h)
  python scripts/seed_demo_history.py --scenario no         # verdict NO    (dry in ~2-3 days)
  python scripts/seed_demo_history.py --start 60 --end 35 --hours 12   # custom
  python scripts/seed_demo_history.py --scenario today --clear          # also remove old readings in the window
  python scripts/seed_demo_history.py --remove                          # delete all seeded readings
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.mongo import sensor_readings  # noqa: E402

SCENARIOS = {
    # name: (start %, end %, hours)   -> falling rate, hours until 25 %
    "today": (60, 35, 12),   # ~2.1 %/h -> dry in ~5 h   -> TODAY
    "soon": (50, 38, 12),    # ~1.0 %/h -> dry in ~13 h  -> SOON
    "no": (65, 58, 12),      # ~0.6 %/h -> dry in ~2.5 d -> NO
}
DRY_BELOW = 25


def _latest_reading(device_id=None):
    query = {"device_id": device_id} if device_id else {}
    return sensor_readings.find_one(query, sort=[("received_at", -1)])


def _time_value(dt_utc: datetime, like):
    """Return dt_utc in the same form as the existing received_at value."""
    if isinstance(like, str):
        return dt_utc.isoformat()
    if isinstance(like, datetime) and like.tzinfo is None:
        return dt_utc.replace(tzinfo=None)  # pymongo default: naive UTC
    return dt_utc


def main():
    ap = argparse.ArgumentParser(description="Seed demo soil history for the prediction.")
    ap.add_argument("--scenario", choices=SCENARIOS.keys(), default="today")
    ap.add_argument("--start", type=float, help="soil %% just after watering (overrides scenario)")
    ap.add_argument("--end", type=float, help="soil %% now (overrides scenario)")
    ap.add_argument("--hours", type=float, help="hours since watering (overrides scenario)")
    ap.add_argument("--every", type=int, default=15, help="minutes between readings (default 15)")
    ap.add_argument("--noise", type=float, default=0.3, help="random +/- noise in %% (default 0.3)")
    ap.add_argument("--device", help="device id (default: device of the newest reading)")
    ap.add_argument("--clear", action="store_true",
                    help="delete this device's readings inside the seeded time window first")
    ap.add_argument("--remove", action="store_true", help="delete all seeded readings and exit")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = ap.parse_args()

    if args.remove:
        n = sensor_readings.delete_many({"demo_seed": True}).deleted_count
        print(f"Removed {n} seeded readings.")
        return

    start, end, hours = SCENARIOS[args.scenario]
    start = args.start if args.start is not None else start
    end = args.end if args.end is not None else end
    hours = args.hours if args.hours is not None else hours
    if not (0 <= end < start <= 100) or hours <= 0:
        sys.exit("Need 0 <= end < start <= 100 and hours > 0.")

    template = _latest_reading(args.device)
    device_id = args.device or (template or {}).get("device_id") or "greenpulse-esp32"
    if template is None:
        template = {"device_id": device_id, "temperature": 28.0, "humidity": 65.0,
                    "received_at": datetime.now(timezone.utc)}
        print("No existing readings found: using a basic format.")
    like = template.get("received_at")

    now = datetime.now(timezone.utc)
    first_time = now - timedelta(hours=hours)
    steps = max(int(hours * 60 // args.every), 4)

    if args.clear:
        window = {"device_id": device_id,
                  "received_at": {"$gte": _time_value(first_time - timedelta(minutes=30), like)}}
        count = sensor_readings.count_documents(window)
        if count and not args.yes:
            ans = input(f"Delete {count} readings of {device_id} from the last {hours + 0.5:g} h? (yes/no) ")
            if ans.strip().lower() != "yes":
                sys.exit("Cancelled.")
        n = sensor_readings.delete_many(window).deleted_count
        print(f"Deleted {n} readings in the window.")

    rnd = random.Random(42)
    docs = []
    for i in range(steps + 1):
        frac = i / steps
        t = first_time + timedelta(hours=hours * frac)
        soil = start + (end - start) * frac
        if 0 < i < steps:
            soil += rnd.uniform(-args.noise, args.noise)
        doc = {k: v for k, v in template.items() if k != "_id"}
        doc.update({
            "device_id": device_id,
            "soil_moisture": round(soil, 1),
            "received_at": _time_value(t, like),
            "demo_seed": True,
        })
        if "timestamp" in template:
            doc["timestamp"] = _time_value(t, template["timestamp"])
        if "temperature" in template:
            doc["temperature"] = round(27.0 + 2.0 * frac + rnd.uniform(-0.2, 0.2), 1)
        if "humidity" in template:
            doc["humidity"] = round(70.0 - 6.0 * frac + rnd.uniform(-0.5, 0.5), 1)
        docs.append(doc)

    sensor_readings.insert_many(docs)

    rate = (start - end) / hours
    eta = (end - DRY_BELOW) / rate if end > DRY_BELOW else 0
    print(f"Seeded {len(docs)} readings for {device_id}: {start:g}% -> {end:g}% over {hours:g} h "
          f"(about {rate:.1f}% per hour).")
    print(f"Expected: dry level ({DRY_BELOW}%) in about {eta:.0f} hours.")
    print("Now send one live reading slightly below the last value so the AI runs, for example:")
    print(f"  python scripts/send_reading.py {max(end - 0.5, 0):g} 28.5 64")


if __name__ == "__main__":
    main()