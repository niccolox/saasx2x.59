# Module map (candidate 2)

## Repository layout

```
saasx2x/
  pyproject.toml          uv project, Python 3.13, console script "saasx2x = saasx2x.cli:main"
  compose.yml             db (postgres:16) and worker
  Dockerfile              uv sync --frozen, runs "saasx2x worker"
  Makefile                up, migrate, test, lint, types
  migrations/
    0001_init.sql         same text as schema.sql in this package
  src/saasx2x/
    domain.py             ids, Hostname, CheckSpec, Stage, Observation, ResultKey
    verdict.py            Verdict, BlockSignal, Judgment, judge(), RULES_VERSION
    probe.py              observe(): DNS, TCP, TLS, HTTP on one socket
    scheduler.py          slot math, plan(), run_worker()
    store.py              Store: all SQL, migrations, row parsing
    cli.py                argv and environment parsing, Settings
  tests/
    conftest.py           trustme CA, local TLS server, Postgres fixture
    test_probe.py
    test_verdict.py
    test_scheduler.py
    test_store.py
    test_schema_sync.py
```

## Ownership

| Module | Owns | Imports | Public names |
| --- | --- | --- | --- |
| `domain.py` | The shape of a check and of an observation, and their invariants | pydantic | ids, `parse_hostname`, `parse_path`, `CheckSpec`, `Stage`, `FailureReason`, `Answer`, `Failure`, `Observation`, `ResultKey`, `SlotStart`, `Frozen` |
| `verdict.py` | What an observation means. The status table and the reason table | domain | `judge`, `Verdict`, `BlockSignal`, `Judgment`, `RULES_VERSION` |
| `probe.py` | Network I/O for one check, time limits, errno table, Cloudflare page markers, User-Agent | domain, h11, ssl, asyncio | `observe`, `ProbeEnv`, `default_env`, `Budget`, `BUDGET`, `USER_AGENT` |
| `scheduler.py` | When a check runs, concurrency bound, restart look-back | domain, probe, store | `run_worker`, `plan`, `slot_start`, `offset`, `Clock` |
| `store.py` | Every SQL statement, migrations, target add and remove, row writes | domain, verdict, psycopg | `Store`, `TargetView` |
| `cli.py` | Process boundary: argv, environment, exit codes | all of the above | `main`, `Settings` |

Each piece of state has one writer:

| State | Writer | Readers |
| --- | --- | --- |
| `account`, `target`, `target_check` rows | `Store.add_target`, `Store.remove_target` (from the CLI) | worker through `Store.active_checks` |
| `probe` row | `Store.register_probe` (worker start) | worker |
| `check_result` rows | `Store.record` (worker only, append-only, one row per key) | CLI `target list`, later slices |
| Verdict rules | `verdict.py` | `Store.record`, CLI `check` |

## Call chain for one check

```
cli.main("worker")
  -> scheduler.run_worker            reload checks, plan the window, wait, dispatch
       -> probe.observe              Observation (never raises)
       -> store.record               judge(observation), INSERT ... ON CONFLICT DO NOTHING
            -> verdict.judge
```

From the scheduler, a reader opens three files to trace one check end to end.

## Dependencies

| Package | Why |
| --- | --- |
| `pydantic>=2.9` | Domain model (house pattern) |
| `psycopg[binary,pool]>=3.2` | Async Postgres driver and pool. No ORM, no SQLAlchemy |
| `h11>=0.14` | HTTP/1.1 parser on our own TLS socket. Same parser httpx uses underneath |
| dev: `pytest`, `pytest-asyncio`, `trustme`, `pyright`, `ruff` | `trustme` makes a test CA and a `localhost` certificate offline |

No httpx. observe() owns the socket so that the TCP connect, the TLS handshake and the request all happen on one connection with a time for each stage.

## compose.yml (sketch)

```yaml
services:
  db:
    image: postgres:16
    environment: {POSTGRES_USER: saasx2x, POSTGRES_PASSWORD: saasx2x, POSTGRES_DB: saasx2x}
    ports: ["127.0.0.1:55440:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: {test: ["CMD", "pg_isready", "-U", "saasx2x"], interval: 2s, retries: 30}
  worker:
    build: .
    command: ["saasx2x", "worker"]
    environment:
      SAASX2X_DATABASE_URL: postgresql://saasx2x:saasx2x@db:5432/saasx2x
      SAASX2X_PROBE_NAME: local-1
      SAASX2X_PROBE_REGION: local
    depends_on: {db: {condition: service_healthy}}
    restart: unless-stopped
volumes: {pgdata: {}}
```

`saasx2x worker` runs `Store.migrate()` first. Migration is idempotent and holds an advisory lock, so two workers that start together apply each file once.

## Tests (all offline, no credentials)

| Test file | What it proves | Needs |
| --- | --- | --- |
| `test_probe.py` | One local TLS server per case: 200 is up, 503 is down, 403 with `cf-mitigated: challenge` is blocked, Cloudflare challenge body is blocked, 429 is blocked, a closed port is `tcp/refused`, a server that accepts and never handshakes is `tls/timeout`, an untrusted certificate is `tls/tls_cert_invalid`, a server that stalls headers is `http/timeout`, garbage bytes are `http/bad_response`, a fake resolver with EAI_NONAME is `dns/nxdomain`. The server asserts the User-Agent on every request. | trustme, asyncio |
| `test_verdict.py` | Table cases for rules 1 to 6 and for every `FailureReason` | nothing |
| `test_scheduler.py` | `plan()` gives due times exactly `interval_s` apart over 1000 slots. Offsets stay inside the slot budget. A recorded key is not planned again. A restart mid-slot runs the missing checks at once and skips ended slots. A fake slow target does not delay a fast one (fake clock). | nothing |
| `test_store.py` | `record()` twice with one key gives one row and returns False the second time. `add_target` twice gives one target. Remove then add keeps the old id and its results. | local Postgres from compose |
| `test_schema_sync.py` | Python enums equal `pg_enum` values. `record()` column list equals `information_schema.columns` of `check_result`. | local Postgres |
