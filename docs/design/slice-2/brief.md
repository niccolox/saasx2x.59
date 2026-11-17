# Design brief: SaaSX2X slice 2 (read-only dashboard)

## User goal

The owner wants one screen that shows the state of each monitored site, so the owner opens SaaSX2X each day instead of a SQL client. Kill criterion 3 of the bet in `.local/research/bet-process.md` counts that daily use for 14 days. The screen must also show when the worker writes no rows, because a stalled worker raises no error and loses the bet's evidence.

## What the page shows

For each active target and check, in hostname order:

1. The hostname and port, and the check interval.
2. The last result: verdict, reason, and how long ago the slot started.
3. A strip of the slots in the last 24 hours, one mark for each slot: up, down, blocked, inconclusive, or not observed.
4. Uptime for 24 hours and 7 days. Count "not observed" slots apart. Never count them as up.

The page refreshes about every 60 s. It also shows one line for the whole worker: when the newest row was written, so a stall is visible at once.

## Fixed constraints

- The operator chose React for the page. Use React with TypeScript, built with Vite. Do not use HTMX here.
- FastAPI serves the JSON API and the built page from one process, as a new CLI command `saasx2x web`. Add it as a Compose service `web` on `127.0.0.1:55441`. Node is needed only to build the page. The Python image must not need Node at run time.
- Read only. The web process never writes to Postgres. No sign-in. Bind to `127.0.0.1` only.
- The worker, the schema of `check_results`, and the verdict rules do not change. A new migration is allowed only for an index or a view that a query needs.
- Tests run offline with no credentials, against the Compose Postgres, the same way as slice 1 tests.
- Python 3.13, `uv`, Pydantic v2, `psycopg` 3. Keep `ruff` and `pyright` passing.
- The design must not block these later slices: sign-in and many accounts (every row has `account_id`), many probes (every row has `probe_id`; a slot can have several rows), and more check types.

## The existing system (slice 1)

Read `docs/design/slice-1/SYNTHESIS.md` and the code in `src/saasx2x/`. The facts that matter here:

- `store.py` is the only module that imports `psycopg` and holds SQL. Callers pass and get domain types. No row or cursor leaves it.
- `domain.py` holds pure Pydantic types. `Slot` is a slot aligned to the Unix epoch in UTC, with `containing(at, interval)` and `next()`.
- `verdict.py` holds `Verdict`, `Reason` (each reason owns its verdict), and the pure function `decide_verdict`. `CheckResult` is one row.
- `check_results` key is `(check_id, scheduled_at, probe_id)`. `scheduled_at` is the slot start. A missing row means "not observed". Rows also have `due_at`, `started_at`, `duration_ms`, `verdict`, `reason`, `rules_version`, `observation` (JSONB).
- `checks` has `interval_s` and `created_at`. `targets` has `removed_at`. A slot before the check existed is not "not observed". It is outside the check's life.
- `config.py` parses `SAASX2X_*` settings once. `SAASX2X_ACCOUNT` names the owner account.
- `cli.py` has `migrate`, `worker`, `check`, `target add|remove|list`.

## Open design questions for you to decide

- The API: how many endpoints, and the exact JSON shape. Which types own that shape, and how the TypeScript side gets the same shape without a hand-written copy.
- Where the "expected slots" rule lives (which slots a check should have had), and how "not observed" is computed: in Python from `Slot`, or in SQL with `generate_series`. One owner for that rule.
- How several probes for one slot fold into one mark later, without a rewrite now.
- How the React app is built and served in development and in Compose.
- How the page draws the strip (DOM, SVG, or canvas), and how it stays readable at 288 slots for 5-minute checks and 1,440 for 60 s checks.
- The test plan: what Python tests, what front-end tests, and one end-to-end check in a real browser.
- The module layout. Keep the call chain short.

## Output

Write your design package to the output path the orchestrator gives you. Use the architect runner prompt and the rationale template. Include the type sketch (Python with `raise NotImplementedError` bodies, and TypeScript types with stub components), any SQL, the module map, and the rationale. Do not write the implementation.
