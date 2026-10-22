import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gatekeeper.analysis import cluster, cluster_metrics, plan_risk, quarantine, timeline
from gatekeeper.fixtures import failures, history, plans


def test_environment_and_commit_isolation() -> None:
    rows, truth = history()
    proposed = quarantine(rows, 100)
    names = {r["test"] for r in proposed}
    assert names == truth
    assert "test_platform_specific" not in names
    assert all(r["expires_at"] > 100 for r in proposed)


def test_duplicate_attempt_cannot_create_flake() -> None:
    rows = [
        {
            "repo": "a/b",
            "test": "x",
            "sha": "a" * 40,
            "environment": "linux",
            "run_id": "1",
            "attempt": 1,
            "outcome": "fail",
        }
    ] * 40
    assert quarantine(rows, 0) == []
    with pytest.raises(ValueError, match="conflicting"):
        quarantine(rows + [{**rows[0], "outcome": "pass"}], 0)


def test_grouping_is_order_independent_and_not_singletons() -> None:
    rows = failures()
    groups = cluster(rows)
    metrics = cluster_metrics([r["label"] for r in rows], groups)
    assert metrics["pairwise_precision"] == metrics["pairwise_recall"] == 1
    assert metrics["clusters"] == 10
    shuffled = list(reversed(rows))
    other = cluster(shuffled)
    assert cluster_metrics([r["label"] for r in shuffled], other) == metrics


def test_purity_does_not_hide_singletons() -> None:
    result = cluster_metrics(["a", "a", "b", "b"], [0, 1, 2, 3])
    assert result["purity"] == 1
    assert result["pairwise_recall"] == 0
    assert result["pairwise_precision"] is None


def test_plan_blast_radius_and_unknowns() -> None:
    cases = plans()
    for case in cases:
        report = plan_risk(case)
        assert report["blocked"] == case["label_risky"]
        if report["blocked"]:
            assert report["findings"][0]["affected_count"] == 2
    cases[5]["resource_changes"][0]["change"]["actions"] = ["no-op"]
    assert "unknown IAM values" in plan_risk(cases[5])["findings"][0]["reasons"]


def test_bad_plan_fails_closed() -> None:
    for value in [
        {},
        {"format_version": "2.0", "resource_changes": []},
        {"format_version": "1.2", "errored": True, "resource_changes": []},
    ]:
        with pytest.raises(ValueError):
            plan_risk(value)


@given(st.permutations(list(range(8))))
@settings(max_examples=30, derandomize=True)
def test_quarantine_permutation_property(order: list[int]) -> None:
    rows, _ = history()
    selected = [r for r in rows if r["test"] == "test_case_0"]
    chunks = [selected[i * 4 : (i + 1) * 4] for i in range(8)]
    shuffled = [r for i in order for r in chunks[i]]
    assert quarantine(shuffled, 100) == quarantine(selected, 100)


def test_timeline_unknowns_and_correlation() -> None:
    events = [
        {"id": "a", "kind": "deploy", "at": 1, "component": "x"},
        {"id": "b", "kind": "alert", "at": 2, "component": "x"},
        {"id": "c", "kind": "deploy", "at": None, "component": "x"},
        {"id": "d", "kind": "deploy", "at": 3, "component": "x"},
    ]
    result = timeline(events)
    assert result["candidate"] == "a"
    assert result["events"][-1]["id"] == "c"


def test_unsupported_plan_never_silently_approved() -> None:
    for row in [
        {"address": "module.a.aws_instance.x", "type": "aws_instance", "change": {}},
        {"address": "google_compute.x", "type": "google_compute_instance", "change": {}},
        None,
    ]:
        with pytest.raises(ValueError):
            plan_risk({"format_version": "1.2", "resource_changes": [row]})


def test_comment_preview_neutralizes_untrusted_names() -> None:
    from gatekeeper.analysis import comment_preview

    preview = comment_preview(
        {
            "scope": "test",
            "findings": [
                {
                    "address": "@all <script> [click](url) `x`",
                    "reasons": ["destructive action"],
                    "affected_count": 1,
                }
            ],
        }
    )
    assert "@all" not in preview and "<script>" not in preview and "[click]" not in preview
