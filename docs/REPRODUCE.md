# Reproduce the local evidence

Prerequisites: Python, Node/npm, pinned Rust toolchain via rustup, GitHub CLI authenticated for the pinned public scanner downloads, and Docker Compose for the full container check. No new provider account is required for the native runtime. The GitHub App is optional and unconfigured.

```sh
make setup build
.venv/bin/python scripts/tools.py
make lint test bench
```

The scanners download their current vulnerability database. The metadata control version comes from the installed benchmark environment. Rerun output can legitimately differ from the committed report as that database and dependency environment change. `make bench` writes fresh raw outputs under `docs/results/`, including new attestations with bounded validity; private keys remain in ignored `.cache/supply/` with owner-only permissions. Do not distribute those private keys.

The negative fixture's archive and extracted metadata both identify an old urllib3 dependency. Syft inventories the metadata, Grype scans the resulting SBOM, and the Rust agent signs and checks the exact artifact/SBOM/scan bytes and commit. No vulnerable code is installed, and this is not the whole app's dependency inventory. The separate `make scan` target audits installed Python packages, Node packages and the Rust lockfile; install cargo-audit via `cargo install cargo-audit --locked` first.

For native browser review:

```sh
.venv/bin/python scripts/configure.py
.venv/bin/python scripts/dev.py
```

From another terminal run `.venv/bin/python scripts/seed.py`, then visit http://127.0.0.1:8082. Open `.env` locally for the operator password. The seed script writes only to this local API, computes actual analyses and replays public workflow metadata with a local demo signature. It does not install an App or write to GitHub.

Install Playwright Chromium and its recording support with `.venv/bin/playwright install chromium`. Run `.venv/bin/python scripts/browser_check.py` while the preview is running. The script saves an actual console recording and desktop/mobile screenshots. Inspect the video with `ffprobe -v error -show_format -show_streams -of json docs/results/demo.webm > docs/results/demo-probe.json`. The public evidence site's browser check is `scripts/site_check.py` and requires an anonymous reachable URL; it never uses a deployment bypass token.

Stop the native preview before running `make bench`; both deliberately use the same fixed loopback synthetic upstream ports. Interrupting `scripts/dev.py` terminates its child services. A database file and benchmark result files are retained; no original repository is touched.

CI runs real native HTTP recovery and scanner checks, then makes a separate clone and runs the README's Compose stack and seed. Container runtime dependencies are exported and scanned from the CI runner so the audit tooling never needs executable code in hardened `/tmp`. See uploaded `gatekeeper-ci-evidence` for Compose responses and logs.

The App manifest is in `deploy/github-app-manifest.json`. Before installing, set your own callback/webhook host, App identity and private-key file, and configure the receiver's secret. The helper requests read-only workflow permissions. PR comment output is a preview; no posting endpoint or automatic comments are enabled.
