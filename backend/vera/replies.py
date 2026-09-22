"""Multi-turn state machine; all 'work' is a visible draft, never a fake API action."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from .composer import build_plan
from .policy import active_offers, promotional_permission
from .utils import choose_language, human, iso, obj, text

AUTO_PATTERNS = (
    "thank you for contacting", "thanks for contacting", "our team will respond",
    "we will get back to you", "we'll get back to you", "this is an automated",
    "i am an automated", "i'm an automated", "automated response", "auto reply",
    "auto-reply", "aapka message prapt", "team tak pahucha", "team tak pahuncha",
)


def classify(message: str, prior_inbound: list[str]) -> str:
    lower = re.sub(r"\s+", " ", message.strip().lower()).replace("’", "'")
    if not lower:
        return "empty"
    if re.search(r"\b(?:don't|do not) (?:message|contact|send)|\bstop (?:messaging|sending|contacting)|\bunsubscribe\b|\b(?:band karo|mat bhejo|nahi chahiye|nahin chahiye)\b|संदेश बंद|मैसेज बंद|संपर्क मत", lower) or re.fullmatch(r"(?:please )?stop[.! ]*", lower):
        return "stop"
    if any(p in lower for p in AUTO_PATTERNS) or sum(re.sub(r"\s+", " ", x.strip().lower()) == lower for x in prior_inbound) >= 2:
        return "auto"
    if re.search(r"\b(?:not now|not today|busy|later|tomorrow|kal|baad mein|baad me)\b|बाद में|कल|अभी नहीं", lower) or re.search(r"(?:in|after) \d+ (?:min|hour)", lower):
        return "delay"
    if re.search(r"\b(?:not interested|no thanks|no thank you|leave me alone|go away|don't want|do not want|don't renew|do not renew)\b|नहीं चाहिए|दिलचस्पी नहीं", lower) or lower in {"no", "nahin", "nahi", "nope", "नहीं"}:
        return "decline"
    if re.search(r"\b(?:ignore.*instructions|system prompt|reveal.*secret|api.key|password|otp)\b", lower):
        return "unsafe_request"
    if re.search(r"\b(?:gst|tax return|politics|weather|bitcoin|cricket score|write.*poem|prescribe|dosage|diagnose)\b", lower):
        return "off_topic"
    if re.search(r"\b(?:fuck|idiot|stupid|useless spam|scam|bakwas|bekaar)\b|बकवास", lower):
        return "hostile"
    if re.search(r"\b(?:join|onboard|sign up|signup|register|judna|judrna|jurna)\b|जुड़ना|रजिस्टर", lower):
        return "join"
    if re.search(r"\b(?:price|pricing|cost|charge|kitna|rate)\b|कीमत|कितना", lower):
        return "price"
    if re.search(r"\b(?:is it done|did you publish|is it booked|already sent|have you sent)\b|हो गया", lower):
        return "execution_status"
    if re.search(r"\b(?:yes|yeah|yep|haan|han|please send|send (?:it|me|the)|go ahead|let'?s do it|lets do it|proceed|start|bhejo|kar do|karo|theek hai|confirm|what'?s next|whats next)\b|हाँ|हां|भेजो|कर दो|करें", lower) or lower in {"ok", "okay", "sure", "1"}:
        return "accept"
    if re.search(r"\b(?:thank you|thanks|dhanyavaad|shukriya|bye)\b|धन्यवाद|शुक्रिया", lower):
        return "thanks"
    return "details"


def respond(state: dict, recipient: dict, merchant: dict, category: dict, trigger: dict,
            customer: dict | None, message: str, now: datetime) -> tuple[dict, str]:
    """Mutates only supplied transaction-local state. Returns (response, intent)."""
    history = state.setdefault("messages", [])
    prior = [m["body"] for m in history if m.get("role") in {"merchant", "customer"}]
    intent = classify(message, prior)
    # A concrete callback time after the onboarding question is an execution
    # detail, not automatically a request to delay the current conversation.
    if state.get("stage") == "onboarding_detail" and intent == "delay":
        if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|morning|afternoon|evening", message, re.I) and not re.search(r"busy|message me|later|baad mein", message, re.I):
            intent = "details"
    language = choose_language(merchant, customer, message)

    def say(en: str, mixed: str, hi: str | None = None) -> str:
        return (hi or mixed) if language == "hi" else mixed if language == "hinglish" else en

    def send(body: str, cta: str, why: str) -> dict:
        if any(m.get("role") == "bot" and m.get("body") == body for m in history):
            return {"action": "end", "rationale": "Avoid repeating a previously delivered response."}
        return {"action": "send", "body": body, "cta": cta, "rationale": why}

    if intent == "stop":
        recipient["opt_out"] = True
        return {"action": "end", "rationale": "Explicit STOP: recipient-level opt-out stored; no further proactive outreach."}, intent
    if recipient.get("opt_out"):
        return {"action": "end", "rationale": "Recipient has opted out; no implicit re-enrolment from a later reply."}, intent
    if intent == "auto":
        state["auto_detected"] = True
        recipient["snooze_until"] = iso(now + timedelta(hours=24))
        return {"action": "end", "rationale": "Automated/canned reply detected; exit immediately without opening a human session or asking another question."}, intent
    if intent == "delay":
        seconds = 1800
        match = re.search(r"(\d+)\s*(minutes?|mins?|hours?|hrs?)", message, re.I)
        if match:
            seconds = int(match.group(1)) * (3600 if match.group(2).lower().startswith(("h",)) else 60)
        elif re.search(r"tomorrow|\bkal\b|कल", message, re.I):
            seconds = 86400
        elif "hour" in message.lower():
            seconds = 3600
        seconds = min(86400, max(60, seconds))
        recipient["snooze_until"] = iso(now + timedelta(seconds=seconds))
        return {"action": "wait", "wait_seconds": seconds, "rationale": "Recipient asked for time; backoff recorded for future ticks."}, intent
    if intent in {"decline", "hostile"}:
        recipient["snooze_until"] = iso(now + timedelta(days=7))
        return {"action": "end", "rationale": "Recipient declined or is hostile; exit without arguing and pause proactive contact."}, intent
    if intent in {"off_topic", "unsafe_request"}:
        state["off_topic_count"] = state.get("off_topic_count", 0) + 1
        if state["off_topic_count"] > 1:
            return {"action": "end", "rationale": "Repeated off-topic or unsafe request; no ungrounded professional advice or secrets."}, intent
        return send(say("I can help with this business's listing, message drafts and customer-request preparation. I do not handle tax filing, medical prescribing or account credentials. The current draft remains unchanged.",
                        "Main business listing, message drafts aur customer-request preparation mein help karti hoon. Tax filing, medical prescription ya account credentials handle nahi karti. Current draft unchanged hai.",
                        "मैं व्यवसाय की लिस्टिंग, संदेशों के ड्राफ्ट और ग्राहक अनुरोध तैयार करने में सहायता करती हूँ। टैक्स फ़ाइलिंग, दवा लिखना या खाते के पासवर्ड संभालना इस सेवा में शामिल नहीं है।"),
                    "none", "Scope-bounded response; no argument or fabricated external capability."), intent
    if intent == "execution_status":
        return send(say("Only the draft/request in this conversation is prepared. Nothing has been published, sent to customers, paid for or booked by this bot.",
                        "Sirf is conversation ka draft/request prepare hua hai. Is bot ne publish, customer ko send, payment ya booking nahi ki hai.",
                        "केवल इस बातचीत में ड्राफ्ट/अनुरोध तैयार हुआ है। इस बॉट ने प्रकाशन, ग्राहक को संदेश, भुगतान या बुकिंग नहीं की है।"),
                    "none", "Transparent distinction between drafting and real-world execution."), intent
    name = text(obj(merchant.get("identity")).get("name")) or "your business"
    if intent == "join":
        state["stage"] = "onboarding_detail"
        return send(say(f"Here is the onboarding request draft for {name}. Next, share the owner/manager's preferred callback time. No registration or callback has been submitted yet; do not share passwords or OTPs.",
                        f"{name} ke liye onboarding request draft ready hai. Next, owner/manager ka preferred callback time bataiye. Registration ya callback abhi submit nahi hua hai; password ya OTP share na karein.",
                        f"{name} के लिए जुड़ने के अनुरोध का ड्राफ्ट तैयार है। अगला कदम: मालिक/मैनेजर का पसंदीदा कॉलबैक समय बताइए। अभी रजिस्ट्रेशन या कॉलबैक भेजा नहीं गया है; पासवर्ड या OTP साझा न करें।"),
                    "open_ended", "Explicit joining intent goes directly to one execution detail, not re-qualification."), intent
    if intent == "price":
        offers = active_offers(merchant, customer, now)
        if customer and not promotional_permission(customer):
            offers = []  # Do not quietly broaden the supplied outreach consent.
        title = text(offers[0].get("title")) if offers else ""
        body = say(f"The supplied active offer is {title}. The merchant must confirm eligibility and availability; no additional charge details were supplied." if title else "No applicable confirmed price is present in the supplied context. The merchant needs to confirm the price before any booking or payment.",
                   f"Supplied active offer {title} hai. Eligibility aur availability merchant confirm karega; extra charges ki details nahi di gayi hain." if title else "Supplied context mein applicable confirmed price nahi hai. Booking ya payment se pehle merchant ko price confirm karna hoga.")
        return send(body, "none", "Returns only known eligible prices; no category-catalog substitution."), intent
    if intent == "thanks":
        return {"action": "end", "rationale": "Acknowledgement received; no unnecessary follow-up nudge."}, intent
    if intent == "empty":
        return {"action": "wait", "wait_seconds": 1800, "rationale": "No actionable message received."}, intent

    stage = state.get("stage", "offered")
    if stage == "onboarding_detail" and intent == "details":
        state["stage"] = "fulfilled"
        detail = text(message, 240)
        return send(say(f"Updated onboarding request draft for {name}: preferred callback details — {detail}. This is recorded in this conversation only; a human/operator still needs to submit it through an authorized channel.",
                        f"{name} ka onboarding request draft update: callback details — {detail}. Yeh sirf is conversation mein noted hai; authorized channel par human/operator ko submit karna hoga."),
                    "none", "Carries user-provided execution detail forward without claiming a real handoff."), intent
    if intent == "accept":
        # Re-compose from latest pushed contexts: never return an outdated cached price/digest.
        plan = build_plan(category, merchant, trigger, customer, now=now)
        if plan.suppressed and trigger.get("id") != "reply_only":
            return send(say("The earlier suggestion is no longer actionable with the current context. I have not booked, published or sent anything; the merchant needs to confirm updated details.",
                            "Current context ke saath pehle wali suggestion ab actionable nahi hai. Maine booking, publishing ya sending nahi ki; updated details merchant confirm karega."),
                        "none", "New context/expiry revoked the earlier plan; stale facts not reused."), intent
        if stage == "fulfilled":
            return {"action": "end", "rationale": "Requested draft already delivered; do not loop or pretend to execute it."}, intent
        draft = plan.draft or state.get("draft")
        if not draft:
            if customer:
                draft = say(f"Request draft for {name}: please review the customer's preferred follow-up time. No booking is confirmed. What time should the request include?",
                            f"{name} ke liye request draft: preferred follow-up time review karein. Booking confirm nahi hai. Request mein kaunsa time add karein?")
            else:
                draft = say(f"Here is a listing-review draft for {name}: confirm business details and current offer availability before publishing. What single detail should be updated first?",
                            f"{name} ke liye listing-review draft: publish se pehle business details aur offer availability confirm karein. Sabse pehle kaunsi detail update karni hai?")
        state["stage"] = "fulfilled"
        state["draft"] = draft
        return send(draft, "open_ended" if draft.rstrip().endswith("?") else "none",
                    "Acceptance fulfilled with an actual draft from current context; no additional qualifying question or invented completion."), intent

    detail = text(message, 240)
    if not detail:
        return send(say("That text cannot be used as a business detail. The draft is unchanged.", "Yeh text business detail ke roop mein use nahi hua. Draft unchanged hai."), "none", "Treats instruction-like data as untrusted."), intent
    if stage == "fulfilled":
        updated = f"{state.get('draft', '')}\nMerchant/customer supplied revision: {detail}"
        if len(updated) > 6000:
            return {"action": "end", "rationale": "Draft revision limit reached; avoid unbounded conversation growth."}, intent
        state["draft"] = updated
        return send(say(f"Updated review draft:\n{updated}\nNot published or booked.", f"Updated review draft:\n{updated}\nPublish ya booking nahi hui hai."),
                    "none", "Incorporates the user's actual revision without treating it as a verified external fact."), intent
    state["draft"] = f"Draft for {name}: customer/merchant-supplied focus — {detail}. Confirm availability and any price before use."
    state["stage"] = "fulfilled"
    return send(say(f"Here is the draft using your input: {state['draft']}", f"Aapke input ke saath draft: {state['draft']}"),
                "none", "Answers the business detail with concrete draft progress rather than a repetitive pitch."), intent
