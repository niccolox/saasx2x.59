# Rationale: SaaSX2X slice 1, candidate 1

## Problem

The owner wants to know if each of their sites is up. Slice 1 checks each site on port 443 one time in each 300 seconds and writes each result to Postgres. The repository has no code, so no caller constrains the shape. The later rules constrain it: many accounts, probes in several regions that must agree, more check types, and a 99.999% accuracy target. That target makes the result row evidence, not only a status. A later reader must be able to tell "the target failed" from "the probe failed" from "the probe did not check". A later rule change must be able to judge old rows again.

## Usage (caller's view)

The owner uses the command line.

```
docker compose up -d db
uv run saasx2x migrate
uv run saasx2x target add example.com
uv run saasx2x target list
uv run saasx2x check example.com      # one check now, prints the observation and the verdict, writes no row
uv run saasx2x worker                 # or: docker compose up -d worker
uv run saasx2x target remove example.com
```

The owner reads results with SQL. Slice 1 has no UI.

```sql
SELECT t.hostname, r.scheduled_at, r.verdict, r.duration_ms, r.observation->>'outcome' AS outcome
  FROM check_results r JOIN checks c ON c.id = r.check_id JOIN targets t ON t.id = c.target_id
 ORDER BY r.scheduled_at DESC LIMIT 20;
```

Call site 1, the worker, for each due check:

```python
observation = await check_https(check.hostname, check.port, tls=tls, timeouts=timeouts)
await store.record_result(CheckResult(
    check_id=check.check_id, probe_id=probe_id, scheduled_at=slot.start,
    started_at=started_at, duration_ms=duration_ms, observation=observation))
```

Call site 2, the command line:

```python
target = await store.add_target(settings.account, parse_hostname(args.hostname))
```

Call site 3, a test:

```python
observation = await check_https(Hostname("localhost"), tls_server.port, tls=untrusted, timeouts=Timeouts())
assert isinstance(observation, TlsFailed) and observation.error == "certificate_invalid"
assert decide_verdict(observation) is Verdict.DOWN
```

## Shape

**Core data.** A check gives one observation, and the observation gives one verdict.

`HttpsObservation` is a union of six classes with the discriminator `outcome`. A check has four stages on one connection: DNS, TCP, TLS, HTTP. Each class is one point where the check stops: `DnsFailed`, `TcpFailed`, `TlsFailed`, `HttpFailed`, `HttpResponded`, `ProbeFailed`. Each class holds only the facts that exist at that point, per type-system-discipline. Pydantic rejected a `dns_failed` with a status code in my test of the sketch (measured).

`decide_verdict(observation) -> Verdict` is one pure function with one table, per boundary-discipline.

| Observation | Verdict |
| --- | --- |
| `HttpResponded`, Cloudflare block rule is true | `blocked` |
| `HttpResponded`, status 200 to 399 | `up` |
| `HttpResponded`, status 400 to 599 | `down` |
| `DnsFailed(not_found)`, `TcpFailed`, `TlsFailed`, `HttpFailed` | `down` |
| `DnsFailed(unavailable)`, `ProbeFailed` | `inconclusive` |

The Cloudflare block rule is true in two cases. In case 1, the header `cf-mitigated: challenge` is present. In case 2, `server` is `cloudflare`, the status is 403, 429 or 503, and the first 4096 body bytes contain a marker of a Cloudflare challenge page or block page. The header `server: cloudflare` alone is not sufficient, because Cloudflare puts it on each response that it proxies. An origin 503 behind Cloudflare is `down`.

`inconclusive` is the fourth verdict. It means "this check gave no evidence about the target". A local socket error and a resolver that gave no answer get this verdict.

**The result row.** The key of `check_results` is `(check_id, scheduled_at, probe_id)`. `scheduled_at` is the start of the slot, and the wall clock gives it. The key names the work, not the attempt. A second run conflicts and the store keeps the first row, per make-operations-idempotent. Postgres 16 kept one row with the first verdict after two writes of one slot (measured with `schema.sql`). A slot with no row means "the probe did not check". The row stores the observation as JSONB, plus `verdict` and `rules_version`. The Pydantic union is the only definition of the observation fields, per the house rule on parallel field lists.

**Targets.** Postgres is the only source of truth. `saasx2x target add` and `target remove` are the only writers. `add` is an upsert, and `remove` sets `removed_at`, so a target keeps its id and its results. The worker reads the active checks at the start of each slot. It holds no copy.

**Schedule.** `run_worker` is a loop of about six lines. It calculates the current slot from the wall clock, runs `run_slot`, then sleeps to the end of the slot. No run feeds the next start time, so the schedule cannot drift. `run_slot` asks the store for the checks that have no row for this probe and slot, then starts one task for each. A semaphore of 20 bounds the open connections. The stage budgets are 5 s DNS, 5 s TCP, 5 s TLS, 15 s HTTP, so one check ends in 30 s at most. The end of the slot cancels each check that is not done. After a crash, the restart runs the current slot immediately and checks only what the slot lacks.

