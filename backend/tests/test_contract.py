import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from vera.api import create_app
from vera.config import Settings
from conftest import NOW, load, push, reply, tick


def test_health_metadata_empty(client):
    health = client.get("/v1/healthz")
    assert health.status_code == 200
    assert health.json()["contexts_loaded"] == dict(category=0, merchant=0, customer=0, trigger=0)
    data = client.get("/v1/metadata").json()
    assert set(data) == {"team_name", "team_members", "model", "approach", "contact_email", "version", "submitted_at"}


def test_context_idempotent_and_atomic_replacement(client, sample):
    first = push(client, "merchant", sample["merchant"])
    mutated = copy.deepcopy(sample["merchant"])
    mutated["performance"]["views"] = 9999
    repeated = push(client, "merchant", mutated)
    assert first.json() == repeated.json()
    assert push(client, "merchant", mutated, 3).status_code == 200
    old = push(client, "merchant", sample["merchant"], 2)
    assert old.status_code == 409 and old.json()["current_version"] == 3
    with client.app.state.store.transaction() as db:
        stored = client.app.state.store.context(db, "merchant", "m1")
        assert stored["performance"]["views"] == 9999


def test_same_context_id_different_scope(client):
    assert push(client, "category", {"slug": "same"}).status_code == 200
    assert push(client, "merchant", {"merchant_id": "same"}).status_code == 200
    assert client.get("/v1/healthz").json()["contexts_loaded"]["merchant"] == 1


@pytest.mark.parametrize("change", [
    {"scope": "unsupported"}, {"version": 0}, {"version": True}, {"version": "1"},
    {"payload": []}, {"delivered_at": "invalid"}, {"delivered_at": "2026-04-26T10:00:00"}, {"context_id": ""},
])
def test_invalid_context_returns_400(client, change):
    payload = {"scope": "category", "context_id": "x", "version": 1, "payload": {}, "delivered_at": NOW}
    payload.update(change)
    assert client.post("/v1/context", json=payload).status_code == 400


def test_id_mismatch_and_invalid_nested(client, sample):
    assert push(client, "merchant", sample["merchant"], context_id="different").status_code == 400
    sample["merchant"]["performance"] = []
    assert push(client, "merchant", sample["merchant"]).status_code == 400


def test_bad_json_type_and_size(client):
    assert client.post("/v1/context", content="{", headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/v1/context", content="x", headers={"Content-Type": "text/plain"}).status_code == 415
    response = client.post("/v1/context", content=b" " * (500 * 1024 + 1), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_empty_tick_unknown_trigger(client):
    assert tick(client, []).json() == {"actions": []}
    assert tick(client, ["missing"]).json() == {"actions": []}


def test_action_shape_template_and_dedup(client, sample):
    load(client, sample)
    result = tick(client).json()["actions"]
    assert len(result) == 1
    action = result[0]
    required = {"conversation_id", "merchant_id", "customer_id", "send_as", "trigger_id", "template_name", "template_params", "body", "cta", "suppression_key", "rationale"}
    assert set(action) == required
    assert action["template_name"] == "vera_context_message_v1"
    assert action["body"] == "Vera update: " + action["template_params"][0]
    assert tick(client).json()["actions"] == []


def test_customer_and_merchant_suppressions_are_separate(client, sample):
    load(client, sample, customer=True)
    assert len(tick(client).json()["actions"]) == 1
    t = copy.deepcopy(sample["trigger"])
    t.update(id="tc", scope="customer", customer_id="c1", kind="recall_due", payload={"due_date": "2026-04-28", "service_due": "followup"})
    assert push(client, "trigger", t).status_code == 200
    action = tick(client, ["tc"]).json()["actions"][0]
    assert action["send_as"] == "merchant_on_behalf" and action["customer_id"] == "c1"


def test_expired_future_triggers(client, sample):
    load(client, sample)
    assert tick(client, now="2027-01-01T00:00:00Z").json()["actions"] == []
    sample["trigger"]["not_before"] = "2026-04-27T00:00:00Z"
    push(client, "trigger", sample["trigger"], 2)
    assert tick(client).json()["actions"] == []


def test_max_20_actions_and_distinct_conversations(client, sample):
    push(client, "category", sample["category"])
    ids = []
    for i in range(25):
        mid, tid = f"m{i}", f"t{i}"
        m, t = copy.deepcopy(sample["merchant"]), copy.deepcopy(sample["trigger"])
        m["merchant_id"] = mid
        t.update(id=tid, merchant_id=mid, suppression_key=f"dip:{i}")
        push(client, "merchant", m)
        push(client, "trigger", t)
        ids.append(tid)
    actions = tick(client, ids).json()["actions"]
    assert len(actions) == 20
    assert len({a["conversation_id"] for a in actions}) == 20
    assert len(tick(client, ids).json()["actions"]) == 5


def test_priority_one_per_target(client, sample):
    load(client, sample)
    t = copy.deepcopy(sample["trigger"])
    t.update(id="alert", kind="supply_alert", urgency=5, suppression_key="alert", payload={"molecule": "test-product", "affected_batches": ["batch-1"]})
    push(client, "trigger", t)
    actions = tick(client, ["t1", "alert"]).json()["actions"]
    assert len(actions) == 1 and actions[0]["trigger_id"] == "alert"


def test_concurrent_duplicate_ticks_are_atomic(client, sample):
    load(client, sample)
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: tick(client).json(), range(10)))
    assert sum(len(r["actions"]) for r in results) == 1


