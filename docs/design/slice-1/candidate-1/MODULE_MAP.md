# Module map: SaaSX2X slice 1, candidate 1

## Files

```
saasx2x.59/
  pyproject.toml            uv project, Python 3.13, entry point `saasx2x = saasx2x.cli:main`
  compose.yml               `db` (postgres:16, 127.0.0.1:55440) and `worker` (restart: unless-stopped)
  Dockerfile                image for the `worker` service
  migrations/
    0001_init.sql           the content of schema.sql
  src/saasx2x/
    domain.py               ids, Hostname, Slot, Target, DueCheck, the HttpsObservation union
    verdict.py              Verdict, RULES_VERSION, decide_verdict, CheckResult
    https_check.py          USER_AGENT, Timeouts, tls_context, check_https
    store.py                Store, StoreUnavailable
    worker.py               run_worker, run_slot, SlotSummary
    config.py               Settings
    cli.py                  main
  tests/
    conftest.py             local TLS server (trustme CA), throwaway Postgres database
    test_verdict.py         one case for each row of the verdict table, with Cloudflare fixtures
    test_https_check.py     the check against the local TLS server
    test_store.py           each write two times, then the row count
    test_worker.py          run_slot two times; one slow target; a 1 second interval for 3 slots
    test_schema.py          SQL enum values equal the Python enum values
```

The sketch of each module is in `sketch/saasx2x/`.

## What each module owns

| Module | Knowledge that it owns | Does I/O | Imports from the package |
| --- | --- | --- | --- |
| `domain.py` | The shape of a target, a slot, and an observation | No | Nothing |
| `verdict.py` | What "up", "down", "blocked" and "inconclusive" mean | No | `domain` |
| `https_check.py` | How to do DNS, TCP, TLS and HTTP on one connection, and how to name each failure | Network | `domain` |
| `store.py` | All SQL, all transactions, the JSON form of an observation | Postgres | `domain`, `verdict` |
| `worker.py` | When a check runs and how many run together | Clock | all modules above, `config` |
| `config.py` | The environment variables and their defaults | Environment | `domain`, `https_check` |
| `cli.py` | The command names and the parse of owner input | Terminal | all modules above |

## Public names

| Module | Public names | Count |
| --- | --- | --- |
| `domain.py` | `parse_hostname`, `Slot`, `Target`, `DueCheck`, `HttpsObservation` and its six classes, five id types | types only |
| `verdict.py` | `Verdict`, `RULES_VERSION`, `decide_verdict`, `CheckResult` | 1 function |
| `https_check.py` | `USER_AGENT`, `Timeouts`, `tls_context`, `check_https` | 2 functions |
| `store.py` | `Store` with `connect`, `migrate`, `add_target`, `remove_target`, `list_targets`, `register_probe`, `due_checks`, `record_result` | 8 methods |
| `worker.py` | `run_worker`, `run_slot` | 2 functions |
| `cli.py` | `main` | 1 function |

## Data flow of one slot

```
worker.run_slot(slot)
  store.due_checks(probe_id, slot)            -> list[DueCheck]
  for each DueCheck, in its own task:
    https_check.check_https(hostname, port)   -> HttpsObservation
    verdict.CheckResult(observation=...)      -> verdict derives from the observation
    store.record_result(result)               -> one INSERT ... ON CONFLICT DO NOTHING
```

The call chain is two files deep: `worker.py`, then one leaf. No leaf calls a different leaf.

## Structural guards

| Rule | How the build enforces it |
| --- | --- |
| Only `store.py` imports `psycopg` | ruff `TID251` bans `psycopg`, with a per-file exception for `store.py` |
| Only `https_check.py` imports `ssl`, `socket`, `h11` | ruff `TID251` in the same way |
| Each observation class has a verdict | `match` with `assert_never` in `decide_verdict`, and pyright in `make ci` |
| SQL enums equal Python enums | `tests/test_schema.py` reads `enum_range` and compares |
| A verdict agrees with its observation | `CheckResult.verdict` is a computed field, not an input |
| One User-Agent | `USER_AGENT` is a constant, and `check_https` has no header parameter |
| An applied migration file does not change | `Store.migrate` compares the sha256 of each applied file |

## Dependencies

| Package | Use |
| --- | --- |
| `pydantic`, `pydantic-settings` | Domain model and settings |
| `psycopg[binary,pool]` 3 | Async Postgres driver and pool |
| `h11` | HTTP/1.1 parser with no I/O, on the socket that the check opens |
| dev: `pytest`, `pytest-asyncio`, `trustme`, `ruff`, `pyright` | Tests, lint, types |

The design does not use SQLAlchemy, Alembic, httpx, APScheduler or Prefect.

## Later slices, and where each one goes

| Later rule | Change | Rewrite of slice 1 (inferred, not built) |
| --- | --- | --- |
| Many accounts | More rows in `accounts`. Sign-in replaces `Settings.account`. | None |
| Probes in several regions | One worker for each region with its own `probe_name`. Each writes its own rows. | None |
| Agreement of regions | A reader groups `check_results` on `(check_id, scheduled_at)`. | None |
| Probe network failure | A reader finds a slot where one probe failed all its checks. Add an index on `(probe_id, scheduled_at)` with that reader. | None |
| DNS, SSL expiry, TCP checks | A value in `check_kind`, a sibling of `https_check.py`, new classes in the observation union, a `match check.kind` in `run_slot`. | None |
| A different interval for each plan | A column `interval_seconds` on `checks`. `due_checks` filters on it. | None |
| Retention | Partition `check_results` by range on `scheduled_at`. The primary key contains that column. | None |
| Heartbeat | No probe makes a heartbeat, and `check_results.probe_id` is NOT NULL. A heartbeat needs its own table or a probe row for the control plane. | Open question |
