"""Pure, deterministic composition. No network, random values, or wall-clock reads.

`now` is optional for standalone composition. HTTP callers always supply the
judge's simulated time. Empty/suppressed plans are NOT outbound messages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .policy import active_offers, eligibility, kind_of, promotional_permission
from .utils import choose_language, date_label, fmt, history_turns, human, number, obj, parse_dt, pct, rows, text


@dataclass
class Plan:
    body: str = ""
    cta: str = "none"
    rationale: str = ""
    task: str = "review"
    draft: str = ""
    language: str = "en"
    suppressed: bool = False

    def result(self, trigger: dict, customer: dict | None) -> dict:
        from .utils import stable_id
        result = {
            "body": self.body,
            "cta": self.cta,
            "send_as": "merchant_on_behalf" if customer else "vera",
            "suppression_key": text(trigger.get("suppression_key"), 500) or stable_id("trigger_", trigger),
            "rationale": self.rationale,
        }
        if self.suppressed:
            result["suppressed"] = True
        return result


def select_digest(category: dict, merchant: dict, trigger: dict) -> dict:
    payload = obj(trigger.get("payload"))
    if obj(payload.get("top_item")):
        return payload["top_item"]
    refs = [payload.get(k) for k in ("top_item_id", "digest_item_id", "alert_id") if payload.get(k)]
    digest = rows(category.get("digest"))
    if refs:
        return next((d for d in digest if d.get("id") in refs), {})
    kind = kind_of(trigger)
    desired = {"research_digest": {"research", "tech", "trend"}, "regulation_change": {"compliance"},
               "cde_opportunity": {"cde"}, "category_seasonal": {"seasonal"}, "supply_alert": {"alert", "supply"}}
    candidates = [d for d in digest if d.get("kind") in desired.get(kind, {d.get("kind") for d in digest})]
    if not candidates:
        return {}
    signals = " ".join(text(s) for s in merchant.get("signals", []) if isinstance(s, str)) if isinstance(merchant.get("signals"), list) else ""
    recent = " ".join(text(t.get("body")) for t in history_turns(merchant.get("conversation_history"))[-3:])
    tokens = set(re.findall(r"[a-z]{4,}", (signals + " " + recent).lower()))
    return sorted(candidates, key=lambda d: (
        -len(tokens & set(re.findall(r"[a-z]{4,}", (text(d.get("title")) + " " + text(d.get("patient_segment"))).lower()))),
        text(d.get("id")),
    ))[0]


def build_plan(category: dict, merchant: dict, trigger: dict, customer: dict | None = None,
               *, now: datetime | None = None) -> Plan:
    language = choose_language(merchant, customer)

    def say(en: str, mixed: str, hi: str | None = None) -> str:
        return (hi or mixed) if language == "hi" else mixed if language == "hinglish" else en

    def suppress(reason: str) -> Plan:
        return Plan(rationale=f"Suppressed: {reason}.", language=language, suppressed=True)

    reason = eligibility(category, merchant, trigger, customer, now)
    if reason:
        return suppress(reason)
    p = obj(trigger.get("payload"))
    kind = kind_of(trigger)
    slug = text(category.get("slug") or merchant.get("category_slug"))
    identity = obj(merchant.get("identity"))
    name = text(identity.get("name"), 180) or "your business"
    first = text(identity.get("owner_first_name"), 80)
    greeting = ("Dr. " + first if slug == "dentists" and first and not first.startswith("Dr.") else first) or name
    perf, peer, aggregate = obj(merchant.get("performance")), obj(category.get("peer_stats")), obj(merchant.get("customer_aggregate"))
    locality = text(identity.get("locality"), 100)
    offer_time = parse_dt(p.get("match_time_iso")) or now
    offers = active_offers(merchant, customer, offer_time, text(p.get("service_due") or p.get("intent_topic") or kind))
    offer = text(offers[0].get("title")) if offers else ""
    window_days = number(perf.get("window_days"))
    snapshot_label = f"Latest {fmt(window_days)}-day snapshot" if window_days is not None else "Latest snapshot"
    task, draft, cta = kind, "", "binary_yes_no"
    hook, ask, why = "", "", ""

    if customer:
        ci, rel, preferences = obj(customer.get("identity")), obj(customer.get("relationship")), obj(customer.get("preferences"))
        customer_name = text(ci.get("name"), 100) or "there"
        parent = re.search(r"\(parent:\s*([^)]*)\)", customer_name, re.I)
        if parent:
            child_name = customer_name[:parent.start()].strip()
            customer_name = text(parent.group(1))
            intro = say(f"Hi {customer_name}, {name} here about {child_name}.",
                        f"Hi {customer_name}, {name} se, {child_name} ke liye message hai.",
                        f"नमस्ते {customer_name}, {name} की ओर से {child_name} के लिए संदेश है।")
        else:
            intro = say(f"Hi {customer_name}, {name} here.", f"Hi {customer_name}, {name} se message hai.",
                        f"नमस्ते {customer_name}, {name} की ओर से संदेश है।")
        slots = rows(p.get("available_slots") or p.get("next_session_options"))
        valid_slots = [s for s in slots if not now or not parse_dt(s.get("iso")) or parse_dt(s.get("iso")) >= now]
        # Expose one real slot, preserving a single primary action; do not claim a reservation.
        slot = date_label(valid_slots[0].get("iso") or valid_slots[0].get("label")) if valid_slots else ""
        preferred = human(preferences.get("preferred_slots"))
        preference_note = say(f"Your preference is {preferred}.", f"Aapki preference {preferred} hai.",
                              f"आपकी पसंद {preferred} है।") if preferred else ""
        if kind in {"chronic_refill_due", "refill_due"}:
            if slug != "pharmacies":
                return suppress("refill trigger does not match pharmacy category")
            due = date_label(p.get("stock_runs_out_iso") or p.get("due_date"))
            last_refill = date_label(p.get("last_refill"))
            if not (due or last_refill):
                return suppress("no refill timing supplied")
            # Do not expose diagnoses or medicine lists on shared-family channels.
            hook = say(f"Your refill reminder is for {due or 'the refill last recorded on ' + last_refill}.",
                       f"Aapka refill reminder {due or last_refill} ke liye hai.",
                       f"आपका रीफिल रिमाइंडर {due or last_refill} के लिए है।")
            ask = say("Should the pharmacy check availability against your existing prescription? Reply YES.",
                      "Existing prescription ke hisaab se pharmacy se availability check karvani hai? Reply YES.",
                      "मौजूदा प्रिस्क्रिप्शन के अनुसार उपलब्धता की जाँच का अनुरोध तैयार करें? YES लिखें।")
            draft = say("Refill-check request drafted for pharmacy review. Stock, prescription validity and delivery are not yet confirmed.",
                        "Pharmacy review ke liye refill-check request draft hai. Stock, prescription validity aur delivery abhi confirm nahi hain.",
                        "फ़ार्मेसी की समीक्षा के लिए रीफिल-जाँच का अनुरोध तैयार है। स्टॉक, प्रिस्क्रिप्शन की वैधता और डिलीवरी की पुष्टि नहीं हुई है।")
            why = "Purpose-specific refill consent; minimal disclosure on shared channels; no stock, delivery or clinical claims."
        elif kind in {"appointment_tomorrow", "appointment_reminder"}:
            appointment = obj(p.get("appointment"))
            when = date_label(p.get("appointment_at") or p.get("appointment_time") or appointment.get("iso") or appointment.get("starts_at"))
            if not when:
                return suppress("appointment timing was not provided; cannot invent a booking")
            hook = say(f"The appointment on your record is {when}.", f"Aapke record mein appointment {when} par hai.", f"आपके रिकॉर्ड में अपॉइंटमेंट {when} पर है।")
            ask = say("Does this time still work? Reply YES.", "Yeh time abhi bhi theek hai? Reply YES.", "क्या यह समय अभी भी ठीक है? YES लिखें।")
            draft = say(f"Your confirmation for {when} is recorded in this conversation. The merchant's booking system has not been updated by this bot.",
                        f"{when} ke liye confirmation is conversation mein note hai. Booking system is bot se update nahi hua hai.")
            why = "Existing appointment timestamp only; single confirmation, no invented booking."
        elif kind == "wedding_package_followup":
            if slug != "salons":
                return suppress("bridal follow-up does not match salon category")
            wedding = date_label(p.get("wedding_date") or preferences.get("wedding_date"))
            trial = date_label(p.get("trial_completed") or rel.get("last_visit"))
            if not wedding:
                return suppress("wedding date missing")
            hook = say(f"Following your trial on {trial}, your wedding date is recorded as {wedding}.",
                       f"{trial} ke trial ke baad, aapki wedding date {wedding} noted hai.")
            ask = say("Shall we prepare the next consultation request around your schedule? Reply YES.",
                      "Aapke schedule ke hisaab se next consultation request draft karein? Reply YES.")
            draft = say(f"Consultation request draft for {name}: wedding date {wedding}; trial {trial}. No package price or appointment is confirmed. What date suits you?",
                        f"{name} ke liye consultation request draft: wedding {wedding}; trial {trial}. Package price aur appointment confirm nahi hain. Kaunsi date theek rahegi?")
            why = "Bridal-follow-up consent and actual dates; no invented package or artificial urgency."
        elif kind == "trial_followup":
            trial = date_label(p.get("trial_date"))
            if not trial:
                return suppress("trial details are missing")
            hook = say(f"Following the trial on {trial}. {preference_note}", f"{trial} ke trial ka follow-up hai. {preference_note}")
            ask = say(f"Shall we draft a request for {slot}? Reply YES." if slot else "Shall we prepare a follow-up session request? Reply YES.",
                      f"{slot} ke liye request draft karein? Reply YES." if slot else "Follow-up session ki request draft karein? Reply YES.")
            draft = say(f"Session request draft: {name}; following trial {trial}; requested time {slot or preferred or 'to be agreed'}. Availability requires the studio's confirmation.",
                        f"Session request draft: {name}; trial {trial}; requested time {slot or preferred or 'confirm hona hai'}. Studio ki availability confirmation pending hai.")
            why = "Uses the trial record and actual slot, routes child context to parent when supplied."
        elif kind in {"recall_due", "customer_lapsed_soft", "customer_lapsed_hard", "customer_winback", "treatment_followup"}:
            if customer.get("state") == "churned":
                return suppress("customer marked churned; avoid unsolicited winback")
            if kind == "recall_due":
                service = human(p.get("service_due"))
                due = date_label(p.get("due_date"))
                if not service and not due:
                    return suppress("recall schedule is missing")
                hook = say(f"Your {service or 'follow-up'} recall is recorded for {due}." if due else f"Your record flags a {service} follow-up.",
                           f"Aapka {service or 'follow-up'} recall {due} ke liye noted hai." if due else f"Aapke record mein {service} follow-up hai.")
            else:
                last = date_label(rel.get("last_visit"))
                days = number(p.get("days_since_last_visit"))
                if not last and days is None:
                    return suppress("no relationship timing supplied")
                hook = say(f"Your last visit was {fmt(days)} days ago." if days is not None else f"Your last recorded visit was {last}.",
                           f"Aapka last visit {fmt(days)} din pehle tha." if days is not None else f"Aapka last recorded visit {last} tha.")
                if slug == "gyms":
                    hook += say(" A restart can be at your own pace, without pressure.", " Apni pace par restart kar sakte hain, koi pressure nahi.")
            if preference_note:
                hook += " " + preference_note
            if offer and promotional_permission(customer) and "trial" not in offer.lower():
                hook += say(f" Listed active offer: {offer}.", f" Listed active offer: {offer}.")
            ask = say(f"Shall we draft a request for {slot}? Reply YES." if slot else "Shall we prepare a suitable-time request for the team? Reply YES.",
                      f"{slot} ke liye request draft karein? Reply YES." if slot else "Team ke liye suitable-time request draft karein? Reply YES.",
                      f"{slot} के लिए अनुरोध तैयार करें? YES लिखें।" if slot else "टीम के लिए उपयुक्त समय का अनुरोध तैयार करें? YES लिखें।")
            draft = say(f"Request draft for {name}: follow-up, preferred time {slot or preferred or 'to be agreed'}. This is not a confirmed booking.",
                        f"{name} ke liye request draft: follow-up, preferred time {slot or preferred or 'confirm hona hai'}. Yeh confirmed booking nahi hai.")
            why = "Consent-specific reminder, relationship timing, preference and real supplied availability; no pressure or fabricated slots."
        else:
            return suppress("no safe customer message recipe for this trigger and consent scope")
        return Plan(" ".join(x for x in (intro, hook, ask) if x), cta, why, task, draft, language)

    if kind in {"research_digest", "regulation_change", "cde_opportunity"}:
        item = select_digest(category, merchant, trigger)
        title, source = text(item.get("title"), 240), text(item.get("source"), 180)
        if not title:
            return suppress("referenced digest item is not in the supplied context")
        summary = text(item.get("summary"), 480)
        hook = say(f"The shared digest flags: {title}.", f"Shared digest mein yeh update hai: {title}.", f"साझा डाइजेस्ट में यह अपडेट है: {title}।")
        if summary and kind == "research_digest":
            hook += " " + summary
        if source:
            hook += f" Source: {source}."
        if kind == "research_digest":
            cohort = number(aggregate.get("high_risk_adult_count"))
            if cohort is not None and "high_risk" in text(item.get("patient_segment")):
                hook += say(f" Your records include {fmt(cohort)} high-risk adults.", f" Aapke records mein {fmt(cohort)} high-risk adults hain.")
            trial = number(item.get("trial_n"))
            if trial is not None:
                hook += f" Reported sample: {fmt(trial)}."
            ask = say("Shall I turn this supplied summary into a review-ready team note? Reply YES.",
                      "Is supplied summary ka review-ready team note draft bhejun? Reply YES.",
                      "क्या इस सारांश का टीम की समीक्षा के लिए नोट तैयार करूँ? YES लिखें।")
            draft = say(f"Team review note — {title}\nSupplied summary: {summary or 'No full summary was provided.'}\nSource in context: {source or 'not provided'}.\nVerify the original source and applicability before changing practice. No full paper or abstract was retrieved.",
                        f"Team review note — {title}\nSupplied summary: {summary or 'Full summary context mein nahi hai.'}\nContext source: {source or 'nahi diya gaya'}.\nPractice change se pehle original source aur applicability verify karein. Full paper ya abstract retrieve nahi kiya gaya.")
        elif kind == "regulation_change":
            deadline = date_label(p.get("deadline_iso"))
            if deadline:
                hook += say(f" Supplied deadline: {deadline}.", f" Di gayi deadline: {deadline}.")
            ask = say("Shall I draft a verification checklist for your team? Reply YES.", "Team ke liye verification checklist draft bhejun? Reply YES.", "क्या टीम के लिए जाँच सूची तैयार करूँ? YES लिखें।")
            draft = f"Verification checklist — {title}\nSource supplied: {source or 'not provided'}.\nRead the original notice; identify whether it applies to your setup; record any required changes and the responsible person. {text(item.get('actionable'))}\nThis is a draft for professional review, not a verified legal/compliance determination."
        else:
            when = date_label(item.get("date"))
            credits = item.get("credits", p.get("credits"))
            if when:
                hook += " " + when + "."
            if number(credits) is not None:
                hook += f" {fmt(credits)} listed credits."
            ask = say("Shall I share the event details from this digest? Reply YES.", "Is digest se event details bhejun? Reply YES.")
            draft = f"Event details from the shared digest: {title}. {when}. {summary} {text(item.get('actionable'))} Source: {source or 'not supplied'}. Registration and eligibility are not confirmed by this bot."
        why = "Retrieved the referenced/newly supplied digest, attributed its source, and avoided claiming external verification or completed action."
    elif kind == "supply_alert":
        batches = p.get("affected_batches", [])
        batches = [text(b, 70) for b in batches if text(b)] if isinstance(batches, list) else []
        molecule, manufacturer = text(p.get("molecule")), text(p.get("manufacturer"))
        if not batches or not molecule:
            return suppress("supply alert lacks product/batch identification")
        hook = say(f"Received stock alert: {molecule}, batches {', '.join(batches)}.", f"Stock alert mila hai: {molecule}, batches {', '.join(batches)}.", f"स्टॉक अलर्ट मिला है: {molecule}, बैच {', '.join(batches)}।")
        if manufacturer:
            hook += f" Manufacturer in trigger: {manufacturer}."
        hook += say(" Check the original notice against your stock records before making claims to customers.", " Customer ko claim bhejne se pehle original notice aur stock records match karein.")
        ask = say("Shall I draft the batch-verification checklist? Reply YES.", "Batch-verification checklist draft bhejun? Reply YES.", "क्या बैच की जाँच सूची तैयार करूँ? YES लिखें।")
        draft = f"Batch-verification checklist: match {molecule}, {manufacturer}, batches {', '.join(batches)} against the original notice and stock register; have the responsible pharmacist review the match and the notice's instructions. No customer is identified as affected; no stock action has been performed."
        why = "Highest-priority supply signal; uses trigger-specific batch identifiers; does not infer patient exposure or reconcile conflicting manufacturer records."
    elif kind in {"perf_dip", "perf_spike", "seasonal_perf_dip"}:
        metric = text(p.get("metric"))
        delta = number(p.get("delta_pct"))
        deltas = obj(perf.get("delta_7d"))
        if delta is None:
            choices = [(key.removesuffix("_pct"), number(value)) for key, value in deltas.items()]
            choices = [(key, value) for key, value in choices if value is not None and (value < 0 if kind != "perf_spike" else value > 0)]
            if choices:
                metric, delta = sorted(choices, key=lambda x: (-abs(x[1]), x[0]))[0]
        if delta is None:
            return suppress("no matching performance movement in trigger or current merchant data")
        metric = metric or "performance"
        movement = "down" if delta < 0 else "up"
        window = human(p.get("window")) or "7-day comparison"
        hook = say(f"{metric.capitalize()} are {movement} {pct(delta)} in the {window}.",
                   f"{window} mein aapke {metric} {pct(delta)} {movement} hain.", f"{window} में आपके {metric} {pct(delta)} {movement} हैं।")
        current = number(perf.get(metric))
        if current is not None:
            hook += say(f" {snapshot_label}: {fmt(current)} {metric}.",
                        f" {snapshot_label}: {fmt(current)} {metric}.")
        ctr, benchmark = number(perf.get("ctr")), number(peer.get("avg_ctr"))
        if kind == "seasonal_perf_dip" and p.get("is_expected_seasonal"):
            hook += say(" The trigger marks this as an expected seasonal dip, not a diagnosis of poor service.", " Trigger ise expected seasonal dip mark karta hai, poor service ka proof nahi.")
        if ctr is not None and benchmark is not None:
            hook += f" CTR {pct(ctr)} vs category benchmark {pct(benchmark)}."
        if identity.get("verified") is False:
            hook += say(" Your profile is also unverified; address that blocker before paying for more reach.", " Profile bhi unverified hai; extra promotion se pehle yeh blocker check karein.")
            task = "gbp_unverified"
            draft = "Profile verification checklist: open the merchant-owned Google Business Profile; check the verification methods Google currently offers; verify name/address/contact data; let the owner complete the verification. No verification has been performed by this bot."
        else:
            if offer:
                hook += say(f" Your active offer is {offer}.", f" Aapka active offer {offer} hai.")
            draft = f"Review draft for {name}: the {metric} movement is {movement} {pct(delta)} in {window}. Check the current listing, enquiry handling and offer visibility before attributing a cause. " + (f"Use only the listed active offer: {offer}. " if offer else "No active merchant offer was supplied. ") + "This is a proposed review, not a completed account update."
        ask = say("Shall I send a focused checklist for this issue? Reply YES.", "Is issue ki focused checklist bhejun? Reply YES.", "क्या इस समस्या की जाँच सूची भेजूँ? YES लिखें।")
        why = "Uses event delta and latest snapshot without conflating their windows; treats benchmark scope and causal uncertainty explicitly."
    elif kind == "active_planning_intent":
        topic = human(p.get("intent_topic"))
        if not topic:
            return suppress("planning topic is missing")
        if "thali" in topic and offer:
            outline = f"{name} — proposed corporate lunch enquiry: {offer}. Bulk quantity, delivery terms and any corporate price need your approval."
            ask = say("What minimum order quantity should the draft use?", "Draft mein minimum order quantity kya rakhein?")
        elif "kids" in topic and "yoga" in topic:
            outline = f"{name} — proposed kids-yoga enquiry post: age-appropriate sessions with parent consent; age group, instructor availability, schedule and fees to be approved."
            ask = say("Which age group should the draft target?", "Draft mein kaunsa age group target karein?")
        else:
            outline = f"{name} — draft outline for {topic}: audience, service, timing and pricing to be confirmed by the merchant."
            ask = say("What is the first operating detail to include?", "Sabse pehle kaunsi operating detail add karein?")
        hook = say(f"Here is the requested draft, not another sales pitch: {outline}", f"Aapke request ka draft yeh hai: {outline}")
        draft, cta = outline, "open_ended"
        why = "Merchant already expressed planning intent; supplies an actual draft and asks only one execution detail; no invented pricing."
    elif kind == "ipl_match_today":
        match = text(p.get("match"))
        when = date_label(p.get("match_time_iso"))
        if not match or not when:
            return suppress("match identity or time is missing")
        hook = say(f"{match} is listed for {when}; {locality or name} has a match-day planning window.", f"{match}, {when} par listed hai; {locality or name} ke liye match-day planning ka mauka hai.")
        issues = [x for x in rows(merchant.get("review_themes")) if "delivery" in text(x.get("theme")) and x.get("sentiment") == "neg"]
        if issues:
            hook += say(f" Your reviews include {fmt(issues[0].get('occurrences_30d'))} delivery concerns; avoid unconfirmed delivery-time promises.",
                        f" Reviews mein {fmt(issues[0].get('occurrences_30d'))} delivery concerns hain; unconfirmed delivery-time promise na karein.")
        if offer:
            hook += " " + offer + "."
        else:
            hook += say(" No offer is confirmed as eligible for this match date.", " Is match date ke liye eligible offer confirm nahi hai.")
        ask = say("Shall I draft a pickup-enquiry post without a delivery guarantee? Reply YES.", "Delivery guarantee ke bina pickup-enquiry post draft bhejun? Reply YES.")
        draft = f"Draft post for {name}: Planning for {match} on {when}? Contact {name} to check pickup availability. " + (f"Listed eligible offer: {offer}. " if offer else "") + "Merchant to confirm operating hours and order capacity before publishing."
        why = "Match/time and operational review context; respects weekday restrictions and does not fabricate a match-night discount."
    elif kind == "review_theme_emerged":
        theme = human(p.get("theme"))
        count = number(p.get("occurrences_30d"))
        if not theme:
            themes = sorted(rows(merchant.get("review_themes")), key=lambda t: (t.get("sentiment") != "neg", -(number(t.get("occurrences_30d")) or 0)))
            if themes:
                theme, count = human(themes[0].get("theme")), number(themes[0].get("occurrences_30d"))
        if not theme:
            return suppress("review theme was not supplied")
        hook = say(f"{fmt(count)} reviews in 30 days mention {theme}." if count is not None else f"Your supplied reviews flag {theme}.",
                   f"30 din mein {fmt(count)} reviews mein {theme} mention hua hai." if count is not None else f"Aapke supplied reviews mein {theme} flag hua hai.")
        ask = say("Shall I draft a calm response addressing that issue? Reply YES.", "Is issue ke liye calm review-response draft bhejun? Reply YES.")
        draft = f"Review reply draft: Thank you for sharing your experience with {name}. We have noted your concern about {theme}. Please contact the business directly with your visit/order details so the team can look into it."
        why = "Addresses the actual recurring review issue instead of proposing an unrelated discount."
    elif kind == "milestone_reached":
        current, target = number(p.get("value_now")), number(p.get("milestone_value"))
        metric = human(p.get("metric")) or "reviews"
        if current is None or target is None:
            return suppress("milestone counts are missing; no milestone invented")
        if current < target:
            hook = say(f"Your {metric} count is {fmt(current)} — {fmt(target-current)} short of {fmt(target)}.",
                       f"Aapka {metric} count {fmt(current)} hai — {fmt(target)} se {fmt(target-current)} kam.")
        else:
            hook = say(f"Your {metric} count is {fmt(current)}, crossing the {fmt(target)} milestone.",
                       f"Aapka {metric} count {fmt(current)} hai; {fmt(target)} milestone cross ho gaya.")
        ask = say("Shall I draft a neutral feedback request for recent visitors? Reply YES.", "Recent visitors ke liye neutral feedback request draft bhejun? Reply YES.")
        draft = f"Feedback request draft: Thank you for visiting {name}. Your honest feedback helps our team understand your experience. No incentive or positive-rating requirement."
        why = "Distinguishes approaching from achieved milestones; no incentivized or fabricated reviews."
    elif kind == "competitor_opened":
        competitor = text(p.get("competitor_name"))
        distance = number(p.get("distance_km"))
        if not competitor:
            return suppress("competitor identity missing")
        hook = say(f"The supplied local update lists {competitor}" + (f" {fmt(distance)} km away." if distance is not None else "."),
                   f"Local update mein {competitor} listed hai" + (f", {fmt(distance)} km door." if distance is not None else "."))
        if offer:
            hook += say(f" Your actual offer is {offer}; no need to invent a lower price.", f" Aapka actual offer {offer} hai; lower price invent karne ki zaroorat nahi.")
        ask = say("Shall I draft a listing message around your own service rather than a price war? Reply YES.", "Price war ki jagah apni service par listing draft bhejun? Reply YES.")
        draft = f"Listing draft for {name}, {locality}: " + (f"{offer}. " if offer else "Contact the business for current service details. ") + "No comparative quality or superiority claim; merchant review required before publishing."
        why = "Uses supplied competitor identity only; preserves merchant pricing and avoids unsupported comparative claims."
    elif kind == "curious_ask_due":
        if offer:
            hook = say(f"Your listing currently features {offer}.", f"Aapki listing par {offer} hai.")
        elif number(perf.get("calls")) is not None:
            hook = say(f"{snapshot_label}: {fmt(perf['calls'])} calls.", f"Latest snapshot mein {fmt(perf['calls'])} calls hain.")
        ask = say("Which service are people asking for most this week?" if slug != "restaurants" else "Which dish are people asking for most this week?",
                  "Is hafte sabse zyada kis service ki enquiry aa rahi hai?" if slug != "restaurants" else "Is hafte sabse zyada kis dish ki enquiry aa rahi hai?")
        cta = "open_ended"
        draft = ""
        why = "Merchant-specific, low-effort curiosity prompt; one question, no invented demand statistic."
    elif kind in {"dormant_with_vera", "winback_eligible"}:
        lapsed = next((number(aggregate.get(k)) for k in ("lapsed_90d_plus", "lapsed_180d_plus") if number(aggregate.get(k)) is not None), None)
        if lapsed is not None:
            hook = say(f"Your current records show {fmt(lapsed)} lapsed customers; a consent-filtered follow-up draft may be more useful than another renewal nudge.",
                       f"Aapke current records mein {fmt(lapsed)} lapsed customers hain; renewal nudge ki jagah consent-filtered follow-up draft useful ho sakta hai.")
        elif number(perf.get("calls")) is not None:
            hook = say(f"Your latest snapshot shows {fmt(perf['calls'])} calls. Let's restart with one listing check, not a sales pitch.",
                       f"Latest snapshot mein {fmt(perf['calls'])} calls hain. Sales pitch ki jagah ek listing check se restart karte hain.")
        else:
            return suppress("no current merchant signal for a useful re-engagement")
        ask = say("Shall I send a review-only follow-up draft? Reply YES.", "Review ke liye follow-up draft bhejun? Reply YES.")
        draft = f"Follow-up draft for merchant review: Hi, {name} here. Let us know when a visit would suit you. Send only to customers with an applicable, current outreach consent; no audience has been contacted."
        why = "Uses current customer/performance data and avoids repeating subscription pressure; consent filtering remains mandatory."
    elif kind == "renewal_due":
        subscription = obj(merchant.get("subscription"))
        days = number(subscription.get("days_remaining", p.get("days_remaining")))
        plan_name = text(subscription.get("plan") or p.get("plan"))
        if days is None:
            return suppress("renewal timing missing")
        hook = say(f"Your {plan_name or 'current'} plan has {fmt(days)} days remaining.", f"Aapke {plan_name or 'current'} plan mein {fmt(days)} din bache hain.")
        if identity.get("verified") is False:
            hook += say(" Your profile is still unverified; review that blocker before deciding about renewal.", " Profile abhi unverified hai; renewal decision se pehle yeh blocker check karein.")
        amount = number(p.get("renewal_amount"))
        if amount is not None:
            hook += f" Listed renewal amount: ₹{fmt(amount)}."
        ask = say("Shall I summarize the account facts for your renewal decision? Reply YES.", "Renewal decision ke liye account facts summarize karun? Reply YES.")
        draft = f"Renewal review for {name}: plan {plan_name or 'not supplied'}; {fmt(days)} days remaining; views {fmt(perf.get('views')) or 'not supplied'}; calls {fmt(perf.get('calls')) or 'not supplied'}. No payment or renewal was performed."
        why = "Current subscription facts; no invented ROI, payment link, auto-renewal or high-pressure close."
    elif kind == "gbp_unverified":
        if identity.get("verified") is not False and p.get("verified") is not False:
            return suppress("unverified status is not supported")
        hook = say(f"{name}'s supplied profile record is unverified.", f"{name} ka supplied profile record unverified hai.", f"{name} का साझा प्रोफ़ाइल रिकॉर्ड अभी असत्यापित है।")
        if number(perf.get("views")) is not None:
            hook += say(f" Latest snapshot: {fmt(perf['views'])} views.", f" Latest snapshot: {fmt(perf['views'])} views.")
        ask = say("Shall I send an owner-verification checklist? Reply YES.", "Owner-verification checklist bhejun? Reply YES.", "क्या मालिक के लिए सत्यापन की जाँच सूची भेजूँ? YES लिखें।")
        draft = "Owner-verification checklist: open your business profile from your own account; check the methods currently offered; confirm business name/address/contact details; complete the available verification steps yourself. Do not share passwords or OTPs. This bot has not changed or verified your profile."
        why = "Uses actual verification state; ignores unvalidated uplift estimates and does not invent current platform verification requirements."
    elif kind in {"festival_upcoming", "category_seasonal", "weather_heatwave", "local_news_event", "trend_movement"}:
        if kind == "festival_upcoming":
            festival, when = text(p.get("festival")), date_label(p.get("date"))
            if not festival or not when:
                return suppress("festival identity/date missing")
            hook = say(f"The supplied calendar lists {festival} on {when}; this is planning, not a last-minute urgency claim.",
                       f"Supplied calendar mein {festival}, {when} par hai; abhi planning hai, last-minute urgency nahi.")
        elif kind == "category_seasonal":
            trends = p.get("trends", [])
            trend = "; ".join(human(t) for t in trends[:3]) if isinstance(trends, list) else ""
            if not trend:
                item = select_digest(category, merchant, trigger)
                trend = text(item.get("title"))
            if not trend:
                return suppress("seasonal signal missing")
            hook = say(f"The supplied category signal is {trend}. This is category-level demand, not your store's sales.",
                       f"Supplied category signal: {trend}. Yeh category-level demand hai, aapki store sales nahi.")
        else:
            fact = text(p.get("headline") or p.get("title") or p.get("summary") or p.get("query"))
            if not fact:
                return suppress("no usable factual event detail")
            hook = say(f"The supplied update for {locality or name}: {fact}.", f"{locality or name} ke liye supplied update: {fact}.")
        if offer:
            hook += say(f" Your listed offer is {offer}.", f" Aapka listed offer {offer} hai.")
        ask = say("Shall I prepare a merchant-review planning note? Reply YES.", "Merchant-review ke liye planning note draft bhejun? Reply YES.")
        draft = f"Planning note for {name}: {hook} Confirm service relevance, availability and timing before using this in a campaign. No campaign has been launched."
        why = "Grounded calendar/category signal with explicit scope and uncertainty; no invented urgency or store-specific sales uplift."
    else:
        # Adaptive unknown triggers: use only explicit event facts, never random category filler.
        fact = text(p.get("headline") or p.get("title") or p.get("summary"))
        if not fact:
            return suppress("unknown trigger has no usable factual headline")
        hook = say(f"A new supplied update for {name}: {fact}.", f"{name} ke liye naya supplied update: {fact}.")
        ask = say("Shall I turn this into a review note? Reply YES.", "Iska review note draft bhejun? Reply YES.")
        draft = f"Review note for {name}: {fact}. Confirm relevance and any missing operational details before acting."
        why = "Handles unseen trigger through its explicit event facts; no unsupported extrapolation."
    return Plan(f"{greeting}, {' '.join(x for x in (hook, ask) if x)}", cta, why, task, draft, language)


def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None,
            *, now: datetime | None = None) -> dict:
    """Challenge-compatible composition; `now` enables extra simulated-time gates."""
    return build_plan(category, merchant, trigger, customer, now=now).result(trigger, customer)
