"""Single-host SQLite transactions, immutable deliveries and rollout fencing."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(
                  hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS deliveries(
                  id TEXT PRIMARY KEY, digest TEXT NOT NULL, received REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(
                  repo TEXT NOT NULL, id TEXT NOT NULL, attempt INTEGER NOT NULL,
                  sha TEXT NOT NULL, status TEXT NOT NULL, conclusion TEXT, updated REAL NOT NULL,
                  PRIMARY KEY(repo,id,attempt));
                CREATE TABLE IF NOT EXISTS reports(
                  id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                  body TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(
                  id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                  body TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS rollout(
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1), epoch INTEGER NOT NULL,
                  state TEXT NOT NULL, active TEXT NOT NULL, stable TEXT NOT NULL,
                  candidate TEXT, last_result TEXT);
                INSERT OR IGNORE INTO rollout VALUES(1,0,'stable','stable','stable',NULL,NULL);
            """)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def ingest(self, delivery: str, raw: bytes, run: dict[str, Any]) -> bool:
        digest = hashlib.sha256(raw).hexdigest()
        with self.transaction() as c:
            found = c.execute("SELECT digest FROM deliveries WHERE id=?", (delivery,)).fetchone()
            if found:
                if found["digest"] != digest:
                    raise Conflict("delivery ID reused with different bytes")
                return False
            existing = c.execute(
                "SELECT * FROM runs WHERE repo=? AND id=? AND attempt=?",
                (run["repo"], run["id"], run["attempt"]),
            ).fetchone()
            if existing and existing["sha"] != run["sha"]:
                raise Conflict("workflow identity changed commit")
            c.execute("INSERT INTO deliveries VALUES(?,?,?)", (delivery, digest, time.time()))
            ranks = {"queued": 0, "in_progress": 1, "completed": 2}
            if not existing or (
                existing["status"] != "completed"
                and ranks[run["status"]] >= ranks[existing["status"]]
            ):
                c.execute(
                    """INSERT INTO runs VALUES(?,?,?,?,?,?,?) ON CONFLICT(repo,id,attempt)
                             DO UPDATE SET status=excluded.status,conclusion=excluded.conclusion,
                             updated=excluded.updated""",
                    (
                        run["repo"],
                        run["id"],
                        run["attempt"],
                        run["sha"],
                        run["status"],
                        run.get("conclusion"),
                        time.time(),
                    ),
                )
            elif run["status"] == "completed" and run.get("conclusion") != existing["conclusion"]:
                raise Conflict("completed attempt is immutable")
            c.execute(
                "INSERT INTO audit(kind,body,created) VALUES(?,?,?)",
                (
                    "workflow_delivery",
                    json.dumps(
                        {
                            "repo": run["repo"],
                            "run": run["id"],
                            "attempt": run["attempt"],
                            "delivery": delivery,
                        }
                    ),
                    time.time(),
                ),
            )
            return True

    def report(self, kind: str, body: dict[str, Any]) -> int:
        with self.transaction() as c:
            cur = c.execute(
                "INSERT INTO reports(kind,body,created) VALUES(?,?,?)",
                (kind, json.dumps(body, sort_keys=True), time.time()),
            )
            return int(cur.lastrowid)

    def snapshot(self) -> dict[str, Any]:
        with self.transaction() as c:
            return {
                "runs": [
                    dict(r) for r in c.execute("SELECT * FROM runs ORDER BY updated DESC LIMIT 100")
                ],
                "reports": [
                    {
                        "id": r["id"],
                        "kind": r["kind"],
                        "body": json.loads(r["body"]),
                        "created": r["created"],
                    }
                    for r in c.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 30")
                ],
                "audit": [
                    dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 80")
                ],
                "rollout": dict(c.execute("SELECT * FROM rollout").fetchone()),
            }

    def start(self, candidate: str, expected_epoch: int) -> int:
        if candidate not in {"candidate-good", "candidate-bad", "candidate-slow"}:
            raise ValueError("unrecognized synthetic candidate")
        with self.transaction() as c:
            row = c.execute("SELECT * FROM rollout").fetchone()
            if row["epoch"] != expected_epoch or row["state"] == "probing":
                raise Conflict("rollout epoch changed or controller active")
            epoch = expected_epoch + 1
            c.execute(
                "UPDATE rollout SET epoch=?,state='probing',candidate=?,active=?,last_result=NULL",
                (epoch, candidate, candidate),
            )
            c.execute(
                "INSERT INTO audit(kind,body,created) VALUES(?,?,?)",
                (
                    "canary_started",
                    json.dumps({"epoch": epoch, "candidate": candidate}),
                    time.time(),
                ),
            )
            return epoch

    def finish(self, epoch: int, passed: bool, result: dict[str, Any]) -> bool:
        with self.transaction() as c:
            row = c.execute("SELECT * FROM rollout").fetchone()
            if row["epoch"] != epoch or row["state"] != "probing":
                return False
            active = row["candidate"] if passed else row["stable"]
            stable = active if passed else row["stable"]
            c.execute(
                "UPDATE rollout SET state=?,active=?,stable=?,last_result=?",
                ("promoted" if passed else "rolled_back", active, stable, json.dumps(result)),
            )
            c.execute(
                "INSERT INTO audit(kind,body,created) VALUES(?,?,?)",
                (
                    "canary_promoted" if passed else "canary_rolled_back",
                    json.dumps({"epoch": epoch, "result": result}),
                    time.time(),
                ),
            )
            return True

    def recover(self) -> bool:
        """An interrupted local controller fails closed and fences its old generation."""
        with self.transaction() as c:
            row = c.execute("SELECT * FROM rollout").fetchone()
            if row["state"] != "probing":
                return False
            c.execute("UPDATE rollout SET epoch=epoch+1,state='recovered',active=stable")
            c.execute(
                "INSERT INTO audit(kind,body,created) VALUES(?,?,?)",
                ("controller_recovered", json.dumps({"old_epoch": row["epoch"]}), time.time()),
            )
            return True

    def session(self, digest: str) -> dict[str, Any] | None:
        with self.transaction() as c:
            row = c.execute(
                "SELECT csrf,expires FROM sessions WHERE hash=? AND expires>?",
                (digest, time.time()),
            ).fetchone()
            return dict(row) if row else None

    def login(self, digest: str, csrf: str) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
            if c.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 100:
                raise Conflict("session capacity")
            c.execute("INSERT INTO sessions VALUES(?,?,?)", (digest, csrf, time.time() + 3600))

    def logout(self, digest: str) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM sessions WHERE hash=?", (digest,))
