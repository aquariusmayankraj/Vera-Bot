from __future__ import annotations

import copy
import json
from datetime import datetime

from .composer import build_plan
from .config import Settings
from .policy import eligibility, kind_of, open_session, priority
from .replies import classify, respond
from .schemas import ContextRequest, ReplyRequest, TickRequest
from .store import Store
from .templates import template_for
from .utils import UTC, canonical, history_turns, iso, obj, parse_dt, stable_id, text


class ServiceError(Exception):
    def __init__(self, status: int, reason: str, **details):
        self.status = status
        self.payload = {"accepted": False, "reason": reason, **details}
        super().__init__(reason)


class BotService:
    def __init__(self, store: Store, settings: Settings):
        self.store, self.settings = store, settings

    def push_context(self, req: ContextRequest) -> dict:
        payload = copy.deepcopy(req.payload)
        field = {"category": "slug", "merchant": "merchant_id", "customer": "customer_id", "trigger": "id"}[req.scope]
        if field in payload and payload[field] != req.context_id:
            raise ServiceError(400, "context_id_mismatch", details=f"payload.{field} must equal context_id")
        payload[field] = req.context_id
        if req.scope == "trigger":
            if payload.get("scope", "merchant") not in {"merchant", "customer"}:
                raise ServiceError(400, "invalid_trigger_scope")
            if "payload" in payload and not isinstance(payload["payload"], dict):
                raise ServiceError(400, "invalid_payload", details="trigger.payload must be an object")
        for key in ("identity", "performance", "subscription", "consent", "preferences", "relationship", "customer_aggregate", "peer_stats", "voice"):
            if key in payload and not isinstance(payload[key], dict):
                raise ServiceError(400, "invalid_payload", details=f"{key} must be an object")
        for key in ("offers", "digest", "review_themes"):
            if key in payload and (not isinstance(payload[key], list) or any(not isinstance(v, dict) for v in payload[key])):
                raise ServiceError(400, "invalid_payload", details=f"{key} must be a list of objects")
        try:
            serialized = canonical(payload)
        except (ValueError, TypeError):
            raise ServiceError(400, "invalid_payload", details="Payload must be finite JSON") from None
        with self.store.transaction() as db:
            current = db.execute("SELECT version,stored_at,ack_id FROM contexts WHERE scope=? AND id=?", (req.scope, req.context_id)).fetchone()
            if current and current["version"] > req.version:
                raise ServiceError(409, "stale_version", current_version=current["version"])
            if current and current["version"] == req.version:
                return {"accepted": True, "ack_id": current["ack_id"], "stored_at": current["stored_at"]}
            stored = iso(datetime.now(UTC))
            ack = stable_id("ack_", req.scope, req.context_id, req.version)
            db.execute("""INSERT INTO contexts VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(scope,id) DO UPDATE SET version=excluded.version,payload=excluded.payload,
                stored_at=excluded.stored_at,ack_id=excluded.ack_id,delivered_at=excluded.delivered_at""",
                       (req.scope, req.context_id, req.version, serialized, stored, ack, iso(req.delivered_at)))
            return {"accepted": True, "ack_id": ack, "stored_at": stored}

    @staticmethod
    def target(mid: str, cid: str | None) -> str:
        return canonical([mid, cid])

    def recipient(self, db, key: str, merchant: dict, customer: dict | None, now: datetime) -> dict:
        recipient = self.store.get(db, "recipients", key) or {
            "opt_out": False, "unanswered": 0, "last_proactive": None,
            "last_human": None, "snooze_until": None,
        }
        observed = set(recipient.get("history_processed", []))
        context = customer or merchant
        expected = "customer" if customer else "merchant"
        for turn in history_turns(context.get("conversation_history")):
            stamp = parse_dt(turn.get("ts") or turn.get("received_at"))
            if stamp is None or stamp > now:
                continue
            turn_key = stable_id("history_", turn)
            if turn_key in observed:
                continue
            observed.add(turn_key)
            role = turn.get("from", turn.get("role"))
            latest_outbound = parse_dt(recipient.get("last_proactive"))
            latest_human = parse_dt(recipient.get("last_human"))
            if role == expected:
                intent = classify(text(turn.get("body")), [])
                if intent == "stop":
                    recipient["opt_out"] = True
                if intent != "auto" and (not latest_human or stamp > latest_human):
                    recipient["last_human"] = iso(stamp)
                    if not latest_outbound or stamp >= latest_outbound:
                        recipient["unanswered"] = 0
            elif role in {"vera", "bot", "merchant_on_behalf"}:
                if not latest_outbound or stamp > latest_outbound:
                    recipient["last_proactive"] = iso(stamp)
                    if not latest_human or stamp > latest_human:
                        recipient["unanswered"] += 1
        recipient["history_processed"] = sorted(observed)[-200:]
        return recipient

    def tick(self, req: TickRequest) -> dict:
        actions = []
        with self.store.transaction() as db:
            candidates = []
            for tid in sorted(set(req.available_triggers)):
                trigger = self.store.context(db, "trigger", tid)
                if not trigger:
                    continue
                payload = obj(trigger.get("payload"))
                mid = text(trigger.get("merchant_id") or payload.get("merchant_id"), 240)
                cid = text(trigger.get("customer_id") or payload.get("customer_id"), 240) or None
                merchant = self.store.context(db, "merchant", mid)
                if not merchant:
                    continue
                slug = text(merchant.get("category_slug") or payload.get("category"), 240)
                category = self.store.context(db, "category", slug)
                customer = self.store.context(db, "customer", cid) if cid else None
                if not category or (cid and not customer):
                    continue
                if eligibility(category, merchant, trigger, customer, req.now):
                    continue
                candidates.append((priority(trigger, merchant), tid, mid, cid, category, merchant, trigger, customer))
            candidates.sort(key=lambda x: (-x[0], x[1], x[2], x[3] or ""))
            sent_targets: set[str] = set()
            for _, tid, mid, cid, category, merchant, trigger, customer in candidates:
                if len(actions) >= self.settings.max_actions:
                    break
                key = self.target(mid, cid)
                if key in sent_targets:
                    continue
                recipient = self.recipient(db, key, merchant, customer, req.now)
                self.store.put(db, "recipients", key, recipient)
                if recipient.get("opt_out") or recipient.get("unanswered", 0) >= self.settings.max_unanswered:
                    continue
                snooze = parse_dt(recipient.get("snooze_until"))
                if snooze and req.now < snooze:
                    continue
                last = parse_dt(recipient.get("last_proactive"))
                # Safety alerts can bypass cadence, but not consent, STOP or unanswered limits.
                if last and (req.now - last).total_seconds() < self.settings.min_gap_seconds and kind_of(trigger) not in {"supply_alert", "regulation_change"}:
                    continue
                plan = build_plan(category, merchant, trigger, customer, now=req.now)
                if plan.suppressed or not plan.body.strip():
                    continue
                result = plan.result(trigger, customer)
                if db.execute("SELECT 1 FROM suppressions WHERE target=? AND key=?", (key, result["suppression_key"])).fetchone():
                    continue
                # Different trigger ids with identical copy still do not cause repeated sends.
                history_key = stable_id("body_", plan.body)
                if db.execute("SELECT 1 FROM suppressions WHERE target=? AND key=?", (key, history_key)).fetchone():
                    continue
                if any(text(h.get("body"), 10000) == plan.body for h in history_turns((customer or merchant).get("conversation_history"))):
                    continue
                conv_id = stable_id("conv_", mid, cid, tid, result["suppression_key"])
                if self.store.get(db, "conversations", conv_id):
                    continue
                in_session = open_session(merchant, customer, recipient.get("last_human"), req.now)
                template_name, template_params, rendered = (None, [], plan.body) if in_session else template_for(bool(cid), plan.language, plan.body)
                result["body"] = rendered
                action = {"conversation_id": conv_id, "merchant_id": mid, "customer_id": cid,
                          "trigger_id": tid, "template_name": template_name,
                          "template_params": template_params, **result}
                conversation = {
                    "merchant_id": mid, "customer_id": cid, "trigger_id": tid,
                    "created_at": iso(req.now), "last_received": None, "last_turn": 0,
                    "status": "open", "stage": "offered", "task": plan.task,
                    "draft": plan.draft, "messages": [{"role": "bot", "body": rendered, "ts": iso(req.now)}],
                }
                self.store.put(db, "conversations", conv_id, conversation)
                recipient["last_proactive"] = iso(req.now)
                recipient["unanswered"] = recipient.get("unanswered", 0) + 1
                self.store.put(db, "recipients", key, recipient)
                db.execute("INSERT INTO suppressions VALUES(?,?)", (key, result["suppression_key"]))
                db.execute("INSERT OR IGNORE INTO suppressions VALUES(?,?)", (key, history_key))
                actions.append(action)
                sent_targets.add(key)
        return {"actions": actions}

    def reply(self, req: ReplyRequest) -> dict:
        fingerprint = stable_id("request_", req.model_dump(mode="json"))
        with self.store.transaction() as db:
            cached = db.execute("SELECT request_hash,response FROM reply_cache WHERE conversation_id=? AND turn_number=?", (req.conversation_id, req.turn_number)).fetchone()
            if cached:
                if cached["request_hash"] != fingerprint:
                    raise ServiceError(409, "reply_turn_conflict", details="Same conversation/turn was received with different content")
                return json.loads(cached["response"])
            state = self.store.get(db, "conversations", req.conversation_id)
            if state:
                mid, cid = state["merchant_id"], state.get("customer_id")
                if (req.merchant_id is not None and req.merchant_id != mid) or req.customer_id != cid:
                    raise ServiceError(400, "conversation_identity_mismatch")
                expected_role = "customer" if cid else "merchant"
                if req.from_role != expected_role:
                    raise ServiceError(400, "from_role_mismatch")
                if req.turn_number <= state.get("last_turn", 0):
                    raise ServiceError(409, "stale_turn")
                prior_time = parse_dt(state.get("last_received") or state.get("created_at"))
                if prior_time and req.received_at < prior_time:
                    raise ServiceError(409, "stale_reply_time")
            else:
                # The supplied official replay simulator starts fresh conversation IDs.
                mid, cid = req.merchant_id, req.customer_id
                if not mid:
                    raise ServiceError(400, "missing_merchant_id")
                if req.from_role != ("customer" if cid else "merchant"):
                    raise ServiceError(400, "from_role_mismatch")
                state = {"merchant_id": mid, "customer_id": cid, "trigger_id": "reply_only",
                         "stage": "offered", "status": "open", "last_turn": 0,
                         "created_at": iso(req.received_at), "messages": []}
            merchant = self.store.context(db, "merchant", mid)
            customer = self.store.context(db, "customer", cid) if cid else None
            if not merchant or (cid and not customer):
                raise ServiceError(404, "context_missing")
            if customer and customer.get("merchant_id") != mid:
                raise ServiceError(400, "customer_merchant_mismatch")
            category = self.store.context(db, "category", text(merchant.get("category_slug"))) or {}
            trigger = self.store.context(db, "trigger", state["trigger_id"]) or {"id": "reply_only", "kind": "reply_only", "scope": "customer" if cid else "merchant"}
            key = self.target(mid, cid)
            recipient = self.recipient(db, key, merchant, customer, req.received_at)
            if state.get("status") == "ended":
                response, intent = {"action": "end", "rationale": "Conversation already ended; no reactivation or repeat send."}, "closed"
                # A STOP received after an earlier end must still persist globally.
                if classify(req.message, []) == "stop":
                    recipient["opt_out"] = True
            else:
                response, intent = respond(state, recipient, merchant, category, trigger, customer, req.message, req.received_at)
            if intent not in {"auto", "closed", "empty"}:
                recipient["last_human"] = iso(req.received_at)
                recipient["unanswered"] = 0
            state.setdefault("messages", []).append({"role": req.from_role, "body": req.message, "ts": iso(req.received_at)})
            if response["action"] == "send":
                state["messages"].append({"role": "bot", "body": response["body"], "ts": iso(req.received_at)})
            elif response["action"] == "end":
                state["status"] = "ended"
            state["last_turn"] = req.turn_number
            state["last_received"] = iso(req.received_at)
            # Bounded transcript storage; reply replay-cache still prevents duplicate mutation.
            state["messages"] = state["messages"][-60:]
            self.store.put(db, "conversations", req.conversation_id, state)
            self.store.put(db, "recipients", key, recipient)
            db.execute("INSERT INTO reply_cache VALUES(?,?,?,?)", (req.conversation_id, req.turn_number, fingerprint, canonical(response)))
            return response
