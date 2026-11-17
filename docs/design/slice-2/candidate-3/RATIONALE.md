# Slice 2, candidate 3: one board, one pure owner of "expected"

## Problem

The owner wants one screen that shows each active check and shows at once when the worker stops writing rows. A stalled worker raises no error, so the screen itself must carry the signal. The page must read `check_results` and must not write it. Slice 1 fixed these facts. `Slot` owns epoch alignment. A missing row means "not observed". A slot before the check existed is outside the check's life. `check_results` has no write-time column and must not change. `store.py` is the only module with SQL. Later slices add accounts, many probes, and more check types, so every read already carries `account_id` and `probe_id`. Three details make the shape non-obvious. The open slot has no row by design, because a check is due at an offset inside its slot. A strip of 1,440 slots is under 1 px per slot. A dead web process looks like a calm page unless the page watches itself.

## Usage (caller's view)

The owner starts the stack and opens one URL.

```sh
docker compose up -d --build        # db, worker, web
open http://127.0.0.1:55441/        # the page; refreshes each 60 s
```

A developer runs the two halves apart.

```sh
uv run saasx2x web                  # JSON + built page on 127.0.0.1:55441
cd web && npm run dev               # Vite on 127.0.0.1:5173, proxies /api
cd web && npm run gen               # openapi.json + src/api.gen.ts from the Python types
```

Call site 1, Python. A test or a script builds the whole page data from facts and a clock.

```python
facts = await read_store.status_facts(account, since=as_of - WINDOW_7D, as_of=as_of)
board = build_board(facts, as_of)           # pure; no clock, no I/O
board.worker.state                          # WorkerState.STALLED
board.checks[0].tally_24h.uptime            # 0.9965, or None
```

Call site 2, TypeScript. A component reads a type that Python generated.

```tsx
const { state, link } = useBoard();                       // last good board + page link state
state.board?.checks.map(c => <CheckRow check={c} asOfIso={state.board.as_of} ... />);
// c.strip.runs: [{mark: "up", count: 812}, {mark: "down", count: 3}, {mark: "up", count: 420}]
```

Call site 3, the JSON of `GET /api/status`, shortened.

```json
{"as_of": "2026-11-16T14:05:03Z", "window_start": "2026-11-15T14:05:03Z",
 "worker": {"state": "fresh", "newest_row_at": "2026-11-16T14:03:41Z", "silent_s": 82, "expected_every_s": 300},
 "checks": [{"check_id": "…", "hostname": "example.com", "port": 443, "interval_s": 300,
   "last": {"slot_start": "2026-11-16T14:00:00Z", "probe_id": "local-1", "verdict": "up",
            "reason": "status_ok", "http_status": 200, "duration_ms": 212.4},
   "strip": {"first_slot": "2026-11-15T14:05:00Z", "interval_s": 300, "lead": 0, "slot_count": 287,
             "runs": [{"mark": "up", "count": 200}, {"mark": "down", "count": 2}, {"mark": "up", "count": 85}]},
   "tally_24h": {"up": 285, "down": 2, "blocked": 0, "inconclusive": 0, "not_observed": 0, "uptime": 0.993},
   "tally_7d": {"…": "…"}}]}
```

## Shape

**Data structures first.** `StatusBoard` is the only structure that crosses the wire. It holds one `Worker` and a tuple of `CheckStatus`. Each `CheckStatus` holds the `last` result, a `Strip`, and two `Tally` values. The Pydantic types are the domain and the JSON shape. There is no second DTO layer. `SlotRow` carries `probe_id`, so many probes need no change to the reader.

**One endpoint.** `GET /api/status` returns everything the page shows, built from one read transaction. The worker line and the strips then describe the same database state. The page makes one request each 60 s and has no join logic. A fetch for each check would show a green strip beside a stalled worker. `/healthz` is the only other route.

**One owner of "expected".** `expected_slots` in `status.py` is the only definition of which slots a check owed. It returns a `SlotRange`: a first `Slot` and a count. The owed slots are always one consecutive run, so a range is enough, and no per-slot object exists. This avoids 10,080 Pydantic `Slot` validations for each check for 7 d. The rule has two parts. A slot before the first full slot after `created_at` is outside the life of the check. The open slot is owed only when it already has a row. This is why the page never shows a false "not observed" for the slot in progress. SQL returns only rows that exist (per boundary-discipline: SQL stores and filters, and does not define meaning). "Not observed" is `owed.count - observed.count`, computed once in Python.

