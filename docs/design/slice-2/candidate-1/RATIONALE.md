# Rationale: SaaSX2X slice 2, candidate 1

## Problem

The owner must open one page each day and see the state of each site. The page must also show at once when the worker writes no rows. Three facts make the shape hard. First, "not observed" is a row that does not exist, so some code must know which slots a check had to fill. That rule needs one owner, and `Slot` in `domain.py` already owns the slot alignment. Second, a 60 s check has 1,440 slots in 24 hours and 10,080 in 7 days, and the page asks again each 60 s. Third, the page has two silent failures: the worker stops, or the page itself stops (a failed request, a tab that the browser slowed). Each must be visible. The fixed constraints: React with TypeScript and Vite; one FastAPI process for the API and the built page; no write to Postgres; `store.py` keeps all SQL; no change to the worker, `check_results`, or the verdict rules. Later slices add sign-in, more probes for one slot, and more check types.

## Usage (caller's view)

The owner:

```sh
docker compose up -d                 # db, worker, web
# then open http://127.0.0.1:55441/ in a browser
```

A developer of the page:

```sh
uv run saasx2x web                                # API and built page on 127.0.0.1:55441
npm --prefix web ci
npm --prefix web run dev                          # Vite on 127.0.0.1:5173, sends /api to 55441
uv run saasx2x web --openapi > web/openapi.json   # after a change to dashboard.py
```

The API is one request. It returns the whole page at one instant:

```json
{
  "generated_at": "2026-11-16T14:05:07Z",
  "refresh_after_s": 60,
  "worker": {"state": "writing", "newest_row_at": "2026-11-16T14:03:21Z", "expected_every_s": 300},
  "checks": [{
    "check_id": "6f1c1f0e-5b0a-4f0e-9d53-0a6f6f2f8c11",
    "hostname": "example.com", "port": 443, "kind": "https", "interval_s": 300,
    "last": {"slot_start": "2026-11-16T14:00:00Z", "reason": "status_ok", "verdict": "up"},
    "strip": {"start": "2026-11-15T14:05:00Z", "end": "2026-11-16T14:10:00Z", "runs": [
      {"start": "2026-11-15T14:05:00Z", "end": "2026-11-16T03:10:00Z", "reason": "status_ok", "mark": "up"},
      {"start": "2026-11-16T03:10:00Z", "end": "2026-11-16T03:25:00Z", "reason": "tcp_failed", "mark": "down"},
      {"start": "2026-11-16T03:25:00Z", "end": "2026-11-16T09:00:00Z", "reason": "status_ok", "mark": "up"},
      {"start": "2026-11-16T09:00:00Z", "end": "2026-11-16T09:05:00Z", "reason": null, "mark": "not_observed"},
      {"start": "2026-11-16T09:05:00Z", "end": "2026-11-16T14:05:00Z", "reason": "status_ok", "mark": "up"}]},
    "day":  {"up": 284, "down": 3, "blocked": 0, "inconclusive": 0, "not_observed": 1, "expected": 288, "up_ratio": 0.9895},
    "week": {"up": 2010, "down": 3, "blocked": 0, "inconclusive": 2, "not_observed": 1, "expected": 2016, "up_ratio": 0.9985}
  }]
}
```

Call site 1, the route in `web.py`:

```python
@app.get("/api/dashboard", response_model=Dashboard)
async def dashboard(account: Annotated[AccountSlug, Depends(current_account)]) -> Dashboard:
    return await read_dashboard(store, account, clock())
```

Call site 2, the page in `App.tsx`:

```tsx
const state = useDashboard();              // loading | live | stale | unreachable
const { worker, checks } = state.snapshot.dashboard;
<WorkerLine worker={worker} serverNow={serverNow} />
{checks.map((check) => <CheckRow key={check.check_id} check={check} serverNow={serverNow} />)}
// in CheckRow:  <Strip strip={check.strip} />  <Uptime counts={check.day} label="24 h" />
```

Call site 3, a test of a rule with no database:

```python
page = build_dashboard([check_made(hours_ago=30)], day=rows_without(slot_at("09:00")), week=[], now=NOW)
assert [run.mark for run in page.checks[0].strip.runs] == ["up", "not_observed", "up"]
assert page.checks[0].day.not_observed == 1
```

## Shape

**One endpoint, one snapshot.** `GET /api/dashboard` returns `Dashboard`. The page has one screen and one refresh, so one answer with one `generated_at` is the smallest interface. No request takes an id, a range, or an account.

