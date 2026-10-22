"""GitHub App request authentication and narrowly scoped installation tokens."""

import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Any

import httpx
import jwt


def valid_webhook(raw: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return len(secret) >= 24 and hmac.compare_digest(expected, signature)


def workflow(payload: dict[str, Any]) -> dict[str, Any]:
    run = payload["workflow_run"]
    repo = payload["repository"]["full_name"]
    import re

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid repository")
    sha = run["head_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("invalid commit")
    status = run["status"]
    if status not in {"queued", "in_progress", "completed"}:
        raise ValueError("invalid workflow status")
    conclusion = run.get("conclusion")
    allowed = {
        "success",
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "neutral",
        "skipped",
        "stale",
        "startup_failure",
    }
    if status == "completed" and conclusion not in allowed:
        raise ValueError("completed outcome required")
    attempt = int(run.get("run_attempt", 1))
    if not 1 <= attempt <= 10000 or not 0 < int(run["id"]) < 10**20:
        raise ValueError("invalid run identity")
    return {
        "repo": repo,
        "id": str(run["id"]),
        "attempt": attempt,
        "sha": sha,
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
    }


async def installation_token(installation_id: int) -> str:
    if installation_id < 1:
        raise ValueError("invalid installation")
    key = Path(os.environ["GK_APP_PRIVATE_KEY_FILE"]).read_text()
    now = int(time.time())
    encoded = jwt.encode(
        {"iat": now - 30, "exp": now + 540, "iss": os.environ["GK_APP_ID"]}, key, algorithm="RS256"
    )
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": "Bearer " + encoded,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"permissions": {"actions": "read", "contents": "read"}},
        )
        response.raise_for_status()
        return str(response.json()["token"])
