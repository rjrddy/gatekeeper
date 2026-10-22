# Public evidence and private operation

Context: the user requested Vercel hosting. SQLite and an in-process probe controller require persistent state and process lifetime, which a static evidence page does not provide.

Options: advertise an ephemeral API, migrate the backend to a hosted durable service, or publish transparent measured evidence while keeping the full service local.

Decision: ship an authenticated local Compose stack and a Vercel evidence page with real measurements and a console recording. The live hosted backend remains incomplete. No additional provider account or paid resource is provisioned. A separate Render deployment template requests a persistent disk and is not a claim of a free persistent tier.

Tradeoffs: reviewers can inspect the public recording immediately; interactive release operations require running the repo. Random operator credentials are generated into an ignored owner-only file. Sessions store token hashes with expiry and CSRF proof; a separate machine token enables automation. The webhook uses exact-body HMAC and immutable delivery IDs. Provision TLS and Secure cookies for any remote runtime. Credentials are deliberately not published. GitHub App installation and any PR posting need explicit operator setup; no external repository comments are sent.
