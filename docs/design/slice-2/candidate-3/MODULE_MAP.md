# Module map: slice 2, candidate 3

## Files

| Path | Status | Owns |
| --- | --- | --- |
| `src/saasx2x/status.py` | new, pure | The read model. Expected slots, probe fold, worker state, sort order, uptime ratio. The JSON shape of `/api/status`. |
| `src/saasx2x/web.py` | new, thin shell | FastAPI app, `StatusReader` protocol, host allow-list, static files, `serve`, `openapi_json`. |
| `src/saasx2x/store.py` | changed | Adds `ReadStore.status_facts` (3 read statements). Moves pool code to a private base `_Pooled`. No change to `Store` methods. |
| `src/saasx2x/config.py` | changed | Adds `web_host`, `web_port`. |
| `src/saasx2x/cli.py` | changed | Adds the `web` command (one branch). |
| `migrations/0002_status_reads.sql` | new | One index: `check_results (account_id, started_at DESC)`. |
| `web/` | new | The React app. See below. |
| `Dockerfile`, `compose.yml`, `pyproject.toml` | changed | Node build stage, `web` service, `fastapi` and `uvicorn`. |
| `domain.py`, `verdict.py`, `worker.py`, `https_check.py` | unchanged | |

`web/` files:

| Path | Owns |
| --- | --- |
| `openapi.json`, `src/api.gen.ts` | Generated. Committed. The TypeScript contract. |
| `src/api.ts` | The only importer of `api.gen.ts`. Names the types. `fetchBoard`. |
| `src/useBoard.ts` | Refresh loop, last-good-board reducer, `link()` (the page's own staleness). |
| `src/layoutStrip.ts` | Pure: runs to pixel rectangles on a time axis. `describeStrip`. |
| `src/labels.ts` | Text and mark style. `Record<Union, ...>` makes the compiler check each list. |
| `src/format.ts` | Age and percent text. No rule. |
| `src/App.tsx`, `WorkerLine.tsx`, `CheckRow.tsx`, `StripChart.tsx` | Components. |
| `src/fixtures/board.json` | Golden board. Written by a Python test. Read by Vitest. |
| `e2e/status.spec.ts` | Playwright. |

## Dependency direction

```
cli.py ──> web.py ──> status.py ──> domain.py, verdict.py
              │            ▲
              └──> store.py ┘   (store.py imports status.py types; status.py never imports store.py)
```

`web.py` names `StatusReader` (a protocol), not `ReadStore`, in `create_app`. `serve` is the one
place that builds a `ReadStore`.

## Longest call chain (one request)

`GET /api/status` -> `web.status` -> `ReadStore.status_facts` (SQL) -> `status.build_board` -> JSON.
Three files: `web.py`, `store.py`, `status.py`. No fourth layer. No service or repository class.

## Data flow with types

```
as_of: datetime (web clock)
  └─ ReadStore.status_facts(account, since=as_of-7d, as_of) -> StatusFacts
        checks: tuple[CheckFacts(check, created_at, last, rows: tuple[SlotRow])]
        newest_row: NewestRow | None
  └─ build_board(facts, as_of) -> StatusBoard
        worker: Worker(state, newest_row_at, silent_s, expected_every_s)
        checks: tuple[CheckStatus(..., strip: Strip(runs), tally_24h, tally_7d)]
  └─ FastAPI serializes StatusBoard
  └─ openapi-typescript reads the same type -> components["schemas"]["StatusBoard"]
  └─ React: useBoard -> App -> WorkerLine, CheckRow -> StripChart -> layoutStrip -> <rect>
```

## API

| Route | Response | Note |
| --- | --- | --- |
| `GET /api/status` | `StatusBoard`, or 503 `Problem` | One response, one database snapshot. `Cache-Control: no-store`. |
| `GET /healthz` | `{"ok": true}` | Process only. For the Compose health check. |

## Build and run

| Step | Command |
| --- | --- |
| Compose, all | `docker compose up -d --build` then open `http://127.0.0.1:55441/` |
| Dev, API | `docker compose up -d db`, `uv run saasx2x migrate`, `uv run saasx2x web` |
| Dev, page | `cd web && npm ci && npm run dev` then open `http://127.0.0.1:5173/` (Vite proxies `/api`) |
| Regenerate the contract | `cd web && npm run gen` (needs `uv`), commit `openapi.json` and `src/api.gen.ts` |
| Check the contract | `npm run gen:check` (CI step) and the Python test `test_openapi_snapshot` |

The run image has no Node. The first Docker stage builds `web/dist`. The second stage copies it.
The Python side finds it at `parents[2] / "web" / "dist"`, the same pattern as `MIGRATIONS_DIR`.

## Test plan

Python (offline, Compose Postgres, same fixtures as slice 1):

| File | Tests |
| --- | --- |
| `tests/test_status.py` (pure, no DB) | `expected_slots`: first full slot after creation; the open slot is not owed; the open slot with a row is counted; a 60 s and a 300 s interval; a row off the grid is ignored. `fold_probes`: table of verdict sets. `Mark` and `Verdict` have the same members plus `not_observed`. `Tally`: never counts not observed as up; `uptime` is None for no up and no down. `run_length`: adjacent runs differ; sum of counts equals input; a seeded random sequence of 1,440 round-trips. `judge_worker`: idle, fresh, late, stalled, and no rows with an old check. `GRACE >= worker.CHECK_BUDGET + worker.SLOT_MARGIN`. `build_board` sorts by hostname then port. Cost test: 7 d of 60 s rows for 20 checks builds in under 1 s. |
| `tests/test_status_store.py` (DB) | `status_facts` returns seeded rows, last result, newest row. Removed targets are absent. Another account is absent. A write on a `ReadStore` connection raises `ReadOnlySqlTransaction`. Migration 0002 applies twice with no change. A missing schema raises `StoreUnavailable`. |
| `tests/test_web.py` (fake reader, `httpx` TestClient) | Shape of `/api/status`. 503 body on `StoreUnavailable`. `Host: evil.example` gets 400. `/healthz`. Missing `dist` gives 503 text at `/`. `test_openapi_snapshot`: `openapi_json() == web/openapi.json`. `test_compose_publishes_web_on_loopback`. `test_golden_board`: `build_board(GOLDEN_FACTS, FIXED_AS_OF)` equals `web/src/fixtures/board.json`; set `SAASX2X_UPDATE_GOLDEN=1` to write it. |
| `tests/test_cli.py` | `saasx2x web --help` runs. `Settings().web_host == "127.0.0.1"`. |

Front end (`npm test`, Vitest, jsdom): see `sketch/web/src/layoutStrip.test.ts`. Pure tests for
`layoutStrip`, `reduce`, `link`, `format`. Component tests render `App` with the golden fixture.

End to end (`npm run e2e`, Playwright, Chromium): `tests/e2e_serve.py` makes a scratch database,
seeds rows through `Store.record_result`, and serves the app on a port. Two scenarios, `healthy`
and `stalled`. The spec in `sketch/web/e2e/status.spec.ts` lists the checks. Chromium downloads
once with `npx playwright install chromium`. The default `uv run pytest` does not run Playwright.

Two quality gates stay: `ruff check` and `pyright` (strict on `src`). `npm run typecheck` runs
`tsc --noEmit` with `strict`.
