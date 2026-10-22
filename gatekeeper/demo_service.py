"""Synthetic upstreams: these are actual network processes, never external deployments."""

import asyncio
import os

from fastapi import FastAPI

app = FastAPI()


@app.get("/value")
async def value(x: int = 0) -> dict[str, int]:
    if abs(x) > 100000:
        return {"value": 0}
    mode = os.getenv("GK_SERVICE_MODE", "good")
    if mode == "slow":
        await asyncio.sleep(1)
    return {"value": x * 2 + (1 if mode == "bad" else 0)}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
