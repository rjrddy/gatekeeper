"""Independent-clone Compose exercises real service containers, not a pointer-only fake."""

import json
import os
from pathlib import Path

import httpx
from bench_canary import exercise

with httpx.Client(
    base_url="http://127.0.0.1:8082",
    trust_env=False,
    timeout=10,
    headers={"Authorization": "Bearer " + os.environ["GK_TOKEN"]},
) as client:
    result = exercise(client)
    client.post("/api/demo/analyze").raise_for_status()
    assert client.get("/").status_code == 200
    assert client.get("/metrics").status_code == 200
    login = client.post("/api/login", json={"password": os.environ["GK_PASSWORD"]})
    login.raise_for_status()
    session = httpx.Client(base_url="http://127.0.0.1:8082", cookies=login.cookies, trust_env=False)
    assert session.get("/api/state").status_code == 200
    assert session.post("/api/demo/analyze").status_code == 403
    assert (
        session.post("/api/logout", headers={"x-csrf-token": login.json()["csrf"]}).status_code
        == 200
    )
    assert session.get("/api/state").status_code == 401
    session.close()
Path("docs/results/compose-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    "Compose: HTTP proxy rollback/promotion/timeout, React, cookie/CSRF/logout and metrics passed."
)
