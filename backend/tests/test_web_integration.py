"""Website/CORS/isolation regressions in addition to the original engine suite."""
import copy
import pytest
from fastapi.testclient import TestClient
from vera.api import create_app
from vera.config import Settings
from conftest import NOW


def make_context(scope, data):
    key = {"category": "slug", "merchant": "merchant_id", "trigger": "id"}[scope]
    return {"scope": scope, "context_id": data[key], "version": 1, "payload": data, "delivered_at": NOW}


def seed(client, sample, prefix="/demo/v1", headers=None):
    for scope in ("category", "merchant", "trigger"):
        response = client.post(prefix + "/context", json=make_context(scope, sample[scope]), headers=headers)
        assert response.status_code == 200, response.text


def emit(client, prefix="/demo/v1", headers=None):
    return client.post(prefix+"/tick", json={"now": NOW,"available_triggers": ["t1"]}, headers=headers)


@pytest.mark.parametrize("prefix", ["/demo/v1", "/v1"])
def test_all_five_endpoints(client, sample, prefix):
    assert client.get(prefix+"/healthz").json()["status"] == "ok"
    assert client.get(prefix+"/metadata").json()["model"]
    seed(client, sample, prefix)
    action = emit(client, prefix).json()["actions"][0]
    request = {"conversation_id": action["conversation_id"], "merchant_id": "m1", "customer_id": None,
               "from_role": "merchant", "message": "Yes", "received_at": "2026-04-26T10:01:00Z", "turn_number": 1}
    response = client.post(prefix+"/reply", json=request)
    assert response.status_code == 200
    assert response.json()["action"] in ("send", "wait", "end")
    assert client.post(prefix+"/reply", json=request).json() == response.json()


def test_demo_writes_do_not_change_judge(client, sample):
    seed(client, sample)
    assert client.get("/demo/v1/healthz").json()["contexts_loaded"]["merchant"] == 1
    assert client.get("/v1/healthz").json()["contexts_loaded"]["merchant"] == 0
    assert emit(client, "/v1").json()["actions"] == []
    assert len(emit(client).json()["actions"]) == 1
    # Identical IDs can be loaded independently without suppression leaking.
    seed(client, sample, "/v1")
    assert len(emit(client, "/v1").json()["actions"]) == 1


def test_judge_does_not_modify_demo(client, sample):
    seed(client, sample, "/v1")
    assert client.get("/demo/v1/healthz").json()["contexts_loaded"]["merchant"] == 0
    assert emit(client).json()["actions"] == []


@pytest.mark.parametrize("origin", ["https://studio.netlify.app", "http://localhost:5500"])
def test_wildcard_cors_preflight(client, origin):
    r=client.options("/demo/v1/reply", headers={"Origin": origin,"Access-Control-Request-Method":"POST",
        "Access-Control-Request-Headers":"content-type,authorization"})
    assert r.status_code==200
    assert r.headers["access-control-allow-origin"]=="*"
    assert "access-control-allow-credentials" not in r.headers


def test_explicit_cors_and_auth_error(tmp_path):
    settings=Settings(db_path=str(tmp_path/"one.db"),cors_origins=("https://studio.netlify.app",),api_token="private")
    with TestClient(create_app(settings)) as client:
        allowed={"Origin":"https://studio.netlify.app"}
        r=client.post("/demo/v1/tick",json={"now": NOW},headers=allowed)
        assert r.status_code==401
        assert r.headers["access-control-allow-origin"]==allowed["Origin"]
        r=client.options("/v1/tick",headers={"Origin":"https://other.netlify.app","Access-Control-Request-Method":"POST"})
        assert r.status_code==400
        assert "access-control-allow-origin" not in r.headers
        r=client.get("/v1/healthz",headers={"Origin":"https://other.netlify.app"})
        assert "access-control-allow-origin" not in r.headers