**The Pydantic classes in `dashboard.py` own the JSON shape.** FastAPI writes the OpenAPI document from them. `web/openapi.json` is a copy in git, and a Python test fails when it is old. `openapi-typescript` writes `web/src/api.gen.ts` from it before each build and test. No person writes a TypeScript type for the API (single source of truth; derive, do not sync). `Mark` is `Verdict | Literal["not_observed"]`, so it derives from `Verdict`. Each label table in `marks.ts` is a `Record` over a generated union, so a new verdict, reason, or worker state fails `tsc` until it has a label.

**`expected_slots` in `domain.py` is the one owner of "which slots must have a row".** A slot is expected when the check existed for the whole slot, the slot has ended, and the slot is in the span. It is pure and uses `Slot`, so the worker and the dashboard share one alignment rule. Postgres never makes a slot. `ReadStore` returns only rows that exist, grouped by slot. `build_dashboard` adds "not observed" for each expected slot with no row. The number of expected slots in 7 days is arithmetic, so it needs no rows.

**The data structure follows the two access patterns.** The strip needs each slot of 24 hours in time order: `slot_evidence` returns one `SlotEvidence` for each slot with a row. The 7 day uptime needs only counts: `evidence_counts` returns, for each check, the number of slots for each kind of evidence. A 60 s check then costs a few rows for 7 days, not 10,080. Postgres counts and does not judge.

**Several probes fold at the read boundary.** `SlotEvidence.reasons` holds one `Reason` for each probe row of the slot. `fold_probes(reasons) -> Reason` in `verdict.py` is the one function that makes one judgement from them. Its result is always one of its inputs, so a judgement keeps a real reason, and `Reason` already owns its verdict. The JSON has one mark for each slot. A second probe changes no store method, no JSON field, and no component. `fold_probes` is a new function. No slice 1 rule changes, and `RULES_VERSION` stays, because no stored value depends on the fold.

**The strip is runs on a time axis, not slots.** `StripRun` is a time range with one reason. `mark` is a computed field of `reason`, so the two cannot differ, and `reason: null` has one meaning: not observed. A check that is up all day is one run for 288 slots and for 1,440 slots. `Strip.tsx` draws one SVG `<rect>` for each run, with x and width from the times. A run that is not "up" has a stroke that does not scale, so one down slot of 60 s is at least 2 px wide. "down" is drawn last. A part of the axis with no run means that the check did not exist then.

**The uptime has one formula, on the server.** `SlotCounts` has five disjoint counts of expected slots. `up_ratio` is a computed field: `up / (up + down)`. "not observed" has its own count and is in no ratio. The page formats the ratio and always shows the "not observed" count beside it.

**Both silent failures have a state.** `WorkerStatus.state` is `idle`, `waiting`, `writing`, or `stalled`. The rule is pure and on the server: the newest row is late when its age is more than the shortest interval plus 60 s. `useDashboard` gives `live` or `stale` for the page itself, and asks at once when the tab becomes visible. The page computes each "ago" text from `generated_at` and the monotonic time since the answer came, so the clock of the browser does not matter.

**"Read only" is a property of the connection.** `ReadStore` has no write method, and each of its connections has `default_transaction_read_only = on`. A later edit cannot add a write that works. The `web` command never opens `Store`.

**Interface depth.** The browser sees one URL. `web.py` sees one function, `read_dashboard`. Behind it are three statements, the slot arithmetic, the probe fold, the run merge, the counts, and the stall rule. `ReadStore` exposes three reads to one caller. That caller is the module that owns the page rules, as `worker.due_checks` does for the worker. What stays visible to the page: the time axis of a strip and the five counts. It needs both to draw.

**Build and serve.** `web/` is a Vite project. `npm run build` writes `web/dist`. `create_app` serves that folder at `/`, found by the same path rule as `MIGRATIONS_DIR`. The Dockerfile builds the page in a Node stage and copies `web/dist` into the Python image, which has no Node. In development, Vite sends `/api` to port 55441, so the page has one origin in each mode and the server has no CORS rule. With no built page, the API works and `/` returns 503 with the build command, so Python tests need no Node.

**What this slice does not do.** No write, no sign-in, no push channel, no cache, no migration, no router, no state library, no CSS framework, no detail view of one result.

## Synthesis decision

*Arena fills this in.*

## Tradeoffs accepted

