# Explain infrastructure findings

Context: a single risk score hides the rule and can imply unsupported probability estimates. Terraform may carry secrets in planned values.

Options: numeric risk ranking, apply-and-observe, or static rule explanations plus dependency reach.

Decision: inspect supported AWS root-module JSON plans, return explicit reasons and reverse reference reachability, and persist findings rather than raw plan values. Reject unsupported provider or module identities. Render PR comment previews without posting externally.

Tradeoffs: no nested-module resolution, provider schema analysis, dynamic expression execution, policy organization hierarchy, or Terraform apply. Dependency reach is an upper-bound graph hint, not a causal outage prediction. Tag-only changes and private ingress controls exercise false positives, but this small fixture corpus does not establish general coverage.
