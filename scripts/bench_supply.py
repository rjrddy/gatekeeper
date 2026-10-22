"""Fresh Syft/Grype evidence over package metadata; no vulnerable code is installed."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / "docs/results/supply"


def run(cmd: list[str], expected: int = 0, env=None) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    if p.returncode != expected:
        raise RuntimeError(f"{cmd[0]} exit {p.returncode}, expected {expected}: {p.stderr[-2500:]}")
    return p


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cache = ROOT / ".cache/supply"
    cache.mkdir(parents=True, exist_ok=True)
    binary = str(ROOT / "bin/gatekeeper-agent")
    syft = str(ROOT / ".cache/bin/syft") if (ROOT / ".cache/bin/syft").exists() else "syft"
    grype = str(ROOT / ".cache/bin/grype") if (ROOT / ".cache/bin/grype").exists() else "grype"
    private, public = cache / "signing.key", cache / "trusted.pub"
    if not private.exists():
        run([binary, "keygen", "--private", str(private), "--public", str(public)])
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    outcomes = {}
    for name, version, expected in [
        ("bad", "1.26.4", 1),
        ("control", importlib.metadata.version("urllib3"), 0),
    ]:
        directory = cache / name
        directory.mkdir(exist_ok=True)
        metadata = directory / f"urllib3-{version}.dist-info"
        metadata.mkdir(exist_ok=True)
        (metadata / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: urllib3\nVersion: {version}\n"
            "Summary: Metadata fixture only; code not installed\n"
        )
        out = OUT if name == "bad" else OUT / "control"
        out.mkdir(exist_ok=True)
        # Archive bytes and scan the same extracted metadata; not an SBOM of this application.
        artifact = out / "artifact.bin"
        with tarfile.open(artifact, "w") as tar:
            tar.add(metadata, arcname=metadata.name)
        env = {
            **os.environ,
            "SYFT_CHECK_FOR_APP_UPDATE": "false",
            "GRYPE_CHECK_FOR_APP_UPDATE": "false",
        }
        started = time.perf_counter()
        bom = run([syft, str(directory), "-o", "cyclonedx-json"], env=env)
        (out / "sbom.json").write_text(bom.stdout)
        report = run([grype, "sbom:" + str(out / "sbom.json"), "-o", "json"], env=env)
        (out / "scan.json").write_text(report.stdout)
        (out / "scan.stderr.log").write_text(report.stderr)
        (out / "commit.txt").write_text(commit + "\n")
        shutil.copyfile(public, out / "trusted.pub")
        shared = [
            "--artifact",
            str(artifact),
            "--sbom",
            str(out / "sbom.json"),
            "--scan",
            str(out / "scan.json"),
            "--commit",
            commit,
        ]
        run(
            [
                binary,
                "attest",
                *shared,
                "--key",
                str(private),
                "--ttl",
                "86400",
                "--output",
                str(out / "attestation.json"),
            ]
        )
        verify = [
            binary,
            "verify",
            *shared,
            "--attestation",
            str(out / "attestation.json"),
            "--public-key",
            str(out / "trusted.pub"),
        ]
        verdict = run(verify, expected)
        result = json.loads(verdict.stdout)
        (out / "verdict.json").write_text(verdict.stdout)
        original = artifact.read_bytes()
        artifact.write_bytes(original + b"tamper")
        try:
            tampered = run(verify, 2)
            (out / "tamper-rejected.json").write_text(tampered.stderr)
        finally:
            artifact.write_bytes(original)
        outcomes[name] = {
            "version": version,
            "exit_code": expected,
            "tamper_exit_code": 2,
            "verdict": result,
            "elapsed_seconds": time.perf_counter() - started,
            "sbom_sha256": hashlib.sha256(bom.stdout.encode()).hexdigest(),
        }
    outcome = {
        "scope": "Fresh package-metadata fixture scan; no vulnerable library code installed. "
        "Not a scan of the entire application or a reproducible-build claim.",
        "syft_version": run([syft, "version", "-o", "json"]).stdout,
        "grype_version": run([grype, "version", "-o", "json"]).stdout,
        "commit": commit,
        "fixtures": outcomes,
    }
    (OUT.parent / "supply.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