- We accept three statements with no shared transaction in exchange for a store that knows no page rule. A row that arrives between two statements can make the 7 day count differ from the strip by one slot until the next refresh.
- We accept two store reads with different shapes (slots for 24 hours, counts for 7 days) in exchange for a 7 day uptime that costs a few rows for each check.
- We accept that the uptime does not count the open slot and the slot in which the check was made, while the strip shows a row in each. In exchange, the total of an uptime depends only on `created_at`, the interval, and the time, and it does not change inside a slot.
- We accept that a worker stall shows after one interval plus 60 s, not at once. A shorter time gives a false stall for each slow check.
- We accept `web/openapi.json` in git, with a command to refresh it, in exchange for a Python test that needs no Node and an API diff in each review.
- We accept no check of the JSON in the browser. The page and the API ship in one image. A tab that is open across a deploy can read a new shape with old code until the owner loads the page again.
- We accept frozen dataclasses, not Pydantic models, for the five store read types. Postgres already made the values valid, and one request can read 30,000 of them.
- We accept `SAASX2X_WEB_HOST=0.0.0.0` inside the container. The Compose port map binds the host side to 127.0.0.1, and the default on the host is 127.0.0.1.
- We accept a text `<title>` on each run as the only hover detail. It needs no state and no measurement.

## Alternatives considered

- **Postgres owns the slots: a view or a query with `generate_series`, a left join, and counts in SQL.** It hides the most behind the smallest Python code: one statement, one snapshot. It lost because SQL must then repeat the alignment of `Slot`, and the fold of probes cannot use `Reason.verdict`. A view cannot take the time as an argument, so a test cannot fix the clock without a function. Each rule case needs a database. Postgres also makes up to 10,080 rows for each 60 s check on each refresh.
- **One JSON object for each slot, and the page computes runs and uptime.** The server is simpler. It lost because the interface is wide: up to 1,440 objects for each check each minute, and the uptime formula and the "not observed" count move to TypeScript as a second owner. The page must merge slots to draw a visible mark, so the run logic exists in each design. The question is only which side owns it.
- **Several endpoints: a list of checks, a strip for each check, a worker status.** Each is small. It lost because the page must then join N + 2 answers with different clocks and show a state for each partial failure. The caller does the work that one snapshot hides.
- **Read all rows of 7 days into Python (one store read, no counts).** The store is the smallest. It lost on the main access pattern: 10,080 rows for each 60 s check each minute, to change a ratio in its fourth digit.
- **Hand-written TypeScript types, or a Zod schema, for the API.** It hides nothing and adds a second list of fields and enum values. It lost to the generated types.
- **Canvas, or one DOM element for each slot.** Canvas has no hover text, no accessible names, and no test in jsdom. One element for each slot gives 1,440 nodes for each check, each less than 1 px wide. Both lost to one SVG rectangle for each run.
- **Node Playwright for the browser check.** It lost to `pytest-playwright`: the Python test uses the scratch database fixture, writes rows through `Store`, and moves the server clock. A Node test needs a seed command and a second process manager.

## Open questions and risks

- Is `up / (up + down)` the right uptime, with "blocked", "inconclusive" and "not observed" as counts beside it? The other choice is `up / expected`, which makes a stalled worker look like an outage of the site.
- Is the fold rule right for two probes that disagree: the most frequent verdict wins, and a tie goes to up, then blocked, then inconclusive, then down? It follows "one failed probe is not an outage". Slice 2 has one probe, so only the rule for one row runs.
- The schema keeps no history of the interval or of a removal. `target add --interval` on a check that exists changes `interval_s`, and `target remove` then `target add` leaves a gap. For both, the dashboard shows "not observed" for slots that were never due, for up to 7 days. Should a later slice make a new check row for a new interval and record each removal period? This slice cannot fix it without a schema change.
- Should the times on the page be UTC, as in the logs and in SQL, or the local time of the browser? The sketch uses UTC with the label "UTC".
- Is the stall rule right for checks with different intervals? The rule compares the newest row of any check with the shortest interval. With a 60 s check and a 300 s check, the worker shows as stalled when the 60 s check writes no row for 2 minutes, also when the 300 s check still writes. A healthy worker writes a row in each slot, because a check ends in 30 s. A worker that writes rows for only a part of its checks shows as "writing", and the "not observed" marks of each row show the fault.
- `ALLOWED_HOSTS` is `127.0.0.1` and `localhost`. Does the owner open the page through a different name, for example over a tunnel?
- The versions in `web/package.json` are major ranges. The first `npm install` fixes them in `package-lock.json`. Does the owner want a different Node version than 24 in the build stage?

## Next implementation step

Write `expected_slots`, `fold_probes`, and `build_dashboard` with `tests/test_dashboard.py`, because each other part (the store reads, the route, the page) only moves data to or from that pure function.
