"""Fail-closed outreach rules; these are challenge policies, not legal advice."""
from __future__ import annotations

import re
from datetime import datetime

from .utils import history_turns, number, obj, parse_dt, rows, text

CONSENT_SCOPES: dict[str, set[str]] = {
    "recall_due": {"recall_reminders"},
    "customer_lapsed_soft": {"recall_reminders", "winback_offers"},
    "customer_lapsed_hard": {"winback_offers"},
    "appointment_tomorrow": {"appointment_reminders"},
    "appointment_reminder": {"appointment_reminders"},
    "chronic_refill_due": {"refill_reminders"},
    "refill_due": {"refill_reminders"},
    "wedding_package_followup": {"bridal_package_followup"},
    "trial_followup": {"kids_program_updates", "program_updates", "trial_followup", "treatment_followup"},
    "treatment_followup": {"treatment_followup"},
    "renewal_due": {"renewal_reminders"},
    "supply_alert": {"recall_alerts"},
    "recall_alert": {"recall_alerts"},
    "festival_upcoming": {"promotional_offers"},
    "ipl_match_today": {"match_night_specials", "promotional_offers"},
    "program_update": {"program_updates", "kids_program_updates"},
    "customer_winback": {"winback_offers"},
}

ALIASES = {
    "category_research_digest_release": "research_digest",
    "research_digest_release": "research_digest",
    "scheduled_recurring": "curious_ask_due",
    "category_trend_movement": "trend_movement",
}


def kind_of(trigger: dict) -> str:
    kind = text(trigger.get("kind"), 100)
    return ALIASES.get(kind, kind)


def customer_permission(customer: dict, trigger: dict, now: datetime | None = None) -> tuple[bool, str]:
    consent, prefs = obj(customer.get("consent")), obj(customer.get("preferences"))
    if consent.get("revoked") or consent.get("revoked_at") or consent.get("opted_out") or consent.get("opted_out_at"):
        return False, "customer consent revoked"
    if prefs.get("reminder_opt_in") is False:
        return False, "customer explicitly disabled outreach"
    if text(prefs.get("channel")).lower() not in {"whatsapp", "whatsapp_via_parent", "whatsapp_via_son", "whatsapp_via_guardian"}:
        return False, "no consented WhatsApp channel"
    opted = parse_dt(consent.get("opted_in_at"))
    if opted is None or (now is not None and opted > now):
        return False, "missing or future consent timestamp"
    scopes = consent.get("scope", [])
    scopes = {scopes} if isinstance(scopes, str) else {str(x) for x in scopes} if isinstance(scopes, list) else set()
    required = CONSENT_SCOPES.get(kind_of(trigger))
    if not required or not scopes.intersection(required):
        return False, "missing purpose-specific customer consent"
    return True, "purpose-specific consent verified"


def promotional_permission(customer: dict) -> bool:
    scopes = obj(customer.get("consent")).get("scope", [])
    return isinstance(scopes, list) and bool(set(str(x) for x in scopes) & {"promotional_offers", "winback_offers", "match_night_specials"})


def eligibility(category: dict, merchant: dict, trigger: dict, customer: dict | None, now: datetime | None) -> str | None:
    if not category or not merchant:
        return "category or merchant context is missing"
    payload = obj(trigger.get("payload"))
    mid = trigger.get("merchant_id") or payload.get("merchant_id")
    if mid and merchant.get("merchant_id") and mid != merchant.get("merchant_id"):
        return "trigger/merchant identity mismatch"
    if trigger.get("scope") == "customer" and customer is None:
        return "customer context is missing"
    if customer is not None:
        if customer.get("merchant_id") != merchant.get("merchant_id"):
            return "customer does not belong to this merchant"
        cid = trigger.get("customer_id") or payload.get("customer_id")
        if cid and cid != customer.get("customer_id"):
            return "trigger/customer identity mismatch"
        allowed, reason = customer_permission(customer, trigger, now)
        if not allowed:
            return reason
    if now is not None:
        expiry = parse_dt(trigger.get("expires_at"))
        if expiry and now >= expiry:
            return "trigger expired in simulated time"
        for key in ("not_before", "starts_at", "available_from", "scheduled_at"):
            start = parse_dt(trigger.get(key) or payload.get(key))
            if start and now < start:
                return f"trigger {key} is in the future"
        # An explicit recall/service due date is not a license to message months early.
        if customer and kind_of(trigger) in {"recall_due", "chronic_refill_due", "refill_due"}:
            due = parse_dt(payload.get("due_date") or payload.get("stock_runs_out_iso"))
            if due and (due - now).total_seconds() > 14 * 86400:
                return "recall/refill is outside the 14-day reminder window"
        if kind_of(trigger) == "ipl_match_today":
            match = parse_dt(payload.get("match_time_iso"))
            if match and now.astimezone(match.tzinfo).date() != match.date():
                return "match-day trigger is not for the simulated local date"
    return None


