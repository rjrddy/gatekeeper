"""Actual HTTP proxy, webhook replay and SIGKILL recovery, in isolated child processes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from gatekeeper.store import Store


def exercise(client: httpx.Client, restart=None) -> dict:
    def get():
        r = client.get("/api/state")
        r.raise_for_status()
        return r.json()["rollout"]

    def routed():
        r = client.get("/demo/value?x=7")
        r.raise_for_status()
        return {"body": r.json(), "upstream": r.headers["x-gatekeeper-upstream"]}

    rows = []
    before = routed()
    assert before["body"] == {"value": 14}
    for candidate, expected in [
        ("candidate-bad", "rolled_back"),
        ("candidate-good", "promoted"),
        ("candidate-slow", "rolled_back"),
    ]:
        epoch = get()["epoch"]
        started = time.perf_counter()
        r = client.post("/api/canary", json={"candidate": candidate, "expected_epoch": epoch})
        r.raise_for_status()
        assert (
            client.post(
                "/api/canary", json={"candidate": candidate, "expected_epoch": epoch}
            ).status_code
            == 409
        )
        deadline = time.monotonic() + 10
        while (state := get())["state"] == "probing" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert state["state"] == expected, state
        after = routed()
        assert after["body"] == {"value": 14}, after
        assert after["upstream"] == ("stable" if candidate == "candidate-bad" else "candidate-good")
        rows.append(
            {
                "candidate": candidate,
                "state": state,
                "proxy_after": after,
                "observed_seconds": time.perf_counter() - started,
            }
        )
    recovery = None
    if restart:
        epoch = get()["epoch"]
        client.post(
            "/api/canary", json={"candidate": "candidate-slow", "expected_epoch": epoch}
        ).raise_for_status()
        assert get()["state"] == "probing"
        restart()
        state = get()
        assert state["state"] == "recovered" and state["epoch"] == epoch + 2, state
        assert routed()["upstream"] == "candidate-good"
        recovery = {
            "fault": "SIGKILL API while probing; new process, same SQLite file",
            "state": state,
            "proxy_after": routed(),
        }
    return {
        "initial": before,
        "canaries": rows,
        "recovery": recovery,
        "scope": "Actual local HTTP behavior; x=0..11, per-upstream timeout .25s. No fleet claim.",
    }


def main() -> None:
    owned: list[subprocess.Popen] = []
    with tempfile.TemporaryDirectory(prefix="gatekeeper-proxy-") as tmp:
        env = dict(
            os.environ,
            GK_PASSWORD=secrets.token_urlsafe(32),
            GK_TOKEN=secrets.token_urlsafe(32),
            GK_WEBHOOK_SECRET=secrets.token_urlsafe(32),
            GK_DATABASE=tmp + "/state.db",
        )
        log = open("docs/results/http-processes.log", "w")

        def spawn(module: str, port: int, mode="good"):
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                module,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "info",
            ]
            if module.endswith("create_app"):
                cmd += ["--factory"]
            p = subprocess.Popen(cmd, env={**env, "GK_SERVICE_MODE": mode}, stdout=log, stderr=log)
            owned.append(p)
            with httpx.Client(trust_env=False) as c:
                for _ in range(100):
                    try:
                        if c.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                            return p
                    except httpx.HTTPError:
                        pass
                    if p.poll() is not None:
                        raise RuntimeError("server exited; see process log")
                    time.sleep(0.05)
            raise RuntimeError("readiness timeout")

        try:
            for port, mode in [(18301, "good"), (18302, "good"), (18303, "bad"), (18304, "slow")]:
                spawn("gatekeeper.demo_service:app", port, mode)
            api = spawn("gatekeeper.app:create_app", 18300)

            def restart():
                api.kill()
                api.wait(timeout=5)
                spawn("gatekeeper.app:create_app", 18300)

            with httpx.Client(
                base_url="http://127.0.0.1:18300",
                trust_env=False,
                timeout=5,
                headers={"Authorization": "Bearer " + env["GK_TOKEN"]},
            ) as client:
                outcome = exercise(client, restart)
                public = json.loads(Path("docs/results/public-unlabeled.json").read_text())
                replay = []
                for row in public:
                    body = json.dumps(
                        {
                            "repository": {"full_name": row["repo"]},
                            "workflow_run": {
                                "id": row["run_id"],
                                "run_attempt": 1,
                                "head_sha": row["sha"],
                                "status": "completed",
                                "conclusion": "failure",
                            },
                        }
                    ).encode()
                    sig = hmac.new(
                        env["GK_WEBHOOK_SECRET"].encode(), body, hashlib.sha256
                    ).hexdigest()
                    headers = {
                        "x-github-event": "workflow_run",
                        "x-github-delivery": str(row["run_id"]),
                        "x-hub-signature-256": "sha256=" + sig,
                    }
                    first = client.post("/api/github/webhook", content=body, headers=headers)
                    second = client.post("/api/github/webhook", content=body, headers=headers)
                    invalid = client.post(
                        "/api/github/webhook", content=body + b" ", headers=headers
                    )
                    assert first.json() == {"accepted": True} and second.json() == {
                        "accepted": False
                    }
                    assert invalid.status_code == 401
                    replay.append(
                        {
                            "run_id": row["run_id"],
                            "source_url": row["source_url"],
                            "first": first.json(),
                            "replay": second.json(),
                            "changed_bytes_status": invalid.status_code,
                        }
                    )
                client.post("/api/demo/analyze").raise_for_status()
                outcome["public_metadata_replays"] = replay
                outcome["audit_events"] = len(client.get("/api/state").json()["audit"])
                assert not Store(env["GK_DATABASE"]).finish(4, True, {})
            Path("docs/results/canary.json").write_text(json.dumps(outcome, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "canary_states": [r["state"]["state"] for r in outcome["canaries"]],
                        "restart": outcome["recovery"]["state"]["state"],
                        "public_metadata_runs": len(replay),
                    },
                    indent=2,
                )
            )
        finally:
            for p in owned:
                if p.poll() is None:
                    p.terminate()
            for p in owned:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=5)
            log.close()


if __name__ == "__main__":
    main()
