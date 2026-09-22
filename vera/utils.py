from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stable_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256(canonical(parts).encode()).hexdigest()[:24]


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result
    except ValueError:
        return None


def obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def rows(value: Any) -> list[dict]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def text(value: Any, limit: int = 600) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    value = str(value)
    # Values remain data, never instructions. Reject obvious instruction-like fields.
    if re.search(r"ignore (?:all |the |previous )*instructions|system prompt|api[_ -]?key|<\|im_start\|>", value, re.I):
        return ""
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return re.sub(r"\s+", " ", value).strip()[:limit]


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def fmt(value: Any) -> str:
    n = number(value)
    return f"{n:,.0f}" if n is not None and n.is_integer() else (f"{n:,.2f}".rstrip("0").rstrip(".") if n is not None else "")


def pct(value: Any) -> str:
    n = number(value)
    return f"{abs(n) * 100:.1f}".rstrip("0").rstrip(".") + "%" if n is not None else ""


def human(value: Any) -> str:
    return text(value).replace("_", " ")


def date_label(value: Any) -> str:
    dt = parse_dt(value)
    if dt is None:
        return text(value, 100)
    # ISO values take precedence over occasionally inconsistent synthetic labels.
    if isinstance(value, str) and "T" not in value:
        return dt.strftime("%d %b %Y").lstrip("0")
    return dt.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def history_turns(value: Any) -> list[dict]:
    if isinstance(value, dict):
        value = value.get("turns", value.get("messages", []))
    return rows(value)


def choose_language(merchant: dict, customer: dict | None = None, message: str = "") -> str:
    if re.search(r"[\u0900-\u097f]", message):
        return "hi"
    if re.search(r"\b(haan|nahi|nahin|mujhe|aap|bhejo|batao|chahiye|karna|karo|judna|judrna|theek)\b", message, re.I):
        return "hinglish"
    identity = obj((customer or merchant).get("identity"))
    pref = text(identity.get("language_pref") or identity.get("preferred_language")).lower()
    if not pref and not customer:
        for turn in reversed(history_turns(merchant.get("conversation_history"))):
            if turn.get("from") == "merchant":
                body = text(turn.get("body"))
                if re.search(r"[\u0900-\u097f]", body):
                    return "hi"
                if re.search(r"\b(haan|mujhe|nahi|aap|chahiye)\b", body, re.I):
                    return "hinglish"
                break
        langs = identity.get("languages", [])
        pref = "hi-en mix" if isinstance(langs, list) and "hi" in langs else "en"
    if pref in {"hi", "hindi"}:
        return "hi"
    if "hi-en" in pref or "hindi" in pref or pref == "hinglish":
        return "hinglish"
    # English fallback is explicit in README for other regional languages.
    return "en"
