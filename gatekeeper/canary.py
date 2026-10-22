"""Real bounded HTTP behavior checks; the proxy reads the durable route separately."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

from gatekeeper.store import Store


def upstreams() -> dict[str, str]:
    return {
        key: os.getenv("GK_" + key.upper().replace("-", "_") + "_URL", default)
        for key, default in [
            ("stable", "http://127.0.0.1:18301"),
            ("candidate-good", "http://127.0.0.1:18302"),
            ("candidate-bad", "http://127.0.0.1:18303"),
            ("candidate-slow", "http://127.0.0.1:18304"),
        ]
    }


async def probe(store: Store, epoch: int, candidate: str) -> dict[str, Any]:
    addresses = upstreams()
    baseline = store.snapshot()["rollout"]["stable"]
    rows = []
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=0.25, trust_env=False) as client:
            for x in range(12):
                row: dict[str, Any] = {"input": x, "matches": False}
                try:
                    stable = await client.get(addresses[baseline] + "/value", params={"x": x})
                    current = await client.get(addresses[candidate] + "/value", params={"x": x})
                    stable.raise_for_status()
                    current.raise_for_status()
                    row["stable"] = stable.json()
                    row["candidate"] = current.json()
                    row["matches"] = row["stable"] == row["candidate"]
                except (httpx.HTTPError, ValueError):
                    row["error"] = "candidate/reference unavailable or invalid"
                rows.append(row)
                if not row["matches"]:
                    break
        result = {
            "rows": rows,
            "passed": len(rows) == 12 and all(r["matches"] for r in rows),
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "candidate": candidate,
        }
        result["applied"] = store.finish(epoch, result["passed"], result)
        return result
    except asyncio.CancelledError:
        store.finish(epoch, False, {"passed": False, "reason": "controller cancelled"})
        raise
    except Exception:
        # A malformed response or local fault must never leave a candidate promoted.
        store.finish(epoch, False, {"passed": False, "reason": "controller exception"})
        raise
