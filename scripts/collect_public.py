"""Read-only public Actions excerpts; source URLs and selection boundaries are retained."""

import json
import re
import subprocess
from pathlib import Path

repo = "pytest-dev/pytest"
runs = json.loads(
    subprocess.check_output(
        ["gh", "api", f"repos/{repo}/actions/runs?status=failure&per_page=12"], text=True
    )
)["workflow_runs"]
rows = []
for run in runs:
    if run["name"] != "test":
        continue
    proc = subprocess.run(
        ["gh", "run", "view", str(run["id"]), "--repo", repo, "--log-failed"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode or not proc.stdout.strip():
        continue
    # Keep failure lines and nearby context; never copy arbitrary full job archives.
    lines = proc.stdout.splitlines()
    matches = [
        i
        for i, line in enumerate(lines)
        if re.search(
            r"AssertionError|ModuleNotFoundError|ImportError|TimeoutError|"
            r"ERROR |FAILED |##\[error\]",
            line,
        )
    ]
    selected = sorted({j for i in matches for j in range(max(0, i - 2), min(len(lines), i + 4))})
    excerpt = "\n".join(lines[j] for j in selected)[-16000:]
    excerpt = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email redacted]", excerpt)
    excerpt = re.sub(
        r"(?i)(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)", "[token redacted]", excerpt
    )
    if excerpt:
        rows.append(
            {
                "repo": repo,
                "run_id": run["id"],
                "sha": run["head_sha"],
                "source_url": run["html_url"],
                "log": excerpt,
                "label": "UNREVIEWED",
                "selection": "failure-marker context, truncated tail; automated redaction",
            }
        )
    if len(rows) >= 4:
        break
Path("docs/results/public-unlabeled.json").write_text(json.dumps(rows, indent=2) + "\n")
print("Collected public run excerpts:", len(rows))