**Probe fold now, not later.** `fold_probes(first, *rest)` takes the verdicts of one slot and returns one `Mark`. The first-argument form makes an empty slot impossible in the type, so "no row" cannot reach the fold (per encode-lessons-in-structure). Today each slot has one verdict, so the function is `Mark.of`. A second probe changes the body of this one function and nothing else: `SlotRow`, the SQL, the wire shape, and the page already hold a `probe_id`.

**Run-length strips.** The wire carries `runs: [{mark, count}]`. A quiet day is one run. A strip is O(changes) in JSON and in DOM. The strip also carries `lead`, the grid slots before the check existed. The page draws on a time axis, so a 60 s row and a 300 s row line up. `layoutStrip` (pure TypeScript) turns runs into pixel rectangles. It gives each non-up mark at least 3 px and draws it on top, so one failed minute in 24 h stays visible. It merges neighbors so a flapping strip gives at most one rect for each pixel column. The page uses SVG: real `<title>` hover text, a DOM that a test can read, and no per-slot node. Marks differ by height and hatch as well as color.

**One owner of every ratio and every state.** `Tally.uptime` is `up / (up + down)`, computed in Python only. Blocked, inconclusive, and not observed give no evidence either way. They stay out of the ratio and show as counts. TypeScript only rounds. `judge_worker` decides `idle`, `fresh`, `late`, `stalled` from the age of the newest row and the shortest active interval. The page prints the state and never recomputes it. Labels are `Record<Reason, string>` over the generated union, so a new `Reason` in Python fails `tsc` until a label exists (per type-system-discipline; no hand-synced list).

**The page watches itself.** `useBoard` keeps the last good board, records a monotonic time at each good response, and shows its own "data is old" banner after 150 s with no good response. It keeps the board on screen, dimmed. A dead web process and a stalled worker are then two different, visible messages. Ages use the server's `as_of`, so a wrong browser clock changes nothing.

**Where the stall signal comes from.** `check_results` has no write-time column. `NewestRow.written_at` is `started_at + duration_ms`, which is the write time to within milliseconds, because the worker writes right after the check ends. Migration 0002 adds one index, `(account_id, started_at DESC)`, so "newest row" is an index read. With no row at all, silence counts from the creation of the oldest active check, so a worker that never wrote a row also turns late and then stalled.

**TypeScript types with no hand copy.** `status.py` types define the response. `web.openapi_json()` prints the OpenAPI document. `openapi-typescript` writes `src/api.gen.ts`. Both outputs are committed. A Python test fails when the committed `openapi.json` is stale. `npm run gen:check` fails when `api.gen.ts` is stale. `src/api.ts` is the only importer of the generated file.

**Read-only in three layers.** The app depends on a one-method protocol (`StatusReader`). `ReadStore` has no write method. Its sessions start with `default_transaction_read_only=on` and a 10 s statement timeout. A test proves that a write raises. A `TrustedHostMiddleware` allow-list (`127.0.0.1`, `localhost`) blocks DNS rebinding from another site, because the service has no sign-in.

**Interface depth.** The public surface is small. Python: `build_board(facts, as_of)`, `ReadStore.status_facts(account, since, as_of)`, `create_app(reader, account=...)`. TypeScript: `useBoard()` and one `StatusBoard` type. Behind `build_board` sit the expected-slot rule, the probe fold, the run-length encoding, both tallies, the worker judgment, and the sort. Behind `status_facts` sit the snapshot transaction, three statements, and the grouping by check. A caller coordinates no stages. The call chain for one request is three files: `web.py`, `store.py`, `status.py`.

**Build and serve.** A two-stage Dockerfile builds `web/dist` in a Node stage and copies it into the Python image. The run image has no Node. FastAPI mounts `web/dist` after the API routes. In development, Vite on :5173 proxies `/api` to :55441. `web` and `worker` share one image and differ by command. The web process does not migrate. Before the worker migrates, `/api/status` answers 503 with a plain message.

**Deliberately not done.** No write route. No sign-in. No cache. No push channel. No table or view for rollups. No change to `check_results`, the worker, or verdict rules. No per-probe breakdown on the page.

## Synthesis decision

To fill in by arena.

## Tradeoffs accepted

