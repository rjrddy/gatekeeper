# Durable state on one host

Context: workflow attempts and route decisions must survive an API process restart. A second coordinator finishing late must not reverse a later decision.

Options: memory only, SQLite transactions, or a replicated Postgres service.

Decision: use SQLite WAL with full synchronous commits, a separate connection per transaction, immutable attempt identities and a compare-and-swap rollout epoch. The real proxy reads the route for each new request. API startup rolls an interrupted probe back and advances the epoch.

Tradeoffs: simple deployment and inspectable transactions; writes serialize. Exactly one API worker owns probe lifecycle. Multiple API replicas would run conflicting startup recovery. In-flight upstream requests can finish on the former route. Disk/device durability beyond SQLite's synchronization contract and host loss are not tested. A stuck host cannot recover until a controller restarts. Distributed rollout requires external ownership and a renewable lease, not merely more workers.
