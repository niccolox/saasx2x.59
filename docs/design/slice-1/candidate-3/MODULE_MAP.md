# Module map, candidate 3

## Layout

```
saasx2x/
  pyproject.toml            uv project. Python 3.13. Import-linter contracts below.
  compose.yaml              postgres:16, ports "127.0.0.1:55440:5432". Optional worker service.
  migrations/0001_init.sql  same content as schema.sql
  src/saasx2x/
    domain.py               pure types: ids, Hostname, Slot, Observation union, DueCheck, Target
    verdict.py              Verdict, Reason, judge(), CheckResult, RULES_VERSION
    settings.py             Settings (env SAASX2X_*)
    probe.py                Prober protocol, NetworkProber, USER_AGENT. Only module with network I/O.
    store.py                Store. Only module with SQL. Migrations, targets, due(), write().
    scheduler.py            Clock, Worker. Only module that imports both probe and store.
    cli.py                  argparse entry point
  tests/
    certs/                  self-signed certificate and key for the local TLS server
    conftest.py             local TLS server fixture, Postgres fixture on a temporary database
    test_verdict.py         table test of judge(), one case for each Reason
    test_probe.py           NetworkProber against the local TLS server (up, 500, closed port, reset)
    test_store.py           due(), write() twice, add and remove target
    test_scheduler.py       fake Clock and fake Prober. Slow target, crash and restart.
    test_schema_matches_enums.py   SQL pairs equal the Reason enum
```

## Dependencies between modules

```
cli ──> scheduler ──> probe ──> domain, settings
                 ├──> store ──> verdict ──> domain
                 └──> verdict, domain, settings
```

Written as rules:

| Module | May import |
| --- | --- |
| domain | nothing from saasx2x |
| verdict | domain |
| settings | domain |
| probe | domain, settings |
| store | domain, verdict |
| scheduler | domain, verdict, settings, probe, store |
| cli | all |

Encoding. `pyproject.toml` holds an import-linter `layers` contract with these rules. `probe` and `store` must not import each other. `ci` runs `lint-imports`. A wrong import fails the build.

## One check, from the clock to the row

1. `Worker.tick` calls `Store.due(probe_id, now)`. It gets `DueCheck` values.
2. `Worker._run_one` calls `Prober.observe(host)`. It gets an `Observation`.
3. `Worker._run_one` builds `CheckResult(...)`. `CheckResult.reason` calls `judge`.
4. `Worker._run_one` calls `Store.write(result)`.

Three files for the whole flow: `scheduler.py`, `probe.py`, `store.py`. `verdict.py` and `domain.py` are pure.

## Public surface

| Module | Public names |
| --- | --- |
| probe | `Prober`, `NetworkProber`, `USER_AGENT` |
| store | `Store` (7 methods) |
| verdict | `judge`, `CheckResult`, `Reason`, `Verdict`, `RULES_VERSION` |
| scheduler | `Worker`, `Clock`, `SystemClock` |
| domain | types only |

Helpers start with an underscore. No module re-exports another module's names.

## Migrations

Plain SQL files in `migrations/`, named `NNNN_name.sql`. `Store.migrate()` applies them in order. See RATIONALE.md for the reason.

## Run

```
docker compose up -d db
uv run saasx2x migrate
uv run saasx2x target add example.com
uv run saasx2x worker
```
