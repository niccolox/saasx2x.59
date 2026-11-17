# Candidate 2 rationale. Slice 1, port 443 uptime check

## Problem

The owner wants each of their sites checked on port 443 every 5 minutes, with each result in Postgres. The check is small. The shape is not, because later slices put hard rules on the data this slice writes. Many accounts must own the rows. Probes in several regions must agree before an alert. The 99.999% accuracy target needs a probe failure to look different from a target failure. Other check types (TCP, DNS, SSL expiry) must fit without a rewrite. The brief also fixes some constraints. The schedule must not drift. A slow target must not delay others. A repeated check must not corrupt data. Tests must run offline against a local self-signed TLS server. The work is greenfield, so there is no existing code to integrate with.

## Usage (caller's view)

The owner's quickstart:

```sh
docker compose up -d db
uv run saasx2x migrate
uv run saasx2x target add example.com
uv run saasx2x target add api.example.com --path /healthz
uv run saasx2x check example.com          # one observation now, printed, not stored
docker compose up -d worker
uv run saasx2x target list                 # host, path, last verdict, last slot
uv run saasx2x target remove example.com   # stops checks, keeps history
```

`saasx2x check` prints the stage times and the verdict:

```
example.com  93.184.216.34  dns 3 ms  tcp 21 ms  tls 44 ms  http 80 ms  status 200  verdict up
```

Call site 1, the worker, for one due check (`scheduler._run_one`):

```python
async with permits:
    observation = await observe(due.spec, env)
await store.record(due.key, due.spec.account_id, due.due_at, observation)
```

Call site 2, the CLI:

```python
host = parse_hostname(args.host)          # "Example.COM" -> "example.com", exit 2 on bad input
spec = await store.add_target("owner", host, parse_path(args.path))
```

Call site 3, a test against a local TLS server:

```python
spec = CheckSpec(check_id=CheckId(1), account_id=AccountId(1), kind=CheckKind.HTTPS,
                 host=parse_hostname("localhost"), port=server.port, path=parse_path("/"),
                 interval_s=300)
observation = await observe(spec, ProbeEnv(resolve=to_loopback, tls=ca.client_context()))
assert judge(observation) == Judgment(verdict=Verdict.BLOCKED,
                                      block_signal=BlockSignal.CF_MITIGATED_CHALLENGE)
```

## Shape

**Core data shape. The stage ladder.** One check climbs four stages in a fixed order on one socket: DNS, TCP, TLS, HTTP. An `Observation` holds the time of each completed stage and then one end. The end is an `Answer` (status and the few headers the rules read) or a `Failure` (the stage that stopped, a reason enum, and a short detail). A validator makes the completed stages a prefix of the ladder. A `Failure` at stage S must have exactly the stages before S. A status code without a TCP connect cannot exist. The same rules are CHECK constraints in `check_result`, so a bad row fails in Postgres too. I tested this against Postgres 16 with three valid rows and seven invalid rows. Later check kinds stop at a lower stage of the same ladder. TCP stops after TCP, SSL expiry after TLS, DNS after DNS. Per model-the-domain and type-system-discipline.

**Facts and judgment are separate.** `probe.observe()` returns facts only. `verdict.judge()` is a pure, total function from an observation to a `Judgment`. Only `Store.record()` calls it when it writes a row. The row stores the facts, the verdict, and `rules_version`. The verdict is derived at one point and never set by hand, so it cannot disagree with its facts. A rule change can recompute old rows from the stored facts. Per boundary-discipline.

**Verdict rules.** There are four verdicts: `up`, `down`, `blocked`, and `probe_error`. For an answer, the first match wins:

| # | Condition | Verdict |
| --- | --- | --- |
| 1 | `cf-mitigated: challenge` with any status | blocked |
| 2 | `server: cloudflare`, status 403, 429 or 503, body has challenge markers | blocked |
| 3 | `server: cloudflare`, status 403, body is the WAF block page | blocked |
| 4 | status 429 | blocked |
| 5 | 200 to 399, or 401 | up |
| 6 | any other status | down |

Redirects are not followed, because a 3xx shows that the server answered. A failure maps through `REASON_VERDICT`, a table that an import-time assert keeps total. `probe_error` needs local evidence: `ENETUNREACH` on every address, local resource exhaustion, or a probe bug. Ambiguous failures (DNS SERVFAIL, timeouts, host unreachable) are `down` for that probe.

**Target source of truth. Postgres, written by the CLI.** `account`, `target` and `target_check` are the only list of targets. The CLI writes them through `Store.add_target` and `Store.remove_target`. The worker reloads them every 60 seconds. There is no config file to sync, and the stage 2 API calls the same two methods. Add is an upsert. Remove sets `removed_at`, so result history stays and a later add brings back the same id. Stage 1 uses one seeded account, `owner`. Composite foreign keys `(id, account_id)` make `check_result.account_id` match the owner of its check, so later row-level security has a column on every row with no sync risk.

