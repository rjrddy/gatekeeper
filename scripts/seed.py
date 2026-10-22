"""Seed actual analysis and replay public metadata only into your local demo instance."""

import hashlib
import hmac
import json
import os
from pathlib import Path

import httpx

for line in Path(".env").read_text().splitlines():
    key, value = line.split("=", 1)
    os.environ[key] = value
with httpx.Client(
    base_url="http://127.0.0.1:8082",
    trust_env=False,
    timeout=15,
    headers={"Authorization": "Bearer " + os.environ["GK_TOKEN"]},
) as client:
    for endpoint in ["demo/analyze", "public/analyze", "evidence/verify"]:
        response = client.post("/api/" + endpoint)
        if response.status_code != 503:
            response.raise_for_status()
    for row in json.loads(Path("docs/results/public-unlabeled.json").read_text()):
        raw = json.dumps(
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
        signature = hmac.new(
            os.environ["GK_WEBHOOK_SECRET"].encode(), raw, hashlib.sha256
        ).hexdigest()
        client.post(
            "/api/github/webhook",
            content=raw,
            headers={
                "x-github-event": "workflow_run",
                "x-github-delivery": str(row["run_id"]),
                "x-hub-signature-256": "sha256=" + signature,
            },
        ).raise_for_status()
print("Local synthetic analysis and signed public-metadata replay seeded. No GitHub writes.")
