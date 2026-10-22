"""Authenticated live CI analysis, signed webhook ingestion, and real proxy routing."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import subprocess
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gatekeeper.analysis import cluster, comment_preview, plan_risk, quarantine, timeline
from gatekeeper.canary import probe, upstreams
from gatekeeper.fixtures import failures, history, plans
from gatekeeper.github import valid_webhook, workflow
from gatekeeper.store import Conflict, Store

log = logging.getLogger("gatekeeper")


class Start(BaseModel):
    candidate: str = Field(pattern=r"^candidate-(good|bad|slow)$")
    expected_epoch: int = Field(ge=0)


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class Event(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    kind: str = Field(pattern=r"^(deploy|alert|log)$")
    component: str = Field(min_length=1, max_length=100)
    at: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    summary: str = Field(min_length=1, max_length=500)


class BodyLimit:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        size = 0

        async def bounded() -> dict:
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > 1_000_000:
                raise HTTPException(413, "body limit exceeded")
            return message

        await self.app(scope, bounded, send)


def create_app(path: str | None = None) -> FastAPI:
    password = os.getenv("GK_PASSWORD", "")
    token = os.getenv("GK_TOKEN", "")
    webhook = os.getenv("GK_WEBHOOK_SECRET", "")
    if len(password) < 16 or len(token) < 24 or len(webhook) < 24:
        raise RuntimeError("configure GK_PASSWORD, GK_TOKEN and GK_WEBHOOK_SECRET")
    store = Store(path or os.getenv("GK_DATABASE", "data/gatekeeper.db"))
    tasks: set[asyncio.Task] = set()
    budgets: dict[str, list[float]] = defaultdict(list)
    budget_lock = threading.Lock()
    counters: dict[str, int] = defaultdict(int)
    secure = os.getenv("GK_COOKIE_SECURE") == "1"

    def rate(key: str, limit: int) -> None:
        with budget_lock:
            now = time.monotonic()
            for old in list(budgets):
                if not budgets[old] or budgets[old][-1] < now - 60:
                    del budgets[old]
            if key not in budgets and len(budgets) >= 1000:
                raise HTTPException(429, "rate capacity")
            budgets[key] = [t for t in budgets[key] if t > now - 60]
            if len(budgets[key]) >= limit:
                raise HTTPException(429, "rate limited")
            budgets[key].append(now)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        store.recover()
        yield
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Gatekeeper", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def headers(request: Request, call_next: Any) -> Response:
        trace = secrets.token_hex(16)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        counters["requests"] += 1
        if response.status_code >= 500:
            counters["errors"] += 1
        route = request.scope.get("route")
        log.info(
            json.dumps(
                {
                    "event": "http_completed",
                    "trace_id": trace,
                    "route": getattr(route, "path", "unmatched"),
                    "status": response.status_code,
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                }
            )
        )
        return response

    async def auth(request: Request) -> dict[str, Any]:
        bearer = request.headers.get("authorization", "")
        if bearer:
            if not hmac.compare_digest(
                hashlib.sha256(bearer.encode()).digest(),
                hashlib.sha256(("Bearer " + token).encode()).digest(),
            ):
                raise HTTPException(401, "invalid machine token")
            session = {"machine": True}
        else:
            cookie = request.cookies.get("gk_session", "")
            session = store.session(hashlib.sha256(cookie.encode()).hexdigest()) if cookie else None
            if not session:
                raise HTTPException(401, "sign in required")
            if request.method not in ("GET", "HEAD") and not hmac.compare_digest(
                request.headers.get("x-csrf-token", ""), session["csrf"]
            ):
                raise HTTPException(403, "CSRF proof required")
        rate("authenticated", 600 if request.method == "GET" else 60)
        return session

    @app.exception_handler(Conflict)
    async def conflict(_request: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.get("/health")
    def health() -> dict[str, str]:
        store.snapshot()
        return {"status": "ok"}

    @app.post("/api/login")
    def login(body: Login, response: Response) -> dict[str, str]:
        rate("login", 10)
        if not hmac.compare_digest(
            hashlib.sha256(body.password.encode()).digest(),
            hashlib.sha256(password.encode()).digest(),
        ):
            raise HTTPException(401, "invalid credentials")
        value = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        store.login(hashlib.sha256(value.encode()).hexdigest(), csrf)
        response.set_cookie(
            "gk_session",
            value,
            httponly=True,
            secure=secure,
            samesite="strict",
            max_age=3600,
            path="/",
        )
        return {"csrf": csrf}

    @app.get("/api/session")
    def session(session: dict = Depends(auth)) -> dict[str, Any]:
        return session

    @app.post("/api/logout", dependencies=[Depends(auth)])
    def logout(request: Request, response: Response) -> dict[str, bool]:
        value = request.cookies.get("gk_session", "")
        store.logout(hashlib.sha256(value.encode()).hexdigest())
        response.delete_cookie("gk_session", path="/")
        return {"ok": True}

    @app.get("/api/state", dependencies=[Depends(auth)])
    def state() -> dict[str, Any]:
        return store.snapshot()

    @app.get("/metrics", dependencies=[Depends(auth)], response_class=PlainTextResponse)
    async def metrics() -> str:
        return "\n".join(f"gatekeeper_{k}_total {v}" for k, v in sorted(counters.items())) + "\n"

    @app.post("/api/github/webhook")
    async def ingest(request: Request) -> dict[str, bool]:
        rate("webhook", 120)
        raw = await request.body()
        if not valid_webhook(raw, request.headers.get("x-hub-signature-256", ""), webhook):
            raise HTTPException(401, "invalid webhook signature")
        delivery = request.headers.get("x-github-delivery", "")
        if not delivery or len(delivery) > 100:
            raise HTTPException(422, "delivery identity required")
        if request.headers.get("x-github-event") != "workflow_run":
            return {"accepted": False}
        try:
            run = workflow(json.loads(raw))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, "invalid workflow event") from None
        accepted = store.ingest(delivery, raw, run)
        counters["webhooks"] += accepted
        return {"accepted": accepted}

    @app.post("/api/demo/analyze", dependencies=[Depends(auth)])
    def analyze() -> dict[str, Any]:
        observations, _ = history()
        logs = failures()
        groups = cluster(logs)
        proposals = quarantine(observations, time.time())
        risks = [plan_risk(p) for p in plans()]
        for risk in risks:
            risk["comment_preview"] = comment_preview(risk)
        clustered = [
            {"group": group, "label": row["label"], "log": row["log"]}
            for row, group in zip(logs, groups)
        ]
        result = {
            "quarantine": proposals,
            "clusters": clustered,
            "plans": risks,
            "scope": "seeded synthetic analysis, not public accuracy evidence",
        }
        store.report("analysis", result)
        return result

    @app.post("/api/plans", dependencies=[Depends(auth)])
    async def plan(request: Request) -> dict[str, Any]:
        try:
            result = plan_risk(await request.json())
        except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
            raise HTTPException(422, "invalid supported plan") from None
        result["comment_preview"] = comment_preview(result)
        store.report("plan", result)
        return result

    @app.post("/api/canary", dependencies=[Depends(auth)])
    async def canary(body: Start) -> dict[str, int]:
        epoch = store.start(body.candidate, body.expected_epoch)
        task = asyncio.create_task(probe(store, epoch, body.candidate))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        counters["canaries"] += 1
        return {"epoch": epoch}

    @app.post("/api/evidence/verify", dependencies=[Depends(auth)])
    def evidence() -> dict[str, Any]:
        directory = Path(os.getenv("GK_EVIDENCE", "docs/results/supply"))
        required = [
            "artifact.bin",
            "sbom.json",
            "scan.json",
            "attestation.json",
            "trusted.pub",
            "commit.txt",
        ]
        if not all((directory / p).exists() for p in required):
            raise HTTPException(503, "run the real supply-chain benchmark first")
        binary = os.getenv("GK_AGENT", "bin/gatekeeper-agent")
        cmd = [
            binary,
            "verify",
            "--artifact",
            str(directory / "artifact.bin"),
            "--sbom",
            str(directory / "sbom.json"),
            "--scan",
            str(directory / "scan.json"),
            "--attestation",
            str(directory / "attestation.json"),
            "--public-key",
            str(directory / "trusted.pub"),
            "--commit",
            (directory / "commit.txt").read_text().strip(),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            result = json.loads(proc.stdout or proc.stderr)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise HTTPException(503, "verification tool failed") from None
        result["exit_code"] = proc.returncode
        store.report("supply", result)
        return result

    @app.get("/demo/value", dependencies=[Depends(auth)])
    async def proxy(x: int = 0) -> JSONResponse:
        if abs(x) > 100000:
            raise HTTPException(422, "probe input bound")
        active = store.snapshot()["rollout"]["active"]
        try:
            async with httpx.AsyncClient(timeout=0.4, trust_env=False) as client:
                response = await client.get(upstreams()[active] + "/value", params={"x": x})
                response.raise_for_status()
                return JSONResponse(response.json(), headers={"X-Gatekeeper-Upstream": active})
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "active upstream unavailable") from None

    @app.get("/api/timeline", dependencies=[Depends(auth)])
    def events() -> dict[str, Any]:
        rows = store.snapshot()["audit"]
        recorded = [r["body"] for r in store.snapshot()["reports"] if r["kind"] == "incident"]
        return timeline(
            recorded
            + [
                {
                    "id": str(r["id"]),
                    "kind": "deploy" if "canary" in r["kind"] else "event",
                    "component": "synthetic-api",
                    "at": r["created"],
                    "summary": r["kind"],
                }
                for r in rows
            ]
        )

    @app.post("/api/events", dependencies=[Depends(auth)])
    def incident(body: Event) -> dict[str, int]:
        return {"id": store.report("incident", body.model_dump())}

    web = Path(os.getenv("GK_WEB", "apps/web/dist"))
    if web.exists():
        if (web / "assets").exists():
            app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(web / "index.html")

    return app
