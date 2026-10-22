# Gatekeeper design

The hard problem is turning incomplete, repeated, out-of-order CI observations into a reproducible release decision without confusing correlation with causation. Release approval is tied to a specific commit, artifact digest, SBOM, vulnerability report and policy version. It must not change when a webhook is replayed or an old canary controller finishes late.

The Rust agent verifies a locally trusted Ed25519 key, signed digest bindings, attestation time bounds, structural SBOM/scan validity and severity policy. Signature validity alone never approves an artifact. Missing inputs and scanner errors fail closed. This is local-key artifact integrity, not a transparency-log or SLSA provenance guarantee.

The Python service persists immutable events in SQLite WAL transactions. A delivery ID is unique; replay of identical bytes is idempotent, while reuse with changed bytes is a conflict. Completed workflow attempts are keyed by repository, run ID and attempt; pending or older observations cannot overwrite completion. Quarantine requires mixed pass/fail observations at the same commit, test and environment, with distinct attempts. It is a proposal with expiry; deterministic failures remain release-blocking.

Failure signatures normalize volatile paths and timings while preserving exception classes and assertion structure. Evaluation reports both purity and pairwise precision/recall, so singleton clusters cannot masquerade as useful clustering. Synthetic injection labels are evaluated separately from manually labeled public CI excerpts. Small public samples do not establish a complete failure taxonomy.

Terraform findings include the directly changed resources and reverse dependency reachability in the plan configuration graph. Unknown IAM/security-sensitive values require review. Findings expose reasons and affected addresses rather than treating a heuristic score as failure probability. Plans are inspected, never applied.

A durable canary state machine uses revision compare-and-swap plus fencing epochs. A real HTTP proxy reads the active upstream from storage for each request. Only a controller holding the current epoch may promote or roll back. Sequential probes compare a candidate with the stable reference using synthetic inputs. A mismatch or candidate timeout changes the actual proxy route back to stable and records evidence. Requests already in flight may finish on the old route. This is a single-host demonstration, not a distributed rollout platform.

GitHub webhooks validate HMAC over the exact request body. App installation-token plumbing and a manifest are supplied; installation must be configured before claiming a live App. Public Actions collection is read-only. PR comments are rendered as reviewable Markdown and require explicit posting opt-in; no third-party repository is modified automatically.

The console reads actual stored events, findings, quarantine proposals, signature checks and proxy state. Authentication uses random HttpOnly sessions stored as hashes plus CSRF for state-changing operations and a provisioned machine token. Logs exclude credentials and raw payloads. SQLite is a single-host volume, not a stateless Vercel database. Public hosting must state whether it is recorded evidence or an actual persisted service.
