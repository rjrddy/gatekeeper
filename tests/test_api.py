import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gatekeeper.app import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GK_PASSWORD", "synthetic-operator-password")
    monkeypatch.setenv("GK_TOKEN", "synthetic-machine-token-only-123456789")
    monkeypatch.setenv("GK_WEBHOOK_SECRET", "synthetic-webhook-secret-123456789")
    with TestClient(create_app(str(tmp_path / "g.db"))) as c:
        yield c


def test_auth_csrf_and_revocable_session(client: TestClient) -> None:
    assert client.get("/api/state").status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    response = client.post("/api/login", json={"password": "synthetic-operator-password"})
    assert response.status_code == 200
    csrf = response.json()["csrf"]
    assert client.get("/api/state").status_code == 200
    assert client.post("/api/demo/analyze").status_code == 403
    assert client.post("/api/demo/analyze", headers={"X-CSRF-Token": csrf}).status_code == 200
    saved = client.cookies.get("gk_session")
    assert client.post("/api/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    client.cookies.set("gk_session", saved)
    assert client.get("/api/state").status_code == 401


def test_webhook_exact_bytes_replay_and_conflict(client: TestClient) -> None:
    payload = {
        "repository": {"full_name": "synthetic/demo"},
        "workflow_run": {
            "id": 123,
            "run_attempt": 1,
            "head_sha": "a" * 40,
            "status": "completed",
            "conclusion": "failure",
        },
    }

    def send(body: dict, delivery: str, valid: bool = True):
        raw = json.dumps(body).encode()
        signature = (
            "sha256="
            + hmac.new(b"synthetic-webhook-secret-123456789", raw, hashlib.sha256).hexdigest()
        )
        return client.post(
            "/api/github/webhook",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-GitHub-Delivery": delivery,
                "X-Hub-Signature-256": signature if valid else "bad",
            },
        )

    assert send(payload, "one", False).status_code == 401
    assert send(payload, "one").json()["accepted"]
    assert not send(payload, "one").json()["accepted"]
    changed = json.loads(json.dumps(payload))
    changed["workflow_run"]["conclusion"] = "success"
    assert send(changed, "one").status_code == 409
    assert send(changed, "two").status_code == 409
    old = json.loads(json.dumps(payload))
    old["workflow_run"]["status"] = "queued"
    old["workflow_run"]["conclusion"] = None
    assert send(old, "three").status_code == 200


def test_input_bounds_and_no_arbitrary_upstream(client: TestClient) -> None:
    auth = {"Authorization": "Bearer synthetic-machine-token-only-123456789"}
    assert (
        client.post(
            "/api/canary", json={"candidate": "http://internal", "expected_epoch": 0}, headers=auth
        ).status_code
        == 422
    )
    assert client.post("/api/plans", json={}, headers=auth).status_code == 422
    assert client.post("/api/github/webhook", content=b"x" * 1_000_001).status_code == 413


def test_login_rate_limit_is_enforced(client: TestClient) -> None:
    for _ in range(10):
        assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 429


def test_proxy_unavailable_is_visible(client: TestClient) -> None:
    response = client.get(
        "/demo/value?x=7",
        headers={"Authorization": "Bearer synthetic-machine-token-only-123456789"},
    )
    assert response.status_code == 503


def test_incident_join_preserves_unknown_timestamp(client) -> None:
    headers = {"authorization": "Bearer synthetic-machine-token-only-123456789"}
    for row in [
        {"id": "a", "kind": "deploy", "at": 1, "component": "fixture", "summary": "release"},
        {"id": "b", "kind": "alert", "at": 2, "component": "fixture", "summary": "error rate"},
        {"id": "c", "kind": "log", "at": None, "component": "fixture", "summary": "missing clock"},
    ]:
        assert client.post("/api/events", json=row, headers=headers).status_code == 200
    result = client.get("/api/timeline", headers=headers).json()
    assert result["candidate"] == "a"
    assert result["events"][-1]["id"] == "c"


def test_dashboard_polling_does_not_exhaust_write_budget(client) -> None:
    headers = {"authorization": "Bearer synthetic-machine-token-only-123456789"}
    for _ in range(65):
        assert client.get("/api/state", headers=headers).status_code == 200
    assert client.post("/api/demo/analyze", headers=headers).status_code == 200
