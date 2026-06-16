"""Steps c) + d) LLM classification and narrative summary via Gemini 1.5 Flash.

Calls are batched (one call for all uncategorised rows, one call for the
narrative). Retry up to 3 times with exponential backoff. On final failure
the caller decides how to degrade.
"""
import json
import time

import google.generativeai as genai

from app.config import settings

CATEGORIES = [
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other",
]

MODEL_NAME = "gemini-1.5-flash"
MAX_RETRIES = 3


class LLMError(Exception):
    pass


def _model():
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY not configured")
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(MODEL_NAME)


def _call_with_retry(prompt: str) -> str:
    """Single LLM call, retried 3x with exponential backoff."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = _model().generate_content(prompt)
            return resp.text
        except Exception as e:  # noqa: BLE001 - any SDK/network error retried
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)  # 1s, 2s, 4s
    raise LLMError(f"LLM call failed after {MAX_RETRIES} attempts: {last_err}")


def _extract_json(text: str):
    """Gemini may wrap JSON in ```json fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


def classify_categories(items: list[dict]) -> tuple[dict[int, str], str]:
    """Batched classification.

    items: [{"id": <txn id>, "merchant": str, "notes": str}, ...]
    Returns ({txn_id: category}, raw_response_text).
    """
    listing = "\n".join(
        f"{it['id']}: merchant={it['merchant']}, notes={it.get('notes') or ''}"
        for it in items
    )
    prompt = (
        "You are a financial transaction classifier. Assign each transaction "
        f"exactly one category from this list: {', '.join(CATEGORIES)}.\n"
        "Respond ONLY with a JSON object mapping the numeric id to the category "
        'string, e.g. {"12": "Food", "13": "Travel"}.\n\n'
        f"Transactions:\n{listing}"
    )
    raw = _call_with_retry(prompt)
    parsed = _extract_json(raw)
    result = {int(k): v for k, v in parsed.items() if v in CATEGORIES}
    return result, raw


def generate_narrative(stats: dict) -> dict:
    """Single call -> JSON summary with narrative + risk_level."""
    prompt = (
        "You are a financial analyst. Given these aggregate transaction stats, "
        "produce a JSON object with exactly these keys: "
        '"narrative" (a 2-3 sentence plain-English spending summary) and '
        '"risk_level" (one of "low", "medium", "high" based on anomaly count '
        "and spend concentration).\n"
        "Respond ONLY with the JSON object.\n\n"
        f"Stats:\n{json.dumps(stats, indent=2)}"
    )
    raw = _call_with_retry(prompt)
    parsed = _extract_json(raw)
    return {
        "narrative": parsed.get("narrative", ""),
        "risk_level": parsed.get("risk_level", "medium"),
    }