**Result key. One row per (check, slot, probe).** The primary key is `(check_id, slot_start, probe_id)`. The insert uses `ON CONFLICT DO NOTHING`, so the first write wins. A rerun after a crash, or a second worker started by mistake, cannot add or change a row. `slot_start` is in the key, so time partitions later need no key change. `probe_id` is in the key, so multi-region rows for one slot sit next to each other. Per make-operations-idempotent.

**Scheduler. Epoch-aligned slots, fixed offsets, minute windows.** Each check's due time is `floor(t / 300) * 300 + offset(check_id)`. The offset is a blake2b hash in `[0, 260 s)`, so a 30-second check always ends inside its slot. Due times come from the epoch, not from the last run, so there is no drift. The offset uses the check id only. All probes observe one target at the same instant, so later agreement compares facts from the same instant. The loop works in 60-second windows. It reloads checks, asks the store which keys this probe already wrote, and starts each missing check at its due time under a semaphore (default 32 in flight). A slow target holds one permit for at most 30 seconds. On restart the first window looks back one interval. It runs a missing check at once if its slot still has 30 seconds left. Each row stores `due_at` and `started_at`, so drift and queue lag show in the data.

**Timeouts.** DNS 5 s, TCP 5 s, TLS 10 s, HTTP headers 15 s, and 30 s for the whole check, body read included. Each stage gets the smaller of its own limit and the time left. The body read stops at 16 KiB.

**Migrations.** I chose plain SQL files applied in name order, one transaction per file, under an advisory lock, with a sha256 per applied file. The design has no ORM models for Alembic to compare against, so Alembic would only wrap SQL in Python. Postgres DDL is transactional, so a failed file leaves nothing behind.

**Interface depth.** The worker calls three functions: `observe`, `record`, and `active_checks`. `observe` hides resolution, address fallback, connect, handshake, HTTP parsing, time limits, the errno table, and Cloudflare page markers. Callers see no socket, header map, body, or SQL row. Per minimize-reader-load, one check is traced in three files from the scheduler.

**What it does not do.** No retries inside a slot, no ICMP, no redirect follows, no alerts, no control targets, no account UI.

## Synthesis decision

To be filled in by arena.

## Tradeoffs accepted

- We accept a hand-written HTTP/1.1 exchange on h11 in exchange for one connection per check with a true time for each stage. httpx would open its own connection after our TCP probe, or hide the stage boundaries.
- We accept that a DNS SERVFAIL or a timeout from a broken probe network writes `down` rows in slice 1, in exchange for no missed outages. The stored reason and `rules_version` let a later slice recompute those rows when control targets exist.
- We accept a lost row when the insert fails, in exchange for a worker that never blocks on the database. A missing row means "not observed", and it never means "up".
- We accept that a late observation from an ended slot is dropped, in exchange for one clear meaning of `slot_start`.
- We accept a hand-synced enum list in Python and in SQL. `test_schema_sync.py` fails the build when they differ, and the CHECK constraints also guard the ladder.
- We accept that 401 counts as up and 404 counts as down. That is a product call with no per-check override in slice 1.
- We accept that `getaddrinfo` runs in a thread and a timed-out lookup keeps its thread until the system resolver returns.

## Alternatives considered

- **A TOML targets file, synced to the database at start.** Git history and declarative edits are useful, but the file and the rows are two copies. Stage 2 adds targets through an API, so the file would become a compatibility path to delete. It also exposes a sync step and conflict rules to the owner.
- **httpx for the HTTPS step, plus a separate TCP connect.** This is less code, but it opens two connections per check. The TCP time comes from a connection that carried no request. The DNS, TLS and HTTP failures arrive as wrapped exceptions that callers must unwrap. That pushes the errno decisions outside the probe.
- **Store observations only, and compute verdicts in a SQL view.** This is one fewer column set, but the rules would then live in SQL and in Python (for the CLI). A later alert also needs the verdict that was true at the time it fired.
- **Sleep 300 after each run, one task per target.** This is simple, but it drifts by the check duration every cycle. The phase between probes in different regions would also be random.

## Open questions and risks

- Is 401 up for the owner's sites, and should a 404 at `/` be down? Should slice 1 allow an expected-status override for each check?
- Should a `down` result get one confirmation retry inside its slot, as Site24x7 does? That needs an `attempt` part in the key or a second table.
- Are the Cloudflare body markers stable? They are strings from Cloudflare pages, and Cloudflare can change them. Rule 1 (`cf-mitigated`) is the stable signal.
- Does the owner run any site that serves IPv6 only? The probe tries the first address of each family, and an IPv6-only target on a probe with no IPv6 route gives `probe_error`.
- What is the retention for `check_result`? At 1 row per check every 5 minutes, one target makes about 105,000 rows a year for each probe.

## Next implementation step

Write `domain.py` validators and `verdict.judge` with `test_verdict.py` table cases first, because every other module trusts those types.
