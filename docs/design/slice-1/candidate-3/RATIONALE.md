# Rationale, candidate 3

## Problem

The owner needs a worker that checks each site on port 443 every 5 minutes and writes one row for each check to Postgres 16. The system is greenfield, so Phase A had no code to trace. The constraints come from `PRODUCT.md` and the brief.

- Every target belongs to one account. Stage 1 uses the stage 2 account model with one account.
- An alert later needs agreement from more than one region, so each row names its probe.
- A probe network failure must differ from a target failure. The accuracy target is 1 wrong verdict in 100,000.
- A Cloudflare challenge is "blocked", never "down".
- The worker must survive a crash. A repeated check must not corrupt data. A slow target must not delay other targets.
- More check types come later (DNS, SSL expiry, other TCP ports, heartbeat, Web Vitals).

The hard part is not the HTTP call. The hard part is the shape of a result row. That row is the unit that alerts, regions, and new check types will all build on.

## Usage (caller's view)

The owner manages targets with the CLI and reads results in psql.

```
$ saasx2x migrate
$ saasx2x target add example.com
$ saasx2x target add api.example.com --interval 300
$ saasx2x target remove old.example.com
$ saasx2x worker                      # runs until SIGTERM
```

```sql
select t.host, r.slot_start, r.verdict, r.reason,
       r.observation->'tcp'->>'connect_ms'  as tcp_ms,
       r.observation->'http'->>'status'     as status
from check_result r
join target_check c on c.id = r.check_id
join target t on t.id = c.target_id
order by r.slot_start desc, t.host limit 20;
```

Code in the later alert slice reads the same table. It does not call the worker.

```python
# later slice: agreement across probes, one query, no new write path
rows = await db.fetch("""
    select slot_start, array_agg(verdict) from check_result
    where check_id = $1 and slot_start >= $2 group by slot_start""", check_id, since)
```

Test code builds the worker from parts.

```python
worker = Worker(store, NetworkProber(settings), probe_id, settings, FakeClock(t0))
assert await worker.tick() == 2        # two targets due in this slot
assert await worker.tick() == 0        # same slot again, nothing due
```

## Shape

**Core data shape.** There are two layers and one key.

1. `Observation` holds raw facts from one attempt. It is a tagged union of three states: `ConnectFailed`, `NoResponse`, `Responded`. HTTP data exists only after TCP connected. The probe's own network test (`vantage`) exists only on a failure. The wrong combinations do not build, per type-system-discipline.
2. `CheckResult` holds the observation, the probe, the slot, and two timestamps. The verdict and the reason are computed from the observation. No caller passes a verdict in, per model-the-domain.
3. The key is `(check_id, probe_id, slot_start)`. A slot is a cell of a wall-clock grid in UTC, anchored at the epoch. Every probe computes the same slot for the same instant.

The stored row has typed columns for the facts that alert code queries: `verdict`, `reason`, `slot_start`, `rules_version`. The raw observation is one `jsonb` column that holds the `Observation` model. A later check kind adds its own observation union. It needs no new column and no new table. The cost is that psql queries use `->` paths.

**Verdict rules.** `verdict.judge(observation) -> Reason` is one pure function. Each `Reason` member owns its `Verdict`, so no pair can disagree. First match wins.

| Order | Condition | Reason | Verdict |
| --- | --- | --- | --- |
| 1 | `cf-mitigated: challenge`, or `server: cloudflare` with status 403 or 503 and a challenge marker in the first 2 KiB of the body | cloudflare_challenge | blocked |
| 2 | HTTP status 200 to 399 | ok | up |
| 3 | HTTP status 400 to 499 | status_4xx | down |
| 4 | HTTP status 500 to 599 | status_5xx | down |
| 5 | No response, and every vantage anchor failed | probe_network_down | probe_fault |
| 6 | No response, otherwise | dns_failure, tcp_refused, tcp_timeout, tcp_unreachable, tls_failure, http_timeout, connection_reset, http_protocol_error | down |

Notes on the rules.

