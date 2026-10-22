"""Deterministic CI evidence analysis; heuristics never claim causal proof."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any


def quarantine(history: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], dict[tuple[str, int], str]] = defaultdict(dict)
    seen: dict[tuple[str, str, str, str, str, int], str] = {}
    for row in history:
        repo, test, sha, env = (str(row[k]) for k in ("repo", "test", "sha", "environment"))
        if not env or row["outcome"] not in ("pass", "fail"):
            continue
        identity = (repo, test, sha, env, str(row["run_id"]), int(row["attempt"]))
        if identity in seen and seen[identity] != row["outcome"]:
            raise ValueError("immutable attempt has conflicting outcomes")
        seen[identity] = row["outcome"]
        groups[(repo, test, sha, env)][(str(row["run_id"]), int(row["attempt"]))] = row["outcome"]
    evidence: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (repo, test, sha, env), attempts in sorted(groups.items()):
        counts = Counter(attempts.values())
        if counts["pass"] and counts["fail"]:
            evidence[(repo, test, env)].append(
                {"sha": sha, "passes": counts["pass"], "failures": counts["fail"]}
            )
    proposals = []
    for (repo, test, env), mixed in sorted(evidence.items()):
        if len(mixed) >= 2:
            proposals.append(
                {
                    "repo": repo,
                    "test": test,
                    "environment": env,
                    "mixed_commits": len(mixed),
                    "evidence": mixed,
                    "expires_at": now + 7 * 86400,
                    "action": "propose quarantine; keep scheduled runs",
                    "reason": "same commit/environment mixed outcomes; not causal proof",
                }
            )
    return proposals


def normalized(text: str) -> str:
    if len(text) > 200_000:
        raise ValueError("log exceeds analysis bound")
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"^\d{4}-\d\d-\d\dT\S+\s*", "", text, flags=re.M)
    text = re.sub(r"https?://\S+", "URL", text)
    text = re.sub(r"(?:/home/runner/|/Users/|/tmp/)[^\s:]+", "PATH", text)
    text = re.sub(r"\b[0-9a-f]{12,64}\b", "HASH", text)
    text = re.sub(r"\bline \d+\b", "line N", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:ms|s| seconds)\b", "TIME", text)
    return text.lower().strip()


def cluster(records: list[dict[str, Any]], threshold: float = 0.64) -> list[int]:
    if len(records) > 256:
        raise ValueError("clustering bound exceeded")
    texts = [normalized(r["log"]) for r in records]
    tokens = [set(re.findall(r"[a-z_][a-z0-9_]*|==|!=|\b[0-9]{3}\b", t)) for t in texts]
    anchors = [
        next(iter(re.findall(r"\b\w*(?:error|exception)\b|\bpanic\b", t)), "") for t in texts
    ]

    def similarity(a: int, b: int) -> float:
        if anchors[a] != anchors[b]:
            return 0.0
        union = tokens[a] | tokens[b]
        return len(tokens[a] & tokens[b]) / len(union) if union else float(texts[a] == texts[b])

    groups: list[list[int]] = []
    # Complete-link membership prevents a bridge log joining unrelated clusters.
    for i in sorted(range(len(texts)), key=lambda i: (texts[i], i)):
        eligible = [(min(similarity(i, j) for j in g), k) for k, g in enumerate(groups)]
        candidates = [(s, -k) for s, k in eligible if s >= threshold]
        if candidates:
            groups[-max(candidates)[1]].append(i)
        else:
            groups.append([i])
    result = [0] * len(records)
    for g, members in enumerate(groups):
        for i in members:
            result[i] = g
    return result


def cluster_metrics(labels: list[str], groups: list[int]) -> dict[str, Any]:
    if not labels or len(labels) != len(groups):
        raise ValueError("nonempty matching labels required")
    purity = sum(
        max(Counter(labels[i] for i, g in enumerate(groups) if g == group).values())
        for group in set(groups)
    ) / len(labels)
    tp = fp = fn = 0
    for i in range(len(labels)):
        for j in range(i):
            same = groups[i] == groups[j]
            true = labels[i] == labels[j]
            tp += same and true
            fp += same and not true
            fn += true and not same
    return {
        "samples": len(labels),
        "clusters": len(set(groups)),
        "purity": purity,
        "pairwise_precision": tp / (tp + fp) if tp + fp else None,
        "pairwise_recall": tp / (tp + fn) if tp + fn else None,
        "true_pairs": tp,
        "false_pairs": fp,
        "missed_pairs": fn,
    }


def plan_risk(plan: dict[str, Any]) -> dict[str, Any]:
    if not str(plan.get("format_version", "")).startswith("1.") or plan.get("errored"):
        raise ValueError("supported, non-error Terraform JSON plan required")
    changes = plan.get("resource_changes")
    if not isinstance(changes, list) or len(changes) > 1000:
        raise ValueError("bounded resource_changes required")
    for row in changes:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("address"), str)
            or not row["address"]
            or row["address"].startswith("module.")
            or not isinstance(row.get("type"), str)
            or not row["type"].startswith("aws_")
            or not isinstance(row.get("change"), dict)
        ):
            raise ValueError("AWS root-module resource identities required")
    addresses = {r["address"] for r in changes}
    if len(addresses) != len(changes):
        raise ValueError("duplicate resource identity")
    if plan.get("configuration", {}).get("root_module", {}).get("module_calls"):
        raise ValueError("nested modules are outside the reviewed scope")
    dependents: dict[str, set[str]] = defaultdict(set)

    def refs(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [str(x) for x in value.get("references", [])] + [
                x for k, v in value.items() if k != "references" for x in refs(v)
            ]
        if isinstance(value, list):
            return [x for v in value for x in refs(v)]
        return []

    resources = plan.get("configuration", {}).get("root_module", {}).get("resources", [])
    for resource in resources:
        target = resource.get("address")
        if target not in addresses:
            continue
        for ref in refs(resource.get("expressions", {})):
            for address in addresses:
                base = re.sub(r"\[[^]]+\]", "", address)
                if ref == base or ref.startswith(base + "."):
                    dependents[address].add(target)

    def unknown(v: Any) -> bool:
        return (
            v is True
            or (isinstance(v, dict) and any(unknown(x) for x in v.values()))
            or (isinstance(v, list) and any(unknown(x) for x in v))
        )

    findings = []
    for resource in changes:
        address = resource["address"]
        kind = resource["type"]
        change = resource["change"]
        actions = change["actions"]
        if (
            not isinstance(actions, list)
            or not actions
            or any(a not in {"no-op", "create", "read", "update", "delete"} for a in actions)
        ):
            raise ValueError("invalid change actions")
        reasons = []
        if "delete" in actions:
            reasons.append("destructive action or replacement")
        if kind.startswith("aws_iam") and actions != ["no-op"]:
            reasons.append("IAM change requires review")
        if kind.startswith("aws_iam") and unknown(change.get("after_unknown")):
            reasons.append("unknown IAM values")
        after = json_text(change.get("after", {}))
        if kind in {"aws_security_group", "aws_vpc_security_group_ingress_rule"} and (
            "0.0.0.0/0" in after or "::/0" in after
        ):
            reasons.append("public network ingress")
        if unknown(change.get("after_unknown")) and kind.startswith("aws_security"):
            reasons.append("unknown network permissions")
        if reasons:
            reachable = {address}
            queue = [address]
            while queue:
                for child in dependents[queue.pop()]:
                    if child not in reachable:
                        reachable.add(child)
                        queue.append(child)
            findings.append(
                {
                    "address": address,
                    "type": kind,
                    "reasons": reasons,
                    "affected": sorted(reachable),
                    "affected_count": len(reachable),
                }
            )
    return {
        "blocked": bool(findings),
        "findings": findings,
        "scope": "AWS root-module heuristic; not Terraform apply or causal impact proof",
    }


def json_text(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True)


def comment_preview(result: dict[str, Any]) -> str:
    """Render untrusted resource names without Markdown links, mentions or HTML."""
    import html

    lines = ["Gatekeeper plan review", "", result["scope"], ""]
    for row in result["findings"]:
        address = html.escape(row["address"]).replace("@", "&#64;")
        address = address.replace("`", "&#96;").replace("[", "&#91;")
        lines.append(f"- {address}: {'; '.join(row['reasons'])}.")
        lines.append(f"  Dependency reach: {row['affected_count']} resource instances.")
    if not result["findings"]:
        lines.append("No configured heuristic triggered; this is not approval to apply.")
    return "\n".join(lines)


def timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(events, key=lambda e: (e.get("at") is None, e.get("at") or 0, e["id"]))
    alerts = [e for e in ordered if e["kind"] == "alert" and e.get("at") is not None]
    candidates = []
    if alerts:
        first = alerts[0]
        candidates = [
            e
            for e in ordered
            if e["kind"] == "deploy"
            and e.get("component") == first.get("component")
            and e.get("at") is not None
            and e["at"] <= first["at"]
        ]
    return {
        "events": ordered,
        "candidate": candidates[-1]["id"] if candidates else None,
        "interpretation": "temporal correlation only; unknown timestamps retained",
    }
