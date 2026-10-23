import re

DRY_BELOW = 25     # soil moisture % below which the plant is dry
DAMP_BELOW = 40    # below this the soil is getting dry
WET_ABOVE = 80     # above this the soil is too wet to water

_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Any negative cue in the message ("doesn't", "not", "no", "without", "skip", ...).
# If one is present, a "water ... now" phrase is not read as an instruction to water.
_NEGATION = re.compile(
    r"(n't\b|\b(?:not|no|never|without|avoid|skip|hold off|wait|unnecessary|"
    r"nothing|later)\b)",
    re.I,
)
_WATER_NOW = re.compile(
    r"\bwater(?:ing)?\b[^.!?]{0,40}\b(now|immediately|right away|today)\b", re.I
)
# Phrases that clearly say NOT to water (checked when watering_needed is true)
_DONT_WATER = re.compile(
    r"(no need to water|no need for watering|don't water|do not water|"
    r"skip watering|hold off on watering|avoid watering|"
    r"doesn'?t need (?:any )?water|does not need (?:any )?water|"
    r"without (?:needing to )?water)",
    re.I,
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def rule_baseline(soil: float) -> str:
    """Plain threshold urgency, used as an independent cross-check."""
    if soil < DRY_BELOW:
        return "HIGH"
    if soil < DAMP_BELOW:
        return "MEDIUM"
    return "LOW"


def _allowed_urgency(soil: float, placement: str):
    if soil < DRY_BELOW:
        return ("HIGH", "HIGH") if placement == "indoor" else ("MEDIUM", "HIGH")
    if soil < DAMP_BELOW:
        # getting dry: MEDIUM at most, HIGH is reserved for a dry soil
        return ("MEDIUM", "MEDIUM") if placement == "indoor" else ("LOW", "MEDIUM")
    return ("LOW", "MEDIUM")


def _allowed_numbers(reading: dict, weather, history) -> set:
    nums = {float(x) for x in (DRY_BELOW, DAMP_BELOW, WET_ABOVE, 24, 30, 32, 35, 100)}

    def add(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            nums.add(float(v))

    for k in ("soil_moisture", "temperature", "humidity"):
        add(reading.get(k))
        for h in history or []:
            add(h.get(k))
    if weather:
        for k in (
            "temperature", "humidity", "temp_min_24h", "temp_max_24h",
            "rain_probability_max_24h", "rain_expected_mm_24h",
            "rain_expected_in_hours", "rain_now_mm",
        ):
            add(weather.get(k))
    return nums


def validate_care(out, env, reading: dict, weather, history, placement: str) -> dict:
    """Checks an agent output (FinalCare or EnvironmentAssessment) against the data.
    errors   -> output must not be used
    warnings -> recorded only"""
    errors, warnings = [], []

    urgency = getattr(out, "urgency", None)
    watering = getattr(out, "watering_needed", None)
    message = (getattr(out, "care_message", "") or "").strip()
    reasoning = (getattr(out, "reasoning", "") or "").strip()
    quote = getattr(out, "quote", None)
    soil = float(reading["soil_moisture"])

    # 1. completeness
    if urgency not in _RANK:
        errors.append("urgency missing or invalid")
    if not message:
        errors.append("care_message is empty")
    if not reasoning:
        errors.append("reasoning is empty")

    # 2. urgency must be plausible for the measured soil moisture
    if urgency in _RANK:
        lo, hi = _allowed_urgency(soil, placement)
        if not (_RANK[lo] <= _RANK[urgency] <= _RANK[hi]):
            errors.append(
                f"urgency {urgency} is not plausible for soil moisture {soil:.0f}% "
                f"({placement}); expected {lo} to {hi}"
            )
        if urgency == "HIGH" and watering is False:
            errors.append("urgency is HIGH but watering_needed is false")

    # 3. never water a soil that is already too wet
    if soil > WET_ABOVE and watering:
        errors.append(f"watering_needed is true although soil moisture is {soil:.0f}%")

    # 4. the message must agree with the decision
    if watering is False and _WATER_NOW.search(message) and not _NEGATION.search(message):
        errors.append("message says to water now but watering_needed is false")
    if watering is True and _DONT_WATER.search(message):
        errors.append("message says not to water but watering_needed is true")

    # 5. warnings: length, quote size, numbers that are not in the input data
    if len(message) > 300:
        warnings.append("care_message is longer than 300 characters")
    if quote is not None and not (1 <= len(quote.split()) <= 25):
        warnings.append("quote is empty or longer than 25 words")

    allowed = _allowed_numbers(reading, weather, history)
    for text, label in ((message, "care_message"), (reasoning, "reasoning")):
        for m in _NUMBER.findall(text):
            x = float(m)
            if not any(abs(x - a) <= 0.51 for a in allowed):
                warnings.append(f"{label} mentions {m}, which is not in the input data")

    warnings = list(dict.fromkeys(warnings))  # remove duplicates, keep order
    return {"passed": not errors, "errors": errors, "warnings": warnings}