**Shared state.** Each probe writes only rows with its own `probe_id`. Two probes do not write the same row, so the design needs no lock, per separate-before-serializing-shared-state. The agreement of regions is a read on `(check_id, scheduled_at)`.

**Migrations.** Plain SQL files, applied in name order by `Store.migrate`, about 40 lines. The schema uses enum types and JSONB, and later uses partitions and row security. Alembic autogenerate needs SQLAlchemy models, and those models are a second field list beside the Pydantic domain.

**Interface depth.** `check_https` is one function. It hides the resolver, the address loop, the TLS handshake, HTTP parsing, four budgets, and the map from about 20 error conditions to six classes. It always returns and does not raise for a failure. `Store` has eight methods and hides all SQL, the transactions, the JSON mapping, and the conflict rules. No transport type is public. Callers see `Hostname`, `Slot`, `DueCheck`, `CheckResult`. The call chain is two files deep, per minimize-reader-load.

**What the design does not do.** No ICMP. No redirects followed. No retry in a slot. No fill of a past slot. No registry of check types. No alert, no UI, no account sign-in.

## Synthesis decision

Arena fills this section.

## Tradeoffs accepted

- We accept a hand-written HTTP/1.1 exchange with `h11` in exchange for one connection with an exact failure stage and an exact time for each stage.
- We accept JSONB for the observation in exchange for one field list. A chart of `tcp_connect_ms` must read a JSON key. `verdict` and `duration_ms` are columns.
- We accept a stored `verdict` that derives from the stored observation in exchange for an index on it later. The row is insert-only, and `rules_version` records which rules gave the verdict.
- We accept status 400 to 599 as `down` with no option for each check. A site that answers 401 at `/` shows as `down`.
- We accept `DnsFailed(unavailable)` as `inconclusive`. `getaddrinfo` cannot tell a dead local resolver from a dead name server of the target.
- We accept an empty slot when Postgres is down or the worker is down. The design has no local queue of results.
- We accept two extra tables with one row each (`accounts`, `probes`) and a `checks` table in exchange for a result key that later slices keep.
- We accept that two workers with one probe name both check each target. The key keeps the data correct. The targets get two requests.
- We accept the first row when a slot runs two times. A reader then never sees a row change.

## Alternatives considered

- **Two connections: a bare TCP probe, then an `httpx` request.** It is the literal text of the brief and the least code. It lost because "TCP connected, then TCP failed" becomes a state that the verdict rules must handle. It also sends two connections to each target, and `httpx` puts DNS, TCP and TLS failures in one `ConnectError`, so the caller must inspect the cause chain.
- **Targets in a YAML file.** It is easy to edit. It lost because result rows need a target id, so a sync step must copy the file into Postgres. That makes two lists of targets. The next slice gives each account its targets in Postgres in any case.
- **One wide table with a column for each observation field, with SQLAlchemy and Alembic.** It gives direct SQL on each field. It lost because each new check type adds nullable columns and a migration, and the models repeat the Pydantic fields.
- **A cron entry or systemd timer that runs one slot and exits.** The operating system gives the fixed rate and the restart. It is a real contender, and `run_slot` supports it with no change. It lost for slice 1 because the timer configuration is outside the repository and outside Compose, and a different interval for each plan does not fit one timer.
- **A jobs table with `FOR UPDATE SKIP LOCKED`.** It lets many workers share one region. It lost because slice 1 has one worker, and the result key already makes two workers safe.

## Open questions and risks

- Is one connection with four stages an acceptable reading of "TCP connect, then HTTPS"? The alternative is a separate TCP probe before the request.
- Should a status of 401, 403 or 404 at `/` be `down`? If the owner has such a site, the check needs an expected status set.
- Is a 3xx response `up` without a request to the redirect location?
- Is a Cloudflare 429 rate limit page `blocked`? The brief names 403 and 503 only.
- I wrote the Cloudflare page markers from memory (a guess). Will the owner capture one real challenge page and one real block page as test fixtures?
- A heartbeat has no probe, and `check_results.probe_id` is NOT NULL. Does a heartbeat get its own table?
- Slots align on UTC. Do all probe hosts run NTP? A clock error of some seconds moves a check to a different slot.
- Does the worker run in Compose or on the host? A container uses the Docker network path, and its failures look like probe failures.
- How long do raw results stay? One target makes 288 rows each day (calculated).

## Next implementation step

Write `domain.py` and `verdict.py` with `tests/test_verdict.py`, one case for each row of the verdict table, before any I/O code.
