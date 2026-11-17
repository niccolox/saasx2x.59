# Design brief: SaaSX2X slice 1 (port 443 uptime check)

## User goal

The user is building SaaSX2X, an uptime monitor like Site24x7 or Uptime.com. Read `/home/niccolox/Projects/saasx2x.59/PRODUCT.md` for the full product. This task is the first thin slice only.

Slice 1: every 5 minutes, check that each of the owner's sites is up on port 443, and write each result to a database. The owner is the only user. No UI, no accounts UI, no alerts, no billing.

## What one check does

For each target (a hostname such as `example.com`):

1. Open a TCP connection to port 443. Record the connect time or the failure.
2. If TCP connects, make an HTTPS request to the target. Record the status code, the response time, or the failure (DNS, TLS, timeout, connection reset, and so on).
3. Decide a verdict for the check and write one result row.

"Ping" in the user's words means "check that the site is up". It does not mean ICMP. Do not use ICMP in this slice.

## Fixed constraints

- Python 3.13 with `uv`. Pydantic v2 for the domain model. This is the house pattern in the user's other projects.
- Postgres 16 in Docker Compose. Bind the host port to `127.0.0.1:55440`. Ports 55432 and 55480 are already in use.
- Schema migrations: pick one way and justify it (Alembic, or plain SQL files applied in order).
- Interval 300 seconds. The schedule must not drift (fixed-rate, not "sleep 300 after each run"). A slow target must not delay checks of other targets.
- Every HTTP request sends one fixed User-Agent that names SaaSX2X, for example `SaaSX2X-Monitor/0.1 (+https://saasx2x.example/bot)`. This is how targets behind Cloudflare can allowlist the probe. Do not copy browser fingerprints.
- If Cloudflare returns a challenge (for example 403 with `cf-mitigated: challenge`, or a `server: cloudflare` 403 or 503 challenge page), the verdict is "blocked", not "down".
- Tests must run offline with no credentials: a local TLS server with a self-signed certificate is the target in tests.
- The worker must survive a crash and restart. Running the same check twice must not corrupt data.

## Product rules that the design must not block later

These come in later slices. Do not build them now. The slice-1 shape must not need a rewrite to add them.

- Many accounts. Every target belongs to one account.
- Probes in several regions. An alert needs agreement from more than one region. So each result must record which probe made it.
- More check types later: DNS, SSL expiry, TCP on other ports, heartbeat, Web Vitals.
- A 99.999% alert accuracy target. A failure of the probe's own network must be distinguishable from a failure of the target.

## Open design questions for you to decide

- How the owner adds and removes targets in slice 1 (CLI, config file, SQL seed, or something else). One source of truth only.
- The verdict type and the exact rules that map a raw observation to a verdict. Which HTTP status codes count as up?
- The result table schema and its keys. How a row stays unique when a check runs twice.
- The scheduler shape and how concurrency is bounded.
- Timeouts for TCP and HTTPS.
- The module layout. Keep the call chain short.

## Output

Write your design package to the output path the orchestrator gives you. Use the architect runner prompt and the rationale template. Include the type sketch (Python, with `raise NotImplementedError` bodies), the SQL schema, the module map, and the rationale. Do not write the implementation.
