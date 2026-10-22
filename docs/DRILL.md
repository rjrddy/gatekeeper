# Follow-up drill

1. **A delivery ID collides with different bytes.** Reject with conflict before changing an attempt; delivery identity is not silently reassigned.
2. **A terminal failure later claims success.** The attempt is immutable. A rerun needs a distinct attempt identity; contradictory evidence aborts the transaction.
3. **Several threads insert the same delivery.** The primary key and immediate transaction serialize the decision. Inspect the concurrent replay test rather than assuming the GIL provides correctness.
4. **The network acknowledgement is lost after commit.** Retry the same bytes and ID. The second response reports an idempotent replay.
5. **An environment differs only in an unrecorded service version.** The evidence model is incomplete. Quarantine remains a review proposal, not proof of a flaky implementation.
6. **A single flaky commit appears.** It does not meet the current cross-commit proposal policy. That sacrifices recall for reviewable evidence.
7. **A bridge log resembles two groups.** Complete-link membership requires compatibility with every member. This avoids connected-component chaining but can split legitimate families.
8. **Every cluster is a singleton.** Purity can remain perfect while pairwise recall collapses. Both metrics are reported.
9. **The public sample looks perfect.** It is tiny, selected and includes related jobs from one run. Read the source links and do not market it as held-out accuracy.
10. **Terraform includes a child module.** Reject the unsupported scope. A partial graph must not silently become an approval.
11. **A planned IAM value is unknown.** Flag it for review. Unknown is not equivalent to unchanged or harmless.
12. **A plan includes sensitive values.** Persist findings and addresses, not raw planned values. The operator must still treat identifiers as potentially sensitive outside this synthetic demo.
13. **The artifact changes after signing.** The digest binding fails even if the signature bytes remain valid.
14. **Someone supplies their own public key.** The API reads a configured trusted-key path, not a key in an untrusted request. Local CLI trust selection is the operator's responsibility.
15. **A valid signer signs an empty fake scanner result.** Structural checks reject missing structures but cannot prove an honest scanner ran. Trusted builder/scanner provenance remains incomplete.
16. **The vulnerability database ages.** Attestation expiry bounds evidence lifetime, but the verifier does not enforce database freshness independently. Add signed database metadata and policy before claiming freshness guarantees.
17. **The API dies during the candidate probe.** Restart restores stable and advances the epoch. See the actual SIGKILL campaign in results.
18. **A former controller returns after recovery.** Its finish compare-and-swap fails. Tests and the process campaign check the stale write boundary.
19. **The entire host disappears.** The demo is unavailable. A local SQLite volume and startup recovery are not high availability or a backup strategy.
20. **Why publish a recording on Vercel?** It exposes real evidence without pretending that a static host runs a durable controller. Interactive backend hosting is explicitly partial.
