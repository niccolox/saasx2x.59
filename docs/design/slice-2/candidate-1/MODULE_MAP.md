# Module map: SaaSX2X slice 2, candidate 1

## Files

```
saasx2x.59/
  pyproject.toml              changed: add `fastapi`, `uvicorn`; dev: `httpx`, `pytest-playwright`;
                              ruff: ban `fastapi`, `starlette`, `uvicorn` outside web.py
  Dockerfile                  changed: a Node stage builds the page; the Python stage copies web/dist
  compose.yml                 changed: add service `web` on 127.0.0.1:55441
  .gitignore                  changed: web/node_modules/, web/dist/, web/src/api.gen.ts
  .dockerignore               new: web/node_modules, web/dist, .venv, .git
  README.md                   changed: how to open the dashboard and how to build the page
  migrations/                 no change. Slice 2 has no migration.
  src/saasx2x/
    domain.py                 changed: add SlotRange, expected_slots
    verdict.py                changed: add VERDICT_TIE_ORDER, fold_probes
    store.py                  changed: add ReadStore and its five value types
    dashboard.py              new: the JSON shape and the rules of the page
    web.py                    new: create_app, openapi_document, serve
    config.py                 changed: add web_host, web_port
    cli.py                    changed: add `saasx2x web [--openapi]`
    worker.py, https_check.py no change
  web/
    package.json              scripts: gen, dev, build, test
    package-lock.json
    vite.config.ts            dev proxy of /api to 127.0.0.1:55441; vitest settings
    tsconfig.json
    index.html
    openapi.json              in git. A copy of `saasx2x web --openapi`. A Python test checks it.
    src/
      api.gen.ts              not in git. `npm run gen` writes it from openapi.json.
      api.ts                  type names, Snapshot, fetchDashboard
      time.ts                 serverNowMs, formatAge, formatUtc, formatRatio
      marks.ts                MARK_LABEL, MARK_DRAW_ORDER, REASON_LABEL, WORKER_LABEL
      useDashboard.ts         useDashboard, useServerNow
      App.tsx                 App
      WorkerLine.tsx          WorkerLine
      CheckRow.tsx            CheckRow
      Strip.tsx               layoutStrip, Strip, describeRun
      Uptime.tsx              Uptime
      fixtures.ts             dashboards for the tests, each `satisfies Dashboard`
      styles.css              one file, colours as custom properties
      *.test.ts(x)            vitest
  tests/
    test_dashboard.py         new: the pure rules, no database
    test_store_read.py        new: ReadStore against the Compose Postgres
    test_web.py               new: the API through httpx, the OpenAPI copy
    test_browser.py           new: one check in Chromium
```

The sketch of each file is in `sketch/`. The read statements are in `queries.sql`.

## What each module owns

| Module | Knowledge that it owns | Does I/O | Imports from the package |
| --- | --- | --- | --- |
| `domain.py` | Which slots a check must have a row for (`expected_slots`) | No | Nothing |
| `verdict.py` | How the rows of several probes for one slot become one judgement (`fold_probes`) | No | `domain` |
| `store.py` | All SQL. `ReadStore`: which rows exist, grouped by slot. It gives no verdict to a slot. | Postgres, read only | `domain`, `verdict` |
| `dashboard.py` | The JSON shape of the page. What a strip shows, what an uptime counts, when the worker is stalled. | No, except `read_dashboard` through the store | `domain`, `verdict`, `store` |
| `web.py` | HTTP: the route, the status codes, the files of the page, which account a request reads | HTTP | `dashboard`, `store`, `config` |
| `web/src/api.ts` | How the page gets a snapshot. The names of the generated types. | `fetch` | `api.gen.ts` |
| `web/src/useDashboard.ts` | When the page asks again, and when its own data is old | Timers | `api.ts` |
| `web/src/Strip.tsx` | How runs become rectangles on a time axis | No | `api.ts`, `marks.ts`, `time.ts` |

## Public names

| Module | Public names added | Count |
| --- | --- | --- |
| `domain.py` | `SlotRange`, `expected_slots` | 1 function |
| `verdict.py` | `VERDICT_TIE_ORDER`, `fold_probes` | 1 function |
| `store.py` | `ReadStore` with `connect`, `monitored_checks`, `slot_evidence`, `evidence_counts`; `MonitoredCheck`, `NewestRows`, `EvidenceWindow`, `SlotEvidence`, `EvidenceCount` | 4 methods |
| `dashboard.py` | `Dashboard`, `WorkerStatus`, `CheckStatus`, `LastResult`, `Strip`, `StripRun`, `SlotCounts`, `Mark`; `read_dashboard`, `build_dashboard`; `DAY`, `WEEK`, `REFRESH_AFTER`, `STALL_SLACK` | 2 functions |
| `web.py` | `create_app`, `openapi_document`, `serve` | 3 functions |
| HTTP | `GET /api/dashboard`, `GET /`, `GET /assets/*` | 1 JSON route |

## Data flow of one refresh

