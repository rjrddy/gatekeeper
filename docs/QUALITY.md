# Gatekeeper checkpoint

Status: **partial**. The local hard core, full stack and recorded measurements work. Do not describe the GitHub App as installed or the Vercel page as a hosted persistent release controller.

| Required check | Evidence | Status |
| --- | --- | --- |
| Hard core written and explained | Rust verifier, transactional event store, real HTTP proxy, [design](DESIGN.md), [ADRs](adr/) | pass for stated single-host scope |
| Fresh-clone one-command runtime | Actual Linux Compose smoke, independent service containers, auth and proxy assertions in CI | final revision verification pending |
| UI shows live behavior | [browser assertions](results/browser.json), [recording](results/demo.webm), [recording probe](results/demo-probe.json) | pass locally |
| Unit, integration and property/chaos tests | [full check output](results/final-checks.log), [actual process recovery](results/canary.json) | pass |
| Measured benchmark evidence saved | [analysis](results/analysis.json), [canary](results/canary.json), [supply](results/supply.json) | pass |
| A demonstrated caught failure | [signed vulnerability block](results/supply/verdict.json), [tamper rejection](results/supply/tamper-rejected.json) | pass |
| ADRs | [durability](adr/001-local-durability.md), [comparable evidence](adr/002-evidence-not-cause.md), [signing](adr/003-signatures-and-policy.md), [plan scope](adr/004-plan-review-boundaries.md), [hosting/auth](adr/005-hosting-and-auth.md) | pass |
| Interview and drill | [INTERVIEW](../INTERVIEW.md), [DRILL](DRILL.md) | pass |
| CI green | Local checks pass; initial CI passed core/scans/process chaos and Compose behavior, then failed loading the audit tool on noexec tmpfs; audit moved to runner | final revision verification pending |
| No unmeasured claims | Generated README links saved measurements and separates synthetic/public scopes | pass for documented scope |
| Live persistent deployment | Public Vercel evidence page; full runtime remains local Compose | partial |
| Real GitHub App and PR workflow | Manifest, installation-token helper, exact-body webhook authentication, signed local replay of public workflow metadata, comment previews | partial: not installed; no live JUnit ingestion or comment posting |

## What the evidence does and does not establish

The injected flake corpus is deterministic, with explicit attempt and environment identities. The public signature corpus is manually selected from source-linked pytest jobs; several related excerpts share a run. Neither establishes general public-repository flake detection accuracy. Rule fixtures measure configured cases, not full Terraform language coverage.

The supply benchmark freshly scans extracted package metadata corresponding to a tar artifact, signs its report bindings and applies a real Rust policy. No vulnerable code is installed. It is not the app image's SBOM, trusted builder provenance, revocation or independent scanner freshness enforcement. Python, Node, Rust and installed container dependencies are audited separately in CI.

The HTTP campaign uses real independently running local services, including process SIGKILL and restart against the same database file. It proves the checked small campaign, not high availability, fleet-scale convergence or a load SLO. A read-only root filesystem, dropped capabilities and non-executable temporary mount remain in the Compose runtime. Credentials are random and private; sessions are hashed, revocable and CSRF protected.

## Recorded engineering failures

- Initial verifier rejected Syft file components without versions: [raw failure](results/initial-syft-shape-failure.log). Package identity validation now excludes file components and rejects file-only evidence. The real scanner benchmark passes afterward.
- Browser polling exhausted a shared write rate budget: [raw failure](results/initial-browser-rate-failure.log). Read/write budgets are separate; a regression test exercises polling before a write, and the completed recording passes.
- The container audit tool could not load a native library from hardened noexec tmpfs: [raw CI log](results/initial-compose-ci-failure.log). CI now exports exact installed package versions and audits them on the runner. Runtime mount hardening is retained.

## Demo and rerun

Run the README's local Compose commands. In the console: test a bad candidate, probe the real routed value, inspect signed vulnerability rejection, analyze seeded CI signals and public excerpts, inspect infrastructure findings, promote a matching candidate, inject a timeout, and reload the persisted state.

For a fresh native recording, first complete setup/build/bench, generate `.env`, run `scripts/dev.py` with the repository virtual environment, seed using `scripts/seed.py`, then run `scripts/browser_check.py` with Playwright Chromium installed. `ffprobe` creates the recording metadata. The script records actual page activity and asserts the rollout epoch, resulting route, findings and responsive layout; it does not render simulated progress. Do not run native benchmarks concurrently with the native preview: they intentionally use the same fixed synthetic upstream ports.

No original repository was archived, moved, tagged or deleted. The existing portfolio was left unchanged. Stop for review before Tally.
