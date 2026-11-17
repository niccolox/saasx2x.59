# Slice 2 synthesis: the design contract

Base: candidate 1 (`candidate-1/`). Use its `RATIONALE.md`, `MODULE_MAP.md`, `queries.sql`, and `sketch/` as the starting contract. The changes below override candidate 1 where they differ. Do not take other parts of candidates 2 and 3.

No cross-judge ran. Every available model is from one vendor (Anthropic), and the arena skill forbids a same-vendor judge.

## Scores

| Rubric item | C1 | C2 | C3 |
| --- | --- | --- | --- |
| One owner of the expected-slot rule | 5 | 5 | 5 |
| Sign-in, accounts, and probes later with no rewrite | 4 | 5 | 4 |
| TypeScript types derived from Python | 5 | 5 | 5 |
| Smallest code, short call chain, SQL only in `store.py` | 5 | 3 | 4 |
| Strip readable and cheap at 1,440 slots | 4 | 5 | 5 |
| Test plan with a real browser check | 5 | 5 | 5 |

C1 won because each new rule sits beside the type it extends: `expected_slots` beside `Slot` in `domain.py`, and `fold_probes` beside `Reason` in `verdict.py`. It reads 7 days as counted rows and needs no migration. C2 lost on layering: `store.py` imports `dashboard.py`, so the store depends on page rules. C3 lost on the 7-day read, which folds about 10,000 rows for each 60 s check in Python.

## Convergence (all three agree, so keep without debate)

- One endpoint, `GET /api/dashboard`, returns the whole page at one server instant. The page computes each age from that instant, not from the browser clock.
- Expected slots are computed in pure Python from `Slot`. SQL returns only rows that exist. No `generate_series`.
- The strip is runs on a time axis, drawn as SVG rectangles. No canvas, no DOM node for each slot.
- Uptime is `up / (up + down)`, computed on the server only. Blocked, inconclusive, and not observed are counts beside it.
- Pydantic owns the JSON shape. TypeScript types are generated from it. A test fails when the committed schema is stale.
- The web process is read-only twice: the read store has no write method, and each session has `default_transaction_read_only = on`.
- The write time of a row is `started_at + duration_ms`.
- A multi-stage Dockerfile builds `web/dist` in a Node stage. The run image has no Node. Compose service `web` publishes `127.0.0.1:55441`. In development, Vite proxies `/api`.
- The page shows its own stale state apart from a worker stall.

## Grafts

1. **One snapshot transaction (from C2 and C3).** The three reads of `read_dashboard` run in one `REPEATABLE READ READ ONLY` transaction. This removes C1's first accepted tradeoff, so the strip, the counts, and the worker line describe one database state. `ReadStore` exposes one method, `dashboard_rows(account, windows) -> DashboardRows`, that runs the three statements in that transaction. `DashboardRows` holds the three lists.
2. **A pure strip layout with a minimum width (from C3, with C2's priority).** `web/src/layoutStrip.ts` is a pure function from runs and a pixel width to rectangles. Each run that is not up gets at least 3 px. When several runs fall in one pixel column, the column shows the first mark in this order: down, not observed, inconclusive, blocked, up. Vitest covers it. This replaces C1's non-scaling stroke.
3. **The stall is the first thing seen (from C2).** When the worker state is `stalled`, the worker line has `role="alert"` and the document title starts with `STALLED`.
4. **503 before the schema exists (from C2 and C3).** If the tables do not exist, `GET /api/dashboard` answers 503 with a plain message. The web process never runs `migrate`.

## Product defaults chosen by the orchestrator

The owner can change these later.

| Question | Default | Why |
| --- | --- | --- |
| Uptime formula | `up / (up + down)` | A stalled worker must not look like a site outage. The not-observed count shows beside it. |
| Fold of several probes for one slot | C1 `fold_probes` rule | Slice 2 has one probe, so only the one-row case runs. |
| Time zone on the page | UTC, labelled "UTC" | Matches logs and SQL. |
| Stall rule | C1: newest row older than the shortest interval plus 60 s | A check takes at most 30 s. |
| Interval change or remove and re-add | Accept false "not observed" for up to 7 days | Needs a schema change, out of scope. |

## Fixed project facts

- Read `docs/design/slice-2/brief.md` for the constraints.
- Python: new module `src/saasx2x/dashboard.py`, new `src/saasx2x/web.py`, additions to `domain.py`, `verdict.py`, `store.py`, `config.py`, `cli.py`. New dependencies `fastapi` and `uvicorn`. Dev dependency `pytest-playwright`.
- Front end: `web/` at the repository root, Vite, React, TypeScript, Vitest. Commit `web/package-lock.json` and `web/openapi.json`. Do not commit `web/dist`, `web/node_modules`, or `web/src/api.gen.ts`.
- `uv run pytest` stays offline. The browser test is marked and skips when Chromium is not installed.
