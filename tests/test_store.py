from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from gatekeeper.store import Conflict, Store


def run(status: str = "completed") -> dict:
    return {
        "repo": "synthetic/demo",
        "id": "1",
        "attempt": 1,
        "sha": "a" * 40,
        "status": status,
        "conclusion": "failure" if status == "completed" else None,
    }


def test_replayed_delivery_and_terminal_order(tmp_path: Path) -> None:
    store = Store(tmp_path / "g.db")
    assert store.ingest("x", b"raw", run())
    assert not store.ingest("x", b"raw", run())
    with pytest.raises(Conflict):
        store.ingest("x", b"changed", run())
    store.ingest("old", b"old", run("queued"))
    assert store.snapshot()["runs"][0]["status"] == "completed"
    with pytest.raises(Conflict):
        store.ingest("changed", b"changed", {**run(), "conclusion": "success"})
    assert store.ingest("changed", b"valid", run())


def test_concurrent_replay_commits_once(tmp_path: Path) -> None:
    store = Store(tmp_path / "g.db")
    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(lambda _: store.ingest("same", b"same", run()), range(32)))
    assert sum(accepted) == 1
    assert len(store.snapshot()["audit"]) == 1


def test_only_one_controller_can_claim_epoch(tmp_path: Path) -> None:
    store = Store(tmp_path / "g.db")

    def start(_: int) -> bool:
        try:
            store.start("candidate-bad", 0)
            return True
        except Conflict:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(start, range(20))) == 1


def test_stale_controller_cannot_undo_rollback(tmp_path: Path) -> None:
    store = Store(tmp_path / "g.db")
    old = store.start("candidate-bad", 0)
    assert store.recover()
    state = store.snapshot()["rollout"]
    assert state["active"] == "stable"
    assert not store.finish(old, True, {"passed": True})
    newer = store.start("candidate-good", state["epoch"])
    assert store.finish(newer, True, {"passed": True})
    assert not store.finish(old, False, {})
    assert store.snapshot()["rollout"]["active"] == "candidate-good"


def test_restart_retains_committed_evidence(tmp_path: Path) -> None:
    path = tmp_path / "g.db"
    store = Store(path)
    store.ingest("x", b"one", run())
    store.report("plan", {"blocked": True})
    second = Store(path)
    assert second.snapshot()["runs"] == store.snapshot()["runs"]
    assert second.snapshot()["reports"][0]["body"]["blocked"]


def test_nonterminal_observations_do_not_regress(tmp_path: Path) -> None:
    store = Store(tmp_path / "g.db")
    store.ingest("newer", b"in progress", run("in_progress"))
    store.ingest("late", b"queued", run("queued"))
    assert store.snapshot()["runs"][0]["status"] == "in_progress"
