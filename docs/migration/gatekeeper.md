# Migration provenance

Old repositories remain intact. Gatekeeper adapts D2's same-revision mixed-outcome concept with environment isolation, immutable attempt identities and expiring proposals; D1's log normalization with deterministic signatures and nontrivial cluster metrics; D4's Terraform rule fixtures with dependency reachability and conservative unknown-value handling; and D3's timestamp normalization with explicit unknowns and correlation-only labels. P2's reference/candidate HTTP probes become a persisted, epoch-fenced proxy controller rather than an in-memory URL pointer. P3's real Syft/Grype scan workflow supplies scanner evidence; the Rust agent adds digest-bound local-key attestations and explicit trusted-key verification.

No old benchmark number is reused as Gatekeeper evidence. The former D1 public-sample limitation remains open unless a sufficient separately labeled public corpus is actually collected and scored. Production rollback, deployed GitHub App and transparency-log signing are not inferred from local tests.

| Old source | Salvaged boundary | Gatekeeper implementation / rewrite |
| --- | --- | --- |
| D1 `src/triage.py` | Volatile log normalization and grouping | `gatekeeper/analysis.py`: complete-link signatures, stable ordering, pair metrics; frozen manual public labels in `fixtures/public/ci.json` |
| D2 `src/flakes.py` | Same-revision mixed outcomes | `gatekeeper/analysis.py`: environment isolation, immutable attempts, cross-commit evidence and expiring proposals |
| D3 `src/main.py` | Event ordering and closest preceding deploy | `gatekeeper/analysis.py` + authenticated event API: retain unknown timestamps, component correlation, no causal claim |
| D4 `src/main.py` | Destructive/IAM/public-network plan fixtures | `gatekeeper/analysis.py`: reverse configuration references, sensitive unknown review, explicit provider/module rejection, escaped comment preview |
| P2 `src/deploy.py` | Actual reference/candidate HTTP comparison | `gatekeeper/canary.py`, `store.py`, `app.py`: durable proxy route, CAS/epoch fencing, independent processes and SIGKILL recovery |
| P3 `src/main.py`, `scripts/tools.py` | Fresh Syft/Grype inventory and severity evidence; checksum-verified official scanner downloads | `scripts/bench_supply.py`, `scripts/tools.py`: paired controls and tamper cases; `agent/src/`: original Rust Ed25519/digest/time/severity verifier |

Old demos, in-memory route pointers, reused headline numbers and unsupported broad accuracy/production claims are not carried forward. The Rust agent, transactional API and React console are new implementations. Provenance here describes adapted logic and concepts rather than asserting that untouched old modules were copied verbatim.
