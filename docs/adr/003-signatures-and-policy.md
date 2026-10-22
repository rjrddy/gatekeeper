# Integrity and approval are separate checks

Context: a signed report can still contain blocking vulnerabilities. A scanner failure must not look like an empty finding list.

Options: trust a scanner exit code, sign only the artifact, or bind all evidence and reapply policy.

Decision: Rust verifies a locally trusted Ed25519 signature over commit, artifact, SBOM and scanner digests, policy identity and validity interval. It then validates report structure and enforces severity policy. Syft's file components may lack package versions; package components require identities. File-only SBOMs fail closed.

Tradeoffs: the operator holding the signing key is trusted to run honest scanners. The verifier does not prove that arbitrary bytes were built by an approved builder or that every dependency was discovered. This is not SLSA, keyless signing, revocation, transparency logging or reproducible builds. Benchmark artifacts contain package metadata only; vulnerable code is not installed. Saved attestations expire; rerun the benchmark for live checks. Scanner databases change, so counts can change on rerun.