```
browser: useDashboard            GET /api/dashboard each refresh_after_s, and when the tab shows
web.py:  dashboard(account)      account = current_account(); now = clock()
  dashboard.read_dashboard(store, account, now)
    store.monitored_checks(account)                 -> list[MonitoredCheck]      statement 1
    dashboard._strip_window / _week_window          -> list[EvidenceWindow]      pure, uses expected_slots
    store.slot_evidence(account, day windows)       -> list[SlotEvidence]        statement 2
    store.evidence_counts(account, week windows)    -> list[EvidenceCount]       statement 3
    dashboard.build_dashboard(checks, day, week, now) -> Dashboard               pure
      domain.expected_slots     which slots with no row are "not observed"
      verdict.fold_probes       the rows of one slot -> one Reason
web.py:  Dashboard -> JSON (Pydantic)
browser: api.fetchDashboard      -> Snapshot { dashboard, receivedAtMs }
         App -> WorkerLine, CheckRow -> Strip, Uptime
```

A reader follows one request through three Python files: `web.py`, `dashboard.py`, `store.py`.

## How the TypeScript types stay equal to the Python types

```
dashboard.py (Pydantic)  --create_app().openapi()-->  web/openapi.json  --openapi-typescript-->  web/src/api.gen.ts
        test_web.py fails when openapi.json is old            npm run gen, before dev, build and test
```

1. Change a class in `dashboard.py`.
2. Run `uv run saasx2x web --openapi > web/openapi.json`. If you do not, `test_web.py` fails.
3. Run `npm --prefix web test`. `tsc` fails where the page uses a field that changed. `tsc` also fails in `marks.ts` when a verdict, a reason, or a worker state has no label.

The diff of `web/openapi.json` shows each change of the API in review.

## Test plan

| File | What it proves | Needs |
| --- | --- | --- |
| `tests/test_dashboard.py` | `expected_slots`: a slot before `created_at` is not expected; the open slot is not expected; the span limits the range; an interval that does not divide 24 hours. | Nothing |
| | `fold_probes`: one row gives that row; the order of the rows does not matter; `[up, down]` gives up; `[down, down, up]` gives down. | Nothing |
| | `build_dashboard`: a gap gives a "not observed" run; no run before the check existed; the open slot shows only with a row; equal slots merge; a 60 s check that is up all day gives one run. | Nothing |
| | The counts: for each case, `day.expected` equals `expected_slots(...).count`; "not observed" is never in `up`; the names of the `SlotCounts` fields equal the values of `Mark`. | Nothing |
| | `_worker_status`: one case for each of the four states, and a new check starts the wait again. | Nothing |
| `tests/test_store_read.py` | Two probes for one slot give one `SlotEvidence` with two reasons. `evidence_counts` equals a count over `slot_evidence` for the same window. | Compose Postgres |
| | A removed target is not in `monitored_checks`. A row of a different account is never returned. `newest` is the newest slot, also when it is 3 days old. | Compose Postgres |
| | An `INSERT` on a `ReadStore` connection raises `ReadOnlySqlTransaction`. | Compose Postgres |
| `tests/test_web.py` | `GET /api/dashboard` with a fixed clock returns a body that `Dashboard.model_validate` accepts, with `Cache-Control: no-store`. | Compose Postgres |
| | A database with no schema gives 503 with JSON. A `Host` of a different name gives 400. | Compose Postgres |
| | `GET /` serves `index.html` from a temp `dist`. With no `dist`, `GET /` gives 503 and the build command. | Nothing |
| | `web/openapi.json` equals `openapi_document(Settings())`. | Nothing |
| `tests/test_cli.py` | `saasx2x web --openapi` prints JSON and exits 0 with no Postgres. | Nothing |
| `web/src/Strip.test.tsx` | `layoutStrip`: x and width come from the times; "down" is last in the draw order. The 1,440 slot fixture with one down slot renders one "down" rect with the stroke class. | Node |
| `web/src/useDashboard.test.ts` | With fake timers and a fake `fetch`: a request each `refresh_after_s`; a failure keeps the snapshot and gives "stale"; the next answer gives "live"; a tab that becomes visible asks at once. | Node |
| `web/src/time.test.ts` | `serverNowMs` does not read the wall clock. `formatAge` and `formatRatio` cases. | Node |
| `web/src/App.test.tsx` | The `stalledWorker` fixture renders an element with role "alert" and the text "Worker stalled". | Node |
| `tests/test_browser.py` | The whole path in Chromium. See the steps in `sketch/tests/test_browser.py`. | Compose Postgres, the built page, Chromium |

`uv run pytest` runs each Python test offline. `test_browser.py` skips with a reason when the page is not built. `npm --prefix web test` runs `tsc` and vitest offline after one `npm ci`.

## What stays open for later slices

| Later slice | What it changes | What it does not change |
| --- | --- | --- |
| Sign-in and many accounts | The body of `current_account` in `web.py` | Each `ReadStore` method takes the account and filters on `account_id`. No URL has an account. |
| Many probes | Nothing, if the rule of `fold_probes` is right. Else that one function. | `SlotEvidence.reasons` already holds one reason for each probe. The JSON has one mark for each slot. |
| A line for each probe | `WorkerStatus` becomes a list in `Dashboard`, with one more store read | The check rows |
| More check types | New members of `CheckKind` and `Reason`, and their labels in `marks.ts` (`tsc` asks for them) | `CheckStatus` has `kind`. The strip and the counts do not depend on the kind. |