def test_restart_persists_context_and_suppression(tmp_path, sample):
    settings = Settings(db_path=str(tmp_path / "persistent.sqlite3"))
    with TestClient(create_app(settings)) as c:
        load(c, sample)
        assert len(tick(c).json()["actions"]) == 1
    with TestClient(create_app(settings)) as c:
        assert c.get("/v1/healthz").json()["contexts_loaded"]["merchant"] == 1
        assert tick(c).json()["actions"] == []


def test_teardown_disabled_by_default(client, sample):
    load(client, sample)
    tick(client)
    assert client.post("/v1/teardown").status_code == 403
    assert client.get("/v1/healthz").json()["contexts_loaded"]["merchant"] == 1


def test_optional_auth(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "auth.db"), api_token="secret", teardown_token="wipe"))) as c:
        assert c.get("/v1/healthz").status_code == 200
        assert tick(c).status_code == 401
        assert c.post("/v1/tick", json={"now": NOW}, headers={"Authorization": "Bearer secret"}).status_code == 200
        assert c.post("/v1/teardown", headers={"Authorization": "Bearer secret"}).status_code == 401
        assert c.post("/v1/teardown", headers={"Authorization": "Bearer wipe"}).status_code == 200


def test_reply_replay_and_conflict(client, sample):
    load(client, sample)
    conv = tick(client).json()["actions"][0]["conversation_id"]
    a = reply(client, conv, "Yes")
    b = reply(client, conv, "Yes")
    assert a.status_code == 200 and a.json() == b.json()
    assert reply(client, conv, "No").status_code == 409


def test_wrong_identity_role_and_old_turn(client, sample):
    load(client, sample)
    conv = tick(client).json()["actions"][0]["conversation_id"]
    assert reply(client, conv, "Yes", mid="another").status_code == 400
    assert reply(client, conv, "Yes", cid="c1").status_code == 400
    assert reply(client, conv, "Yes", turn=3).status_code == 200
    assert reply(client, conv, "Yes", turn=2).status_code == 409


def test_unknown_replay_conversation_with_known_merchant(client, sample):
    load(client, sample)
    response = reply(client, "new_replay", "Ok lets do it. Whats next?")
    assert response.status_code == 200
    assert response.json()["action"] == "send"
    assert "draft" in response.json()["body"].lower()


def test_freeform_only_after_real_human_reply(client, sample):
    sample["merchant"]["conversation_history"] = [{"from": "merchant", "body": "Hello", "ts": "2026-04-26T09:00:00Z"}]
    load(client, sample)
    a = tick(client).json()["actions"][0]
    assert a["template_name"] is None and a["template_params"] == []


def test_auto_reply_does_not_open_session(client, sample):
    sample["merchant"]["conversation_history"] = [{"from": "merchant", "body": "Thank you for contacting us", "ts": "2026-04-26T09:00:00Z"}]
    load(client, sample)
    a = tick(client).json()["actions"][0]
    assert a["template_name"] is not None


def test_missing_customer_not_accidentally_merchant_outreach(client, sample):
    sample["trigger"].update(scope="customer", customer_id="unknown")
    load(client, sample)
    assert tick(client).json()["actions"] == []


def test_top_level_and_nested_trigger_identity(client, sample):
    sample["trigger"]["payload"]["merchant_id"] = sample["trigger"].pop("merchant_id")
    load(client, sample)
    assert len(tick(client).json()["actions"]) == 1


def test_equal_version_does_not_overwrite_data(client, sample):
    load(client, sample)
    changed = copy.deepcopy(sample["merchant"])
    changed["performance"]["calls"] = 999
    push(client, "merchant", changed, 1)
    action = tick(client).json()["actions"][0]
    assert "999" not in action["body"] and "20 calls" in action["body"]
