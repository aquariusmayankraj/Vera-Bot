import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vera.api import create_app
from vera.config import Settings

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-04-26T10:00:00Z"


@pytest.fixture
def seeds():
    base = ROOT / "challenge_reference" / "dataset"
    return {
        "categories": {p.stem: json.loads(p.read_text()) for p in (base / "categories").glob("*.json")},
        **{k: json.loads((base / f"{k}_seed.json").read_text())[k] for k in ("merchants", "customers", "triggers")},
    }


@pytest.fixture
def sample():
    return {
        "category": {"slug": "restaurants", "peer_stats": {"avg_ctr": 0.03}, "voice": {"tone": "warm_busy_practical"}, "digest": []},
        "merchant": {"merchant_id": "m1", "category_slug": "restaurants", "identity": {"name": "Demo Cafe", "owner_first_name": "Asha", "languages": ["en"], "verified": True},
                     "performance": {"window_days": 30, "calls": 20, "views": 800, "ctr": 0.025, "delta_7d": {"calls_pct": -0.4}},
                     "offers": [{"id": "o1", "title": "Lunch Thali @ ₹149", "status": "active"}], "conversation_history": []},
        "trigger": {"id": "t1", "merchant_id": "m1", "scope": "merchant", "kind": "perf_dip", "payload": {"metric": "calls", "delta_pct": -0.4, "window": "7d"},
                    "urgency": 3, "suppression_key": "dip:m1:week1", "expires_at": "2026-05-30T00:00:00Z"},
        "customer": {"customer_id": "c1", "merchant_id": "m1", "identity": {"name": "Priya", "language_pref": "english"},
                     "state": "lapsed_soft", "relationship": {"last_visit": "2026-03-10", "visits_total": 2},
                     "preferences": {"channel": "whatsapp", "reminder_opt_in": True, "preferred_slots": "weekday_evening"},
                     "consent": {"opted_in_at": "2026-01-01", "scope": ["recall_reminders"]}},
    }


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "test.sqlite3")))
    with TestClient(app) as result:
        yield result


def push(client, scope, payload, version=1, context_id=None):
    key = {"category": "slug", "merchant": "merchant_id", "customer": "customer_id", "trigger": "id"}[scope]
    return client.post("/v1/context", json={"scope": scope, "context_id": context_id or payload[key], "version": version,
                                           "payload": copy.deepcopy(payload), "delivered_at": NOW})


def load(client, sample, customer=False):
    for scope in ("category", "merchant", "trigger"):
        assert push(client, scope, sample[scope]).status_code == 200
    if customer:
        assert push(client, "customer", sample["customer"]).status_code == 200


def tick(client, ids=None, now=NOW):
    return client.post("/v1/tick", json={"now": now, "available_triggers": ids if ids is not None else ["t1"]})


def reply(client, conv, message, turn=2, mid="m1", cid=None, stamp="2026-04-26T10:01:00Z"):
    return client.post("/v1/reply", json={"conversation_id": conv, "merchant_id": mid, "customer_id": cid,
        "from_role": "customer" if cid else "merchant", "message": message, "received_at": stamp, "turn_number": turn})