- The probe does not follow redirects. A 3xx means the server answers. Slice 1 accepts this.
- A Cloudflare 403 or 503 without a challenge marker is "down". An origin outage looks the same, and a missed outage is a wrong verdict.
- A certificate error is "down" with reason `tls_failure`. The probe verifies certificates.
- The vantage test runs only when no HTTP response arrived. It connects to two named hosts (`one.one.one.one:443`, `dns.google:443`) at the same time. Names are used on purpose, so a broken resolver also fails the test. Both must fail to give "probe_fault".
- `body_head` is stored only for status 400 and above. Rule changes can then replay old rows. `RULES_VERSION` is stored on each row.

**Target source of truth.** The `target` table is the only list. The CLI writes it. The worker reads it on every tick. There is no config file, so there is nothing to sync, and results hold a real foreign key to a target in an account. A removed target gets `removed_at`. Its results stay. `target add` creates the target and its `https_443` check in one transaction. The `account` table has one seeded row, and the CLI uses it when it is the only one.

**Scheduler shape.** One asyncio process, one `Worker`. The loop wakes on a 60 second grid. The wake time comes from the wall clock, not from the end of the last tick, so there is no drift. On each wake, `Store.due()` returns the checks that have no row for this probe in their current slot. The worker starts one task for each. A semaphore (default 50) bounds concurrency. The tick does not wait for its tasks.

This gives these properties.

- The absence of a row is the only "pending" state. There is no job table, no lock, and no claim.
- A crash and a restart need no recovery code. The worker restarts, finds the open slot, and runs only the missing checks.
- A failed write leaves no row, so the next tick runs the check again in the same slot.
- A new target runs within 60 seconds. It does not wait for the next 5 minute boundary.
- A slow target holds one semaphore slot. A task whose slot has ended is dropped and counted, so queues cannot pile up.
- A gap in `slot_start` values for a probe shows that the probe was down. The grid makes the gaps visible.

**Idempotency.** `Store.write` is `INSERT ... ON CONFLICT (check_id, probe_id, slot_start) DO NOTHING`. Running a check twice gives one row. The first writer wins. This follows make-operations-idempotent.

**Timeouts.** TCP connect 5 s. HTTPS 10 s for connect, handshake, and the body head. One hard deadline of 20 s covers the whole check, including the vantage test. All are in `Settings`. All are well inside the 60 s tick.

**Probe and I/O.** `NetworkProber.observe(host) -> Observation` is the only public network call. It opens a plain TCP connection and times it. Then it closes it and makes one `GET /` with httpx. httpx types do not leave `probe.py`. The User-Agent is a module constant, because the product rule is one fixed value. The test fixture is a local TLS server with a self-signed certificate. `Settings.ca_bundle` points the probe at it. No test uses the network or credentials.

**Migrations.** Plain SQL files in `migrations/`, applied in name order by `Store.migrate()`. One transaction for each file, under an advisory lock, with a checksum table. Slice 1 has no ORM models for Alembic to compare, so Alembic would only run raw SQL. The plain runner is about 40 lines. `schema.sql` in this package is `0001_init.sql`.

**Interface depth.** Four modules carry the design. Each hides one concern.

| Module | Public surface | Hidden behind it |
| --- | --- | --- |
| `probe` | `observe(host)` | DNS, TCP timing, TLS, httpx, body read limit, vantage test, error classification |
| `store` | 7 methods | SQL, pool, migrations, slot lookup, upsert, account resolution |
| `verdict` | `judge`, `CheckResult` | all verdict policy and the Cloudflare rule |
| `scheduler` | `Worker.run`, `tick` | grid timing, concurrency, drop of stale work, shutdown |

Callers call one method per operation. No caller coordinates several steps. The flow from clock to row crosses three files (`scheduler`, `probe`, `store`), per minimize-reader-load.

**Red flag screen.** Against `design-red-flags.md`.

- Shallow module. None. Each module hides a full concern behind two to seven methods.
- Information leakage. The slot grid exists in `domain.Slot` only. SQL exists in `store.py` only. httpx types exist in `probe.py` only.
- Temporal decomposition. The code groups by knowledge (network, rules, storage), not by stage.
- Split ownership. Each probe writes only its own rows. `target` has one writer, the CLI through `Store`.
- Two ways to do one task. One way to add a target. One function to judge. One write path.
- Importable internals. An import-linter contract fails the build on a wrong import (see `MODULE_MAP.md`).
- Hand-synced list. The `(verdict, reason)` pairs exist in the `Reason` enum and in a SQL `CHECK`. `test_schema_matches_enums.py` fails when they differ. I checked this equality in the sketch.