- We accept that the Pydantic read model is also the wire shape, in exchange for no second set of field lists. A field rename breaks the page. The snapshot test and `tsc` catch it at build time.
- We accept that Python folds 7 d of narrow rows (about 10,000 rows for each 60 s check), in exchange for one owner of "expected" and of the probe fold. SQL with `generate_series` would move less data and own the rule twice.
- We accept `up / (up + down)` as uptime, in exchange for an honest ratio that never counts a missing or doubtful slot as up. A site that Cloudflare always blocks shows "n/a" and a blocked count. This can look odd, and it is deliberate.
- We accept that the strip stops at the last closed slot (or a slot with a row). The right edge can lag by one interval, in exchange for no false "not observed" for the slot in progress.
- We accept that "last result" is the newest single row, not a fold over probes. One probe exists today. A fold is a later change in one function.
- We accept `started_at + duration_ms` as the write time, because the schema cannot change.
- We accept 60 s polling and no push channel. A push channel adds state that can itself stall silently.
- We accept session-level read-only, not a separate Postgres role. A role needs setup outside the allowed migrations.
- We accept that the worker image carries `web/dist` (a few hundred KB), in exchange for one Dockerfile and one image.
- We accept a Playwright dependency with a one-time Chromium download. The default `uv run pytest` stays offline.

## Alternatives considered

- **Several endpoints** (`/api/targets`, `/api/targets/{id}/strip`, `/api/worker`). Rejected. The caller joins the answers. The reads are not one snapshot, so a strip and the worker line can disagree. It adds N+1 requests and more wire types. The surface is bigger and hides less.
- **Compute "expected" and "not observed" in SQL** (`generate_series` joined to `check_results`). Rejected. It moves the epoch rule, the life-of-check rule, and the probe fold into SQL, next to the same rules in `Slot`. Two owners drift. Its one gain, less data, does not matter at owner scale.
- **A dense array of 1,440 marks for each check.** Rejected. The JSON is larger, the DOM is larger, and the page still needs a layout step to keep a one-slot failure visible. Run-length form is the smaller interface for the same job.
- **Canvas, or one `<div>` for each slot.** Rejected. Canvas has no per-mark hover text and no DOM for a test. One `<div>` for each slot is 29,000 nodes for 20 checks, with each slot under 1 px.
- **Hand-written TypeScript types, or zod schemas.** Rejected. They copy the field list. This is the drift that the brief names.
- **A rollup table or a materialized view of slot marks.** Rejected. It is a second copy of state, and a refresh job is one more thing that can stall silently. The brief allows an index or a view only when a query needs it. The queries run on the primary key.
- **Server-sent events or WebSocket for live updates.** Rejected. A stalled push channel looks like a calm page. Polling with a monotonic "last good response" is simple and self-checking.
- **Mark as a re-use of `Verdict`.** Rejected. `not_observed` is not a verdict, and no worker may write it. `Mark` is a separate enum, and a test keeps it in step with `Verdict`.

## Open questions and risks

- Is `up / (up + down)` the uptime that the owner wants? Should blocked slots count against it?
- When two probes disagree on a slot, is "any up wins" the right default? Is a quorum better?
- Are the stall limits right (late after 1 interval + 40 s, stalled after 2 intervals + 40 s)? With one 300 s check, "stalled" shows after about 11 min.
- The owner can change a check's interval. Old rows then sit on the old grid, and the new grid shows many "not observed" slots for the past. Can `checks` get an `interval_changed_at` column later? A migration cannot add it in this slice.
- A target that the owner removes and adds again keeps its check row and its `created_at`. The removed period then looks like "not observed". Should the CLI record the re-add time?
- Does the owner want one worker line per probe once a second probe exists? The `Worker` record can gain a `probes` list without breaking the page.
- Is 7 d of narrow rows fast enough at, say, 50 checks of 60 s (about 500,000 rows)? We plan to measure. If it fails, the 7 d tally moves to a SQL aggregate over a per-slot fold, and the rule moves to one place only.
- Does the owner accept `started_at + duration_ms` as the write time?
- Should the Compose `web` service use a separate read-only Postgres role, set up in an init script?
- Playwright needs a Chromium download once. Does that fit the "offline" rule for tests, or should the browser check run in a separate CI job?

## Next implementation step

Write `status.py` (`SlotRange`, `expected_slots`, `fold_probes`, `run_length`, `build_check_status`, `judge_worker`, `build_board`) and `tests/test_status.py` first, because the page data and the TypeScript types both come from them.