def test_cors_validation_and_content_type_errors(client):
    headers={"Origin":"https://studio.netlify.app"}
    r=client.post("/demo/v1/context",json={},headers=headers)
    assert r.status_code==400 and r.headers["access-control-allow-origin"]=="*"
    r=client.post("/demo/v1/tick",content="not json",headers=headers)
    assert r.status_code==415 and r.headers["access-control-allow-origin"]=="*"


def test_demo_disabled(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path/"one.db"),demo_enabled=False))) as c:
        assert c.get("/demo/v1/healthz").status_code==404
        assert c.post("/demo/v1/context",json={}).status_code==404
        assert c.get("/v1/healthz").status_code==200


def test_demo_uses_auth_for_writes(tmp_path,sample):
    with TestClient(create_app(Settings(db_path=str(tmp_path/"one.db"),api_token="private"))) as c:
        assert c.post("/demo/v1/context",json=make_context("merchant",sample["merchant"])).status_code==401
        seed(c,sample,headers={"Authorization":"Bearer private"})
        assert len(emit(c,headers={"Authorization":"Bearer private"}).json()["actions"])==1


def test_backend_root_is_html_with_link(client):
    r=client.get("/")
    assert r.status_code==200 and "text/html" in r.headers["content-type"]
    assert "FRONTEND_URL" in r.text and "/v1/healthz" in r.text


@pytest.mark.parametrize("url,valid", [
    ("https://studio.netlify.app",True),
    ('https://studio.netlify.app/?x=\"/><script>alert(1)</script>',True),
    ("javascript:alert(1)",False),
    ("https://u:secret@studio.netlify.app",False),
])
def test_root_escapes_frontend_link(tmp_path,url,valid):
    with TestClient(create_app(Settings(db_path=str(tmp_path/"one.db"),frontend_url=url))) as c:
        text=c.get("/").text
        assert ("Open chat interface" in text)==valid
        assert "<script>alert(1)</script>" not in text


def test_demo_and_judge_persist_separately(tmp_path,sample):
    settings=Settings(db_path=str(tmp_path/"main.db"))
    with TestClient(create_app(settings)) as c:
        seed(c,sample); emit(c)
    with TestClient(create_app(settings)) as c:
        assert c.get("/demo/v1/healthz").json()["contexts_loaded"]["merchant"]==1
        assert c.get("/v1/healthz").json()["contexts_loaded"]["merchant"]==0
        assert emit(c).json()["actions"]==[]


def test_teardown_token_wipes_only_judge(tmp_path,sample):
    with TestClient(create_app(Settings(db_path=str(tmp_path/"one.db"),teardown_token="delete-secret"))) as c:
        seed(c,sample); seed(c,sample,"/v1")
        assert c.post("/v1/teardown").status_code==401
        assert c.post("/v1/teardown",headers={"Authorization":"Bearer delete-secret"}).status_code==200
        assert c.get("/v1/healthz").json()["contexts_loaded"]["merchant"]==0
        assert c.get("/demo/v1/healthz").json()["contexts_loaded"]["merchant"]==1


def test_same_disk_db_rejected(tmp_path):
    path=str(tmp_path/"same.db")
    with pytest.raises(ValueError,match="different"):
        with TestClient(create_app(Settings(db_path=path,demo_db_path=path))):
            pass


def test_separate_memory_stores(sample):
    with TestClient(create_app(Settings(db_path=":memory:"))) as c:
        seed(c,sample)
        assert c.get("/v1/healthz").json()["contexts_loaded"]["merchant"]==0


def test_environment_configuration(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS","https://site.netlify.app/, http://localhost:5500")
    monkeypatch.setenv("DEMO_ENABLED","false")
    monkeypatch.setenv("FRONTEND_URL","https://site.netlify.app")
    s=Settings.from_env()
    assert s.cors_origins==("https://site.netlify.app","http://localhost:5500")
    assert not s.demo_enabled
    assert s.frontend_url=="https://site.netlify.app"
