"""
intent.py — Groq structured intent extraction, Pydantic validated, retry once.
No policy decision here — just language understanding.
"""
import json
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from groq import Groq

from app.config import settings
from app.agent.prompts import INTENT_PROMPT, RESPONSE_PROMPT


class IntentEntities(BaseModel):
    amount: Optional[float] = None
    hotel_type: Optional[str] = None  # full_night | delayed_hours | null
    refund_method: Optional[str] = None  # original | alternate | null
    upgrade_class: Optional[str] = None  # business | null


class IntentResult(BaseModel):
    primary_intent: str = Field(description="main intent enum")
    secondary_intents: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    requested_exception: bool = False
    entities: IntentEntities = Field(default_factory=IntentEntities)

    class Config:
        extra = "ignore"


ALLOWED_INTENTS = {
    "refund_request", "rebooking_request", "meal_voucher_request", "lounge_request",
    "hotel_request", "fare_waiver_request", "booking_inquiry", "upgrade_request",
    "complaint", "unknown",
}
ALLOWED_SENTIMENTS = {"neutral", "frustrated", "angry", "legal_threat"}


def _get_client() -> Groq:
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        raise RuntimeError("GROQ_API_KEY not configured in backend/.env — see .env.example")
    return Groq(api_key=settings.GROQ_API_KEY)


def _parse_and_validate(raw: str) -> IntentResult:
    # strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        # remove ```json ... ```
        end = text.rfind("```")
        if end > 3:
            text = text[3:end].strip()
        # remove leading json marker
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    # normalize
    # coerce amount: handle "₹2,000" or "2000" strings
    ent = data.get("entities", {}) or {}
    if isinstance(ent.get("amount"), str):
        s = ent["amount"].replace("₹", "").replace(",", "").strip()
        try:
            ent["amount"] = float(s) if "." in s else int(s)
        except Exception:
            ent["amount"] = None
    data["entities"] = ent
    result = IntentResult(**data)
    # clamp enums to known values, fallback to unknown/neutral on invalid
    if result.primary_intent not in ALLOWED_INTENTS:
        result.primary_intent = "unknown"
    if result.sentiment not in ALLOWED_SENTIMENTS:
        result.sentiment = "neutral"
    # normalize secondary
    result.secondary_intents = [s for s in (result.secondary_intents or []) if s in ALLOWED_INTENTS]
    return result


def extract_intent(message: str, booking_context: str = "", history: str = "") -> IntentResult:
    """
    Call Groq to extract intent. Validates via Pydantic, retry once on invalid JSON.
    Raises on missing API key; caller (orchestrator) handles fallback to unknown.
    """
    client = _get_client()
    prompt = INTENT_PROMPT.format(
        booking_context=booking_context or "No booking loaded",
        history=history or "No history",
        message=message,
    )
    # attempt 1
    try:
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content or ""
        return _parse_and_validate(raw)
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        # retry once with explicit instruction
        retry_prompt = prompt + "\n\nReturn ONLY valid JSON, no extra text. Previous output was invalid: " + str(e)[:200]
        try:
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": retry_prompt}],
                temperature=0.0,
                max_tokens=500,
            )
            raw = resp.choices[0].message.content or ""
            return _parse_and_validate(raw)
        except Exception:
            # safe fallback — do not fail the turn, ask clarification later
            return IntentResult(primary_intent="unknown", secondary_intents=[], sentiment="neutral", requested_exception=False, entities=IntentEntities())
    except Exception as e:
        # Groq API error (auth, timeout, etc.) — fallback
        raise RuntimeError(f"Groq intent extraction failed: {e}") from e


def fallback_intent(message: str) -> IntentResult:
    """Keyword fallback when Groq retries both fail — minimal, no elaborate NLP (6h scope).
    Covers hotel paraphrases required by QA: hotel, accommodation, somewhere to stay, place to stay, arrange hotel/accommodation, stranded, room."""
    low = message.lower()
    detected: list[str] = []
    # collect all matched intents (order matters for primary)
    if any(k in low for k in ["refund", "cash back", "money back"]):
        detected.append("refund_request")
    if any(k in low for k in ["rebook", "re-book", "next flight", "another flight"]):
        detected.append("rebooking_request")
    # hotel / accommodation paraphrases — comprehensive per QA Fix 1
    hotel_keys = ["hotel", "accommodation", "somewhere to stay", "place to stay", "need a place", "need somewhere", "arrange a hotel", "arrange accommodation", "stranded", "provide a room", "a room", "place to stay tonight", "somewhere to stay because", "room"]
    if any(k in low for k in hotel_keys):
        detected.append("hotel_request")
    if any(k in low for k in ["lounge"]):
        detected.append("lounge_request")
    if any(k in low for k in ["meal", "voucher", "food"]):
        detected.append("meal_voucher_request")
    if any(k in low for k in ["waive", "fare difference", "fare waiver"]):
        detected.append("fare_waiver_request")
    if any(k in low for k in ["upgrade", "business class"]):
        detected.append("upgrade_request")
    if "booking" in low or "flight status" in low or "pnr" in low:
        detected.append("booking_inquiry")

    if not detected:
        primary = "unknown"
        secondary = []
    else:
        # deduplicate while preserving order
        seen = set()
        uniq = []
        for d in detected:
            if d not in seen:
                seen.add(d)
                uniq.append(d)
        primary = uniq[0]
        secondary = uniq[1:]

    sentiment = "neutral"
    if any(k in low for k in ["sue", "lawyer", "legal", "court", "formal complaint"]):
        sentiment = "legal_threat"
    elif any(k in low for k in ["furious", "angry", "ridiculous", "frustrated", "terrible", "upset", "annoyed", "disappointed", "stranded", "urgent", "worried", "anxious", "miss an important meeting", "messed up", "unacceptable"]):
        # mood-based: frustrated/angry keywords indicate customer is upset — keep intent as hotel/refund etc. but mark sentiment
        sentiment = "frustrated"
        # also treat strong angry words as frustrated for this prototype
        if any(k in low for k in ["furious", "angry"]):
            sentiment = "frustrated"

    amount = None
    import re
    m = re.search(r"₹?\s*([\d,]+\.?\d*)", message)
    if m and any(k in low for k in ["waive", "fare difference", "fare waiver"]):
        try:
            amount = float(m.group(1).replace(",", ""))
        except Exception:
            amount = None

    hotel_type = None
    if "full" in low and "night" in low:
        hotel_type = "full_night"
    elif "delayed" in low:
        hotel_type = "delayed_hours"

    return IntentResult(
        primary_intent=primary,
        secondary_intents=secondary,
        sentiment=sentiment,
        requested_exception=False,
        entities=IntentEntities(amount=amount, hotel_type=hotel_type),
    )


def generate_response(
    message: str,
    booking: dict,
    policy_result: dict,
    actions_taken: list,
    escalation: Optional[dict],
    decision_trace: list,
    pnr: str,
) -> str:
    """Call Groq to verbalize verified context. Policy already decided — Groq only communicates."""
    client = _get_client()
    prompt = RESPONSE_PROMPT.format(
        booking=json.dumps(booking, indent=2) if isinstance(booking, dict) else str(booking),
        policy_result=json.dumps(policy_result, indent=2) if isinstance(policy_result, dict) else str(policy_result),
        actions_taken=json.dumps(actions_taken, indent=2) if actions_taken else "None this turn",
        escalation=json.dumps(escalation, indent=2) if escalation else "None",
        decision_trace="\n".join(decision_trace) if decision_trace else "No trace",
        message=message,
        pnr=pnr,
    )
    resp = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=700,
    )
    return (resp.choices[0].message.content or "").strip()
