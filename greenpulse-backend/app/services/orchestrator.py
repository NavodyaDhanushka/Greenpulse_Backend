import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ..agents.care_agent import run_care_agent
from ..agents.environment_agent import assess_environment
from ..agents.notification_agent import get_notifications
from ..agents.weather_agent import get_weather
from ..config import settings
from ..db.mongo import ai_responses
from ..mqtt.topics import (
    TOPIC_AI_INPUT, TOPIC_CARE, TOPIC_NOTIFICATIONS, TOPIC_STATUS, TOPIC_WEATHER,
)
from .circuit_breaker import CircuitBreaker
from .fallback import get_fallback_quote, rule_based_care
from .sensor_service import get_recent_readings
from .validation import rule_baseline, validate_care
from .prediction import predict_watering

executor = ThreadPoolExecutor(max_workers=2)        # one job per sensor reading
_agents_pool = ThreadPoolExecutor(max_workers=3)    # the three data agents inside a job

breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=120)

_last_run: dict[str, float] = {}
_lock = threading.Lock()


def _throttled(device_id: str) -> bool:
    now = time.monotonic()
    with _lock:
        last = _last_run.get(device_id)
        if last is not None and now - last < settings.ai_min_interval_seconds:
            return True
        _last_run[device_id] = now
        return False


def _safe(label: str, future, timeout: int = 45):
    try:
        return future.result(timeout=timeout)
    except Exception as e:
        print(f"{label} failed: {e!r}")
        return None


def _announce(publish, state: str, detail: str):
    publish(
        TOPIC_STATUS,
        {
            "source": "backend",
            "status": state,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        retain=True,
    )


def _track_llm(publish, ok: bool):
    if ok:
        if breaker.record_success():
            _announce(publish, "online", "AI service recovered")
    else:
        if breaker.record_failure():
            _announce(publish, "degraded", "AI service unreachable, using rule-based fallback")


def handle_reading(saved: dict, publish):
    """Orchestrator. Runs in a worker thread. `publish` is client.publish_json."""
    device_id = saved["device_id"]

    if _throttled(device_id):
        return

    started = time.monotonic()
    placement = settings.plant_placement
    history = get_recent_readings(device_id, limit=10)

    # 1) Environment, Weather and Notification agents in parallel.
    #    The Environment Agent is skipped while the LLM is known to be down.
    llm_allowed = breaker.allow()
    env_f = _agents_pool.submit(assess_environment, history) if llm_allowed else None
    weather_f = _agents_pool.submit(get_weather)
    notif_f = _agents_pool.submit(get_notifications)

    env = _safe("Environment Agent", env_f) if env_f is not None else None
    if env_f is not None:
        _track_llm(publish, ok=env is not None)
    weather = _safe("Weather Agent", weather_f)
    notifications = _safe("Notification Agent", notif_f)

    if weather:
        publish(TOPIC_WEATHER, weather, retain=True)
    if notifications:
        publish(TOPIC_NOTIFICATIONS, notifications, retain=True)

    # The context the Care Agent is about to receive (the "LLM input" payload)
    publish(
        TOPIC_AI_INPUT,
        {
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "placement": placement,
            "sensor": {
                "soil_moisture": saved["soil_moisture"],
                "temperature": saved["temperature"],
                "humidity": saved["humidity"],
                "soil_status": saved.get("soil_status"),
                "watering_priority": saved.get("watering_priority"),
            },
            "environment_assessment": (
                {
                    "urgency": env.urgency,
                    "watering_needed": env.watering_needed,
                    "reasoning": env.reasoning,
                }
                if env
                else None
            ),
            "weather_summary": weather["summary"] if weather else None,
            "notification_summary": (
                notifications["summary"]
                if notifications and notifications["has_relevant_info"]
                else None
            ),
        },
        retain=True,
    )

    # 2) Care Agent, with validation, one retry, and layered fallbacks
    chosen = None          # ("care-agent" | "environment-agent", object)
    report = None
    rejected: list = []
    attempts = 0

    if env is not None:
        for attempt in (1, 2):
            attempts = attempt
            try:
                candidate = run_care_agent(env, saved, weather, notifications)
            except Exception as e:
                print(f"Care Agent failed: {e!r}")
                _track_llm(publish, ok=False)
                break
            _track_llm(publish, ok=True)
            report = validate_care(candidate, env, saved, weather, history, placement)
            if report["passed"]:
                chosen = ("care-agent", candidate)
                break
            rejected.extend(report["errors"])
            print(f"Care Agent output rejected (attempt {attempt}): {report['errors']}")

        if chosen is None:
            env_report = validate_care(env, env, saved, weather, history, placement)
            if env_report["passed"]:
                chosen = ("environment-agent", env)
                report = env_report
            else:
                rejected.extend(env_report["errors"])
                print(f"Environment Agent output rejected: {env_report['errors']}")

    if chosen is not None and chosen[0] == "care-agent":
        out = chosen[1]
        source = "care-agent"
        care = {
            "urgency": out.urgency,
            "watering_needed": out.watering_needed,
            "care_message": out.care_message,
            "quote": out.quote,
            "quote_source": "llm",
            "plant_condition": env.plant_condition,
            "reasoning": out.reasoning,
        }
    elif chosen is not None:
        out = chosen[1]
        source = "environment-agent"
        quote, quote_source = get_fallback_quote()
        care = {
            "urgency": out.urgency,
            "watering_needed": out.watering_needed,
            "care_message": out.care_message,
            "quote": quote,
            "quote_source": quote_source,
            "plant_condition": out.plant_condition,
            "reasoning": out.reasoning,
        }
    else:
        source = "rule-based"
        care = rule_based_care(saved, history)
        report = {"passed": True, "errors": [], "warnings": []}

    rule_urgency = rule_baseline(float(saved["soil_moisture"]))
    care.update(
        {
            "source": source,
            "degraded": source != "care-agent",
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "soil_moisture": saved["soil_moisture"],
            "device_watering_priority": saved.get("watering_priority"),
            "weather_summary": weather["summary"] if weather else None,
            "notification_summary": (
                notifications["summary"]
                if notifications and notifications["has_relevant_info"]
                else None
            ),
            "environment": (
                {
                    "urgency": env.urgency,
                    "watering_needed": env.watering_needed,
                    "plant_condition": env.plant_condition,
                    "reasoning": env.reasoning,
                }
                if env
                else None
            ),
            "validation": {**report, "attempts": attempts, "rejected_errors": rejected},
            "rule_urgency": rule_urgency,
            "agrees_with_rules": care["urgency"] == rule_urgency,
            "latency_seconds": round(time.monotonic() - started, 1),
            "prediction": predict_watering(device_id),
        }
    )

    try:
        ai_responses.insert_one(dict(care))  # copy: insert_one adds _id
    except Exception as e:
        print(f"Failed to save AI response: {e}")

    publish(TOPIC_CARE, care, retain=True)
    print(
        f"Published care message ({care['source']}): {care['urgency']} "
        f"in {care['latency_seconds']}s"
    )