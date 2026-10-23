import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services.ask import _consistent, decide_verdict, template_answer

results = []


def check(name, got, expected):
    ok = got == expected
    results.append(ok)
    print(("PASS" if ok else "FAIL"), "-", name, "" if ok else f"(got {got!r}, expected {expected!r})")


def pred(hours=None, trend="falling", slope=-3.0):
    return {"available": True, "hours_until_dry": hours, "trend": trend,
            "slope_pct_per_hour": slope, "confidence": "high"}


settings.plant_placement = "indoor"
check("dry soil -> NOW", decide_verdict(20, pred(), None), "NOW")
check("waterlogged -> NO_TOO_WET", decide_verdict(90, pred(), None), "NO_TOO_WET")
check("stable soil -> NO", decide_verdict(55, pred(None, "stable", 0.0), None), "NO")
check("dry in 6 h -> TODAY", decide_verdict(40, pred(6), None), "TODAY")
check("dry in 18 h -> SOON", decide_verdict(40, pred(18), None), "SOON")
check("dry in 40 h -> NO", decide_verdict(45, pred(40), None), "NO")
check("no prediction yet -> NO", decide_verdict(50, {"available": False}, None), "NO")

rain = {"rain_expected_in_hours": 2, "rain_expected_mm_24h": 8, "rain_probability_max_24h": 80}
check("indoor ignores rain", decide_verdict(40, pred(6), rain), "TODAY")
settings.plant_placement = "outdoor"
check("outdoor with rain coming -> NO_RAIN", decide_verdict(40, pred(6), rain), "NO_RAIN")
settings.plant_placement = "indoor"

check("Yes matches NOW", _consistent("Yes, water it now.", "NOW"), True)
check("No does not match NOW", _consistent("No, it is fine.", "NOW"), False)
check("No matches NO", _consistent("No. It is fine.", "NO"), True)
check("Yes does not match NO", _consistent("Yes, water it.", "NO"), False)
check("Not today matches SOON", _consistent("Not today, but soon.", "SOON"), True)
check("empty answer rejected", _consistent("", "NO"), False)

for verdict, soil, p in [
    ("NOW", 20, pred()), ("TODAY", 40, pred(6)), ("SOON", 40, pred(18)),
    ("NO", 55, pred(None, "stable", 0.0)), ("NO", 45, pred(40)), ("NO_TOO_WET", 90, pred()),
]:
    check(f"template for {verdict} is consistent",
          _consistent(template_answer(verdict, soil, p, None), verdict), True)

print(f"\n{sum(results)}/{len(results)} checks passed")