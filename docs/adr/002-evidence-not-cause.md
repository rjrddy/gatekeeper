# Quarantine requires comparable observations

Context: retries, platforms and commits produce misleading aggregate failure rates. Duplicate deliveries must not inflate evidence.

Options: global failure percentage, arbitrary flaky labels, or comparable mixed outcomes.

Decision: deduplicate immutable attempts; require mixed outcomes at the same commit, environment and test across distinct commits. Emit expiring review proposals and keep scheduled runs. Workflow-level GitHub events do not contain test-level outcomes; the quarantine benchmark uses explicit synthetic attempt histories, never inferred public flake labels.

Tradeoffs: conservative coverage, no automatic repository mutation, and no causal diagnosis. A deterministic test with uncontrolled external inputs may appear variable. The seeded injection benchmark is controlled; the small public signature sample is selected and is not a held-out flake evaluation. Signature clustering reports pair metrics alongside purity to expose fragmentation.
