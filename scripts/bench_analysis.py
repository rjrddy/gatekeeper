"""Measured accuracy on frozen labels; public evidence is evaluated separately."""

import json
import time
from pathlib import Path

from gatekeeper.analysis import cluster, cluster_metrics, plan_risk, quarantine, timeline
from gatekeeper.fixtures import failures, history, plans

started = time.perf_counter()
rows, truth = history()
proposals = quarantine(rows, 0)
found = {p["test"] for p in proposals}
logs = failures()
fixtures = plans()
results = [plan_risk(p) for p in fixtures]
expected = [p["label_risky"] for p in fixtures]
public = json.loads(Path("fixtures/public/ci.json").read_text())
public_groups = cluster(public)
out = {
    "seed": 42,
    "flakes": {
        "observations": len(rows),
        "truth": len(truth),
        "proposals": len(found),
        "precision": len(found & truth) / len(found) if found else None,
        "recall": len(found & truth) / len(truth),
        "false_positives": sorted(found - truth),
        "missed": sorted(truth - found),
    },
    "synthetic_clusters": cluster_metrics([r["label"] for r in logs], cluster(logs)),
    "public_clusters": cluster_metrics([r["label"] for r in public], public_groups),
    "public_sources": [
        {"run_id": r["run_id"], "url": r["source_url"], "label": r["label"], "cluster": g}
        for r, g in zip(public, public_groups)
    ],
    "plans": {
        "samples": len(fixtures),
        "risky": sum(expected),
        "caught": sum(r["blocked"] and e for r, e in zip(results, expected)),
        "false_positives": sum(r["blocked"] and not e for r, e in zip(results, expected)),
        "findings": results,
    },
    "timeline": timeline(
        [
            {"id": "deploy", "kind": "deploy", "component": "demo", "at": 10},
            {"id": "alert", "kind": "alert", "component": "demo", "at": 12},
            {"id": "log-unknown", "kind": "log", "component": "demo", "at": None},
        ]
    ),
    "elapsed_seconds": time.perf_counter() - started,
    "scope": "Seeded injection accuracy is not public CI accuracy. Public sample selected by hand.",
}
assert not out["flakes"]["false_positives"] and not out["flakes"]["missed"]
assert out["plans"]["caught"] == sum(expected) and not out["plans"]["false_positives"]
Path("docs/results/analysis.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: v for k, v in out.items() if k not in ("plans", "timeline")}, indent=2))
