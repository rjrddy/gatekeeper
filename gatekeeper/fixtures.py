"""Explicitly synthetic scenarios shared by live console and reproducible measurements."""

from __future__ import annotations

import random
from typing import Any


def history(seed: int = 42) -> tuple[list[dict[str, Any]], set[str]]:
    rng = random.Random(seed)
    truth = {f"test_case_{i}" for i in range(24)}
    rows = []
    for i in range(120):
        for revision in range(8):
            sha = f"{revision:040x}"
            for attempt in range(1, 5):
                outcome = (
                    ("fail" if rng.random() < 0.35 else "pass")
                    if i < 24
                    else ("fail" if i < 40 else "pass")
                )
                rows.append(
                    {
                        "repo": "synthetic/demo",
                        "test": f"test_case_{i}",
                        "sha": sha,
                        "environment": "linux-py313",
                        "run_id": f"{i}-{revision}",
                        "attempt": attempt,
                        "outcome": outcome,
                    }
                )
    # Environment-different outcomes must not turn deterministic platform failures into flakes.
    for revision in range(8):
        for environment, outcome in [("linux-py313", "pass"), ("windows-py313", "fail")]:
            rows.append(
                {
                    "repo": "synthetic/demo",
                    "test": "test_platform_specific",
                    "sha": f"{revision:040x}",
                    "environment": environment,
                    "run_id": f"platform-{revision}",
                    "attempt": 1,
                    "outcome": outcome,
                }
            )
    return rows, truth


def failures(seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    families = [
        ("import", "ModuleNotFoundError: No module named missing_dependency"),
        ("timeout", "TimeoutError: worker request exceeded deadline"),
        ("assertion", "AssertionError: expected stable response but observed candidate drift"),
        ("permission", "PermissionError: access denied opening protected fixture"),
        ("connection", "ConnectionError: backend connection refused"),
        ("schema", "ValidationError: missing required resource_changes field"),
        ("memory", "MemoryError: allocation exceeds configured bound"),
        ("syntax", "SyntaxError: invalid syntax near fixture marker"),
        ("signature", "SignatureError: artifact signature does not match trusted key"),
        ("dependency", "DependencyError: incompatible package constraints"),
    ]
    rows = []
    for label, text in families:
        for i in range(8):
            rows.append(
                {
                    "label": label,
                    "log": (
                        f"2026-01-01T00:00:00Z /home/runner/work/demo/test.py "
                        f"line {rng.randrange(10, 500)}\n{text}\n"
                        f"probe duration {rng.randrange(1, 99)}ms"
                    ),
                    "source": "synthetic injected failure",
                }
            )
    rng.shuffle(rows)
    return rows


def plans() -> list[dict[str, Any]]:
    cases = []
    choices = [
        ("aws_db_instance", ["delete"], {}, True),
        ("aws_iam_policy", ["update"], {"policy": "*"}, True),
        ("aws_security_group", ["update"], {"ingress": ["0.0.0.0/0"]}, True),
        ("aws_s3_bucket", ["delete", "create"], {}, True),
        ("aws_instance", ["delete"], {}, True),
        ("aws_iam_role", ["update"], {}, True),
        ("aws_instance", ["create"], {}, False),
        ("aws_db_instance", ["no-op"], {}, False),
        ("aws_security_group", ["update"], {"ingress": ["10.0.0.0/8"]}, False),
        ("aws_instance", ["update"], {"tags": {"team": "synthetic"}}, False),
    ]
    for i, (kind, actions, after, risky) in enumerate(choices):
        address = f"{kind}.fixture_{i}"
        cases.append(
            {
                "label_risky": risky,
                "format_version": "1.2",
                "resource_changes": [
                    {
                        "address": address,
                        "type": kind,
                        "change": {
                            "actions": actions,
                            "after": after,
                            "after_unknown": {"policy": True} if i == 5 else {},
                        },
                    },
                    {
                        "address": f"aws_instance.dependent_{i}",
                        "type": "aws_instance",
                        "change": {"actions": ["no-op"], "after": {}},
                    },
                ],
                "configuration": {
                    "root_module": {
                        "resources": [
                            {
                                "address": f"aws_instance.dependent_{i}",
                                "expressions": {"upstream": {"references": [address + ".id"]}},
                            }
                        ]
                    }
                },
            }
        )
    return cases