## Synthesis decision

Filled in by arena. This candidate is not the base or a graft until arena records that decision.

Parts that I think are most worth grafting if another candidate is the base: the slot key with `due()` as the only scheduler state, the tagged-union `Observation` with the probe network test, and the pairing of `Reason` and `Verdict` in one enum.

## Tradeoffs accepted

- We accept `jsonb` for the raw observation in exchange for no schema change when a new check kind arrives. Ad hoc psql queries need `->` paths.
- We accept one extra TCP handshake each check in exchange for a clean TCP timing and no use of httpx internals.
- We accept that the probe does not follow redirects in exchange for a simple, predictable rule. A site that redirects to a dead host shows "up".
- We accept a 60 second polling tick in exchange for no job table and no recovery code. It costs one cheap query a minute.
- We accept that a probe with a failed database write loses that attempt and probes again in the same slot. A buffer on disk is not in slice 1.
- We accept a CHECK constraint that lists reasons. A new reason needs a migration. This is deliberate, because the list is small and a wrong reason is a wrong verdict.
- We accept `check_deadline_s` above `https_timeout_s`. This can look like two timeouts for one thing. The first bounds a phase and the second bounds the whole check.
- We accept two workers with one `probe_id` double the traffic to targets. Data stays correct. A lock is not in slice 1.

## Alternatives considered

1. **Typed columns for every observation field in one wide table** (`tcp_ms`, `http_status`, ...). This is easier to query in psql. It lost on interface depth. Every new check kind adds nullable columns or a new table, and callers learn which columns apply to which kind. The jsonb union hides that.
2. **A config file (YAML or TOML) as the target list.** The file would need a sync into Postgres for the foreign key, or results would key on a host string. The first has two sources of truth. The second has no account and no stable id. The `target` table with a CLI has one source.
3. **Pre-created job rows per slot, claimed with `FOR UPDATE SKIP LOCKED`.** This helps multi-region assignment and shows "started, not finished". It lost because a scheduler and a worker would both write the same row, and a stale-claim reaper would be needed. In the chosen shape, the missing result row is the pending state.
4. **A scheduler library (Prefect, APScheduler, cron).** The house pattern uses Prefect. It needs a server and a database of its own, and the slot key is still required for idempotency. The loop here is small and testable with a fake clock. Revisit it when regions need remote dispatch.
5. **Key the result on `(target, probe, started_at)`.** A retry has a different `started_at`, so a repeat check cannot be detected. This fails the idempotency requirement.
6. **Use httpx trace hooks for one connection with TCP time and TLS time.** This saves one handshake. It depends on httpcore trace event names, which are not a public contract. It lost on information leakage.
7. **Compute the verdict in SQL (view or generated column).** This puts the rules in a second language. It makes the Cloudflare rule and replay hard. It lost.
8. **Alembic.** Not chosen, as explained under Migrations.

## Open questions and risks

- Should 401 and 403 count as "up" for some sites? The owner may have pages behind a login. A per-check status range would need a `params` column on `target_check`. The column is an additive migration.
- Should the probe follow redirects (up to five hops) in slice 1? What counts as up when the final host differs?
- Does a Cloudflare "Attention Required" page (WAF block, not a challenge) count as "blocked"? I included its marker. `PRODUCT.md` says "challenge" only.
- Are `one.one.one.one` and `dns.google` the right vantage anchors? Both are large providers. If both are down at once, a real target outage reads as "probe_fault". The multi-region rule limits that harm. Should the owner pick their own anchors?
- Should a later slice add a per-probe heartbeat row so a dead probe is detected by absence of the heartbeat, and not only by a gap in results?
- How long does the product keep raw results? The key leads with `check_id`. Time partitioning would need a rewrite of the table. Should slice 1 partition `check_result` by month now?
- Which probes run which checks? Slice 1 runs every active check on every probe. A later `check_probe` assignment table is additive.
- Should `account_id` be copied onto `check_result` for row-level security? It is now reachable only through two joins.
- Is a 60 second minimum interval (a schema CHECK) acceptable? It limits plans with a shorter interval.

## Next implementation step

Write `verdict.py` and `test_verdict.py` first. A table test with one case for each `Reason`, plus `test_schema_matches_enums.py`, fixes the verdict rules before any network or SQL code exists.
