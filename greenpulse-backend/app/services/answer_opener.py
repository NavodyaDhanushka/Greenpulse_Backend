"""The opening sentence of an Ask GreenPulse answer is written by code.

The code decides the verdict (NOW, TODAY, SOON, NO, NO_TOO_WET, NO_RAIN).
Some questions flip the meaning of Yes and No:
  "Does my plant need water today?"  -> "No, not today."
  "Can I skip watering today?"       -> "Yes, you can skip watering today."
So the code picks the opening sentence from the verdict AND the question.
The LLM only writes the reason after it, so it can never get Yes/No wrong.
"""
import re

WATER_NEEDED = {"NOW", "TODAY"}
NOT_NEEDED = {"NO", "NO_TOO_WET", "NO_RAIN"}

# Words that turn "Do I need to water?" into "Can I NOT water?"
_INVERTED = re.compile(
    r"\b(skip|wait|hold off|postpone|delay|leave it|avoid|"
    r"too much water|over-?water\w*|"
    r"(do not|don't|dont|not) (need to )?water|"
    r"without water\w*|no need)\b",
    re.IGNORECASE,
)

# A yes/no question starts with one of these words
_YES_NO_START = re.compile(
    r"^\s*(can|could|should|shall|do|does|did|is|are|will|would|may|must|"
    r"have|has|am|need)\b",
    re.IGNORECASE,
)

# verdict: (normal yes/no question, inverted yes/no question, any other question)
_OPENERS = {
    "NOW": ("Yes, water it now.",
            "No, please water it now.",
            "Water your plant now."),
    "TODAY": ("Yes, water it today.",
              "No, please water it today.",
              "Water your plant today."),
    "SOON": ("Not yet, but soon.",
             "Yes, you can skip watering for today.",
             "Not today, but soon."),
    "NO": ("No, not today.",
           "Yes, you can skip watering today.",
           "No watering is needed today."),
    "NO_TOO_WET": ("No, the soil is too wet.",
                   "Yes, please skip watering. The soil is too wet.",
                   "Do not water. The soil is too wet."),
    "NO_RAIN": ("No, rain is coming.",
                "Yes, you can skip watering. Rain is coming.",
                "No watering is needed. Rain is coming."),
}

# "Yes," / "No." / "Not yet," that the LLM may add at the start of its reason
_LEADING_YES_NO = re.compile(
    r"^\s*(yes|no|not yet|nope|yeah|yep)\b(?=\s*[,.!:;\-]|\s*$)[\s,.!:;\-]*",
    re.IGNORECASE,
)

# Phrases that would contradict the decision
_SAYS_WATER = re.compile(
    r"\b(water (it|your plant|the plant) (now|today)|water now|"
    r"needs? (water|watering) (now|today))\b",
    re.IGNORECASE,
)
_SAYS_DONT_WATER = re.compile(
    r"\b(do not water|don't water|dont water|skip watering|no need to water|"
    r"(no|not) (water|watering) (is )?needed|"
    r"(does not|doesn't|do not|don't) need (to (be )?)?water\w*)\b",
    re.IGNORECASE,
)


def last_question(question: str) -> str:
    """'I watered yesterday. Do I need to water again?' -> 'Do I need to water again?'"""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", (question or "").strip()) if p.strip()]
    if not parts:
        return ""
    for p in reversed(parts):
        if p.endswith("?"):
            return p
    return parts[-1]


def question_kind(question: str) -> str:
    """'normal' (Do I need to water?), 'inverted' (Can I skip watering?) or 'other'."""
    q = last_question(question)
    if not q or "water" not in q.lower() or not _YES_NO_START.match(q):
        return "other"
    return "inverted" if _INVERTED.search(q) else "normal"


def required_opener(question: str, verdict: str) -> str:
    """The exact first sentence of the answer, chosen by code."""
    row = _OPENERS.get(verdict)
    if row is None:
        return ""
    index = {"normal": 0, "inverted": 1, "other": 2}[question_kind(question)]
    return row[index]


def first_word(text: str) -> str:
    m = re.match(r"\s*([A-Za-z']+)", text or "")
    return m.group(1).lower() if m else ""


def clean_reason(reason: str) -> str:
    """Remove a Yes/No the LLM added by itself and tidy the text."""
    text = _LEADING_YES_NO.sub("", (reason or "").strip(), count=1).strip()
    return text[:1].upper() + text[1:]


def reason_ok(reason: str, verdict: str) -> bool:
    """The reason must exist, be short, and must not contradict the decision."""
    if not reason or len(reason) > 350:
        return False
    if verdict in NOT_NEEDED or verdict == "SOON":
        # Remove negative phrases first, so "does not need water today"
        # is not read as "need water today".
        positive_only = _SAYS_DONT_WATER.sub(" ", reason)
        positive_only = re.sub(r"\b(not|no|never)\s+\w+\s+water\w*", " ", positive_only,
                               flags=re.IGNORECASE)
        return not _SAYS_WATER.search(positive_only)
    if verdict in WATER_NEEDED:
        return not _SAYS_DONT_WATER.search(reason)
    return True

_WEATHER_WORDS = re.compile(r"\b(rain\w*|weather|forecast|storm\w*)\b", re.IGNORECASE)


def weather_note(question: str, placement: str, weather) -> str:
    """Extra sentence (written by code) when the owner asks about rain or weather."""
    if not _WEATHER_WORDS.search(question or ""):
        return ""
    if placement != "outdoor":
        return "Your plant is indoors, so rain does not affect this decision."
    if weather and weather.get("summary"):
        return f"Weather: {weather['summary']}"
    return "I do not have the weather forecast right now."