def active_offers(merchant: dict, customer: dict | None = None, now: datetime | None = None, topic: str = "") -> list[dict]:
    result = []
    for offer in rows(merchant.get("offers")):
        title = text(offer.get("title"))
        if offer.get("status") != "active" or not title or offer.get("available") is False:
            continue
        # Never advertise medical guarantees, even when upstream copy contains them.
        if re.search(r"guaranteed|miracle|100% safe|completely cure|best in city", title, re.I):
            continue
        start = parse_dt(offer.get("valid_from") or offer.get("started"))
        end = parse_dt(offer.get("valid_until") or offer.get("expires_at") or offer.get("ended"))
        if now and ((start and now < start) or (end and now >= end)):
            continue
        if customer:
            visits = number(obj(customer.get("relationship")).get("visits_total")) or 0
            if offer.get("audience") in {"new_user", "new_customer"} and visits > 0:
                continue
            if offer.get("audience") in {"repeat_user", "existing_customer"} and visits == 0:
                continue
        if now:
            # These are the explicit weekday conditions present in the supplied catalog.
            from zoneinfo import ZoneInfo
            try:
                zone = ZoneInfo(text(obj(merchant.get("identity")).get("timezone")) or "Asia/Kolkata")
            except (KeyError, ValueError):
                zone = ZoneInfo("Asia/Kolkata")
            day = now.astimezone(zone).weekday()
            lower = title.lower().replace("–", "-").replace("—", "-")
            if ("weekday" in lower and day > 4) or ("weekend" in lower and day < 5):
                continue
            if re.search(r"tue(?:sday)?\s*-\s*thu(?:rsday)?", lower) and day not in {1, 2, 3}:
                continue
            allowed_days = offer.get("available_days", offer.get("valid_days"))
            if isinstance(allowed_days, list):
                names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                if names[day] not in {str(d).lower()[:3] for d in allowed_days}:
                    continue
        result.append(offer)
    keywords = set(re.findall(r"[a-z]{4,}", topic.lower()))
    result.sort(key=lambda o: (
        -len(keywords & set(re.findall(r"[a-z]{4,}", text(o.get("title")).lower()))),
        0 if "₹" in text(o.get("title")) else 1,
        text(o.get("id")) or text(o.get("title")),
    ))
    return result


def open_session(merchant: dict, customer: dict | None, last_human: str | None, now: datetime) -> bool:
    timestamps = [parse_dt(last_human)]
    context = customer if customer else merchant
    expected_role = "customer" if customer else "merchant"
    for turn in history_turns(context.get("conversation_history")):
        if turn.get("from", turn.get("role")) == expected_role:
            from .replies import classify  # Runtime import avoids a module cycle.
            if classify(text(turn.get("body")), []) != "auto":
                timestamps.append(parse_dt(turn.get("ts") or turn.get("received_at")))
    return any(ts is not None and 0 <= (now - ts).total_seconds() < 86400 for ts in timestamps)


def priority(trigger: dict, merchant: dict) -> int:
    kind = kind_of(trigger)
    urgency = max(1, min(5, number(trigger.get("urgency")) or 1))
    weights = {"supply_alert": 60, "regulation_change": 50, "active_planning_intent": 45,
               "appointment_tomorrow": 40, "chronic_refill_due": 38, "recall_due": 35,
               "review_theme_emerged": 25, "perf_dip": 20, "renewal_due": 15}
    score = int(urgency * 10) + weights.get(kind, 0)
    if kind == "renewal_due" and obj(merchant.get("identity")).get("verified") is False:
        score -= 10  # Fix a concrete account blocker rather than pressuring renewal.
    return score
