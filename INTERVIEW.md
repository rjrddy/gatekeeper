# Gatekeeper interview guide

## Two-minute pitch

Gatekeeper asks whether release evidence deserves a decision. I built a Rust verifier, a Python service and an authenticated React console around three failure boundaries: repeated CI events, stale rollout controllers, and signed but unsafe dependency reports.

The event store deduplicates exact deliveries, keeps completed attempts immutable, and refuses contradictory evidence. Quarantine proposals require comparable mixed outcomes. The canary is a real HTTP proxy: a mismatch or timeout changes the route back to its last approved upstream. Killing the API during a probe exercises startup recovery and fences the former epoch. The Rust verifier binds the artifact, SBOM, scan and commit, then applies vulnerability policy even if the signature is valid.

The recorded injection benchmark found all 24 seeded flakes across 3,856 observations without a false proposal. It caught all six risky fixtures among ten plans. A fresh scanner report for old urllib3 metadata contained 11 advisories, including eight High findings that blocked approval; the current-version control passed. These are local, bounded measurements, not production adoption or general accuracy claims. Sources: [analysis](docs/results/analysis.json), [canary](docs/results/canary.json), [supply](docs/results/supply.json).

## Ten-minute architecture walkthrough

Start at a workflow delivery. GitHub signs the exact bytes; the endpoint checks HMAC before parsing. A transaction inserts the delivery digest and updates an attempt only in a forward direction. Reusing an identity with different bytes or changing a terminal outcome is a conflict.

Then show analysis. Workflow metadata does not contain individual test outcomes, so synthetic attempt histories feed the quarantine detector separately. A proposal includes the environment, comparable commits and expiration. Signature normalization removes volatile paths and timings. Complete-link grouping resists bridge logs, and pairwise recall reveals over-splitting. Public excerpts retain URLs and manual visible-signature labels; selected examples are not held-out evaluation.

Open the plan review. Rules flag destructive actions, sensitive unknown values, changed IAM and public ingress. Reverse configuration references identify dependent instances. The output is an explanation and a Markdown preview, never an automatic apply or unsolicited comment.

Trace a bad candidate. The start transaction checks the expected epoch, changes the actual proxy route and records the event. Sequential HTTP comparisons evaluate the candidate against the stored stable service. The finishing transaction checks the epoch again. A failed comparison restores stable; a passing comparison promotes. On restart, an interrupted rollout is restored before the API begins serving. Requests already in flight remain a stated boundary.

Finally open the Rust gate. Ed25519 authenticates exact claim bytes against a configured public key. Time bounds, policy version, commit and evidence digests must match. Structural validation prevents a broken scanner output from masquerading as an empty result. Severity policy is reapplied independently of the signature. Package metadata fixtures demonstrate actual scanner behavior without installing vulnerable executable code.

End in the React console and request logs. The state comes from committed database rows, the proxy output comes from real HTTP requests, and the evidence verdict comes from the compiled CLI. Random session tokens are stored as hashes, writes require CSRF, and logout revokes the session. The public Vercel site is recorded evidence; persistent interactive hosting and GitHub App installation remain partial.

## Five tradeoffs

- SQLite gives local transactional reasoning and restart tests; it does not give high availability. A replicated database alone would not establish controller ownership.
- Expiring quarantine proposals preserve human review and scheduled execution; they do not automatically speed up another repository's CI.
- Complete-link signatures are deterministic and inspectable; their bounded quadratic work is unsuitable for unbounded log history.
- Locally trusted keys make integrity testable without a signing service; key provenance, revocation and builder attestation remain operator responsibilities.
- Explainable root-module plan rules are defensible; unsupported modules are rejected rather than silently marked safe.

## Five failure modes

- Duplicate or reordered webhooks: exact-body digest deduplication, monotonic states and immutable terminal outcomes. Concurrent replay tests exercise the transaction.
- Competing rollout writers: start uses an expected epoch; finish requires the same current epoch and probing state. A stale controller cannot undo recovery.
- Candidate mismatch or timeout: fail the bounded HTTP comparison and commit the actual route change; the benchmark requests the proxy again afterward.
- API crash while probing: restart restores the last stable route and advances the epoch. A whole-host outage still means unavailability.
- Signed unsafe, stale or mutated evidence: digest, time and trusted-key checks run before approval; severity policy blocks validly signed unsafe evidence. The initial Syft shape error is retained in [the integration failure](docs/results/initial-syft-shape-failure.log).

## Fifteen likely questions

1. **Is this exactly-once delivery?** No. Transport can deliver repeatedly; the database makes one delivery ID idempotent and preserves attempt identity. Different deliveries can refer to the same completed attempt.
2. **Can a pending event overwrite completion?** No. State ranks prevent regression and conflicting completed outcomes abort the entire transaction, including the delivery insert.
3. **Why not infer flakes from workflow status?** A failed workflow is not a failed test. The detector requires test-level comparable attempts; live JUnit artifact ingestion is unfinished.
4. **Does quarantine prove nondeterministic code?** No. It establishes mixed observed outcomes under recorded identity fields. Missing environmental factors and external state can still explain them.
5. **Could cluster purity be misleading?** Yes. Singletons give perfect purity. Pairwise recall and false-pair counts expose that failure; a test explicitly demonstrates it.
6. **How were public labels obtained?** By reviewing visible assertions and a DNS resolver failure in source-linked excerpts. Several assertions come from one public run, so independence and generalization are limited.
7. **Why not use embeddings?** A small signature corpus benefits from an inspectable baseline. I would first collect an independently reviewed corpus before adding model complexity.
8. **What does blast radius mean?** Reverse reachability through configuration references, not outage probability. Unsupported providers and nested modules are outside the accepted scope.
9. **Does signing make an artifact safe?** No. Signing authenticates bindings. Policy still rejects a vulnerability finding, and a trusted signer could lie about scanner provenance.
10. **What did the dependency experiment scan?** An archive's extracted package metadata, using actual Syft and Grype. It did not install the vulnerable version or scan the whole application image. Separate dependency audits run in CI.
11. **What happens if a candidate controller finishes late?** Its epoch/state check fails. It cannot promote or roll back a newer decision.
12. **Is rollback instantaneous?** New proxy requests use the committed route. A request already using the old upstream can complete there. Fleet convergence and a latency SLO are not measured.
13. **Why only one API worker?** Startup recovery is local ownership. Multiple API replicas could mistake another replica's probe for abandoned work. A distributed lease is a separate design change.
14. **What is hosted?** Public measured evidence and the real console recording. The persisted interactive API is local Compose. The manifest and token helper do not imply an installed GitHub App.
15. **What would you change first?** Collect held-out public JUnit histories, then add durable distributed controller ownership and audited signing provenance. Keep measured boundaries visible during each step.

## With three more months

Install the App in an explicitly authorized test repository, ingest versioned test artifacts, measure on held-out public histories, and add a review/expiry workflow for quarantine. Extend plan parsing with provider-aware module resolution and differential fixtures. Move route control behind renewable ownership with a persistent hosted database, measure load and fault convergence, and add short-lived signing identity with an append-only audit service. Do not treat the current local results as proof those additions already work.
