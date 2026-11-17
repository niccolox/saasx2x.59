# Rationale: SaaSX2X slice 2, candidate 2

## Problem

The owner wants one page that replaces the SQL client. The page shows each active check, its last result, a 24 hour strip of slot marks, and uptime for 24 hours and 7 days. It also shows when the worker stops writing rows. A stalled worker raises no error, so the page is the only alarm in slice 2.

Four facts from slice 1 make the shape non-obvious:

- A missing row means "not observed". The database cannot list what is missing, so some code must know which slots a check should have. That rule needs one owner.
- The interval of a check can change (`target add --interval`), and no table keeps the old interval. Old rows are aligned to the old interval.
- A slot can have one row for each probe. Slice 2 has one probe, but the page must not need a rewrite for many.
- `store.py` is the only SQL module, and `domain.py` and `verdict.py` are pure. The web process must not write.

A 60 s check has 1,440 slots in a day and 10,080 in a week. A naive read sends every row of the week to Python each minute. The page must stay cheap when there are many accounts.

## Usage (caller's view)

The owner's README section:

```sh
docker compose up -d db worker web      # then open http://127.0.0.1:55441/
uv run saasx2x web                      # the same, on the host
npm --prefix web run dev                # page development on :5173, /api goes to :55441
uv run saasx2x schema > web/src/generated/dashboard.schema.json   # after a change to Dashboard
```

The one API call, and its body (shortened):

```sh
curl -s http://127.0.0.1:55441/api/dashboard
```

```json
{
  "account": "owner",
  "as_of": "2026-11-16T10:02:13Z",
  "workers": [{"probe_id": "local-1", "state": "stalled",
               "newest_row_at": "2026-11-16T09:41:07Z", "stall_after_s": 600}],
  "checks": [{
    "check_id": "…", "kind": "https", "hostname": "a.example", "port": 443, "interval_s": 300,
    "last": {"slot_start": "2026-11-16T09:40:00Z", "mark": "down",
             "reasons": ["tcp_failed"], "probes": 1},
    "strip": {"first_slot_start": "2026-11-15T10:05:00Z", "interval_s": 300,
              "marks": ["up", "up", "…", "not_observed", "not_observed", "pending"]},
    "day":  {"up": 279, "down": 3, "blocked": 0, "inconclusive": 1, "mixed": 0,
             "not_observed": 4, "expected": 287, "up_ratio": 0.98936},
    "week": {"…": "…"}
  }]
}
```

Call site 1, the route in `web.py`:

```python
@app.get("/api/dashboard")
async def get_dashboard() -> Dashboard:
    facts = await reader.dashboard_facts(current_account(settings), clock())
    return build_dashboard(facts)
```

Call site 2, a rule test in `tests/test_dashboard.py`. It needs no database:

```python
check = monitored("a.example", interval_s=300, created_at=NOW - timedelta(hours=2))
facts = check_facts(check, now=NOW, strip_tallies={slot(NOW, -3): tally(up=1)})
marks = strip_marks(facts)
assert marks[-1] is Mark.PENDING
assert marks.count(Mark.OUTSIDE) == 288 - 24
assert day_counts(facts, marks).not_observed == 22
```

Call site 3, a component. The type comes from the generator, not from a hand-written copy:

```tsx
import type { CheckPanel } from "./generated/dashboard";
export function CheckRow({ panel, asOf }: { panel: CheckPanel; asOf: string }) { … }
```

## Shape

**One endpoint, one snapshot.** `GET /api/dashboard` returns `Dashboard`, the whole page at one instant `as_of`. The page is a pure function of that value. All facts come from one `REPEATABLE READ READ ONLY` transaction, so the strip, the counts, and the worker line cannot disagree. The client never joins two responses and never uses its own clock for an age. Per `minimize-reader-load`, the client has one call and one type to learn.

**One module owns every rule that gives a number.** `dashboard.py` is pure, like `verdict.py`. It owns three rules:

1. `check_windows(check, now)` is the only definition of the expected slots. It derives three `SlotRange`s from `Slot`: the strip (slots that start in the last day, the last one is the current slot), and the counted day and week windows (complete slots that start at or after `created_at`). The slot that contains `created_at` is outside the life of the check. If the worker wrote a row for it, the strip shows the row, but no window counts it.
2. `VerdictTally.fold()` is the only place that folds probe rows. Slice 2 rule: all rows agree gives that verdict, else `MIXED`. The alert slice replaces this one body with its quorum rule.
3. `worker_line(...)` is the stall rule: no row for 2 times the shortest active interval.

Per `single source of truth`, no SQL lists a slot and no TypeScript computes a mark. The store asks `check_windows` for bounds and passes them to SQL as arrays.

**SQL bins and counts. It decides nothing.** The store sends each check's bounds and current interval. SQL uses `date_bin(interval, scheduled_at, epoch)`, which is the same floor as `Slot.containing`. A test compares the two on many instants. Rows are counted by verdict into a jsonb tally for each slot. For the week, slots with equal tallies are grouped, so 10,080 slots come back as a few `TallyBucket`s. Python then computes `not_observed = expected − observed`, and folds each bucket one time. This keeps the fold in Python and the row count small. A new `Verdict` member needs no SQL change, because the SQL never names a verdict value.

**The tally is the seam for many probes.** A `VerdictTally` is `{verdict: count}` for one slot. With one probe, each tally has one entry. With many probes, the SQL and the types stay the same, and only `fold()` changes. A rule that needs the region of each probe adds a key to the tally. That is a local change in one query and one type.

**Interval changes have a defined answer.** Bins use the current interval. After 60 s to 300 s, five old rows go into one slot. Their tally is `{up: 5}`, which folds to up. After 300 s to 60 s, one old row fills one of five new slots, and four show as not observed. That is honest: no probe checked them at the new rate.

**Ratio.** `up_ratio = up / (up + down)`. Not observed, blocked, inconclusive and mixed are outside the ratio. Each one has its own count beside it, so a gap never inflates the ratio and never hides. `MarkCounts.of` raises on `PENDING` and `OUTSIDE`, so those two can never be counted. The ratio is a computed field in Python, so the page shows a number it did not compute.

**Read only, two times over** (per `encode-lessons-in-structure`). `DashboardReader` is a separate class with one read method, so `web.py` cannot call `record_result`: pyright rejects it. Its pool opens each session with `default_transaction_read_only=on`, so Postgres rejects a write too. The web process never runs `migrate`. Before the worker migrates, the API answers 503 and the page shows why.

**Types cross the language border by generation, with two drift checks.** Pydantic makes the JSON schema (`saasx2x schema`). The schema is committed, and a pytest test fails when it differs from the model. `npm run gen` makes `dashboard.ts` from it before each build, test and typecheck. The `.ts` file is not committed, so it cannot drift from the JSON. Display tables use `satisfies Record<Mark, …>`, so a new enum value in Python fails `tsc`. The JSON fixtures of the view tests are parsed by `Dashboard.model_validate_json` in pytest.

**The strip is SVG with a down-sample that keeps bad slots.** A `ResizeObserver` gives the width. The strip has `min(slots, width / 2 px)` columns. Each column shows the first mark of a priority list (`down`, `not_observed`, `mixed`, `blocked`, `inconclusive`, `up`, …) among its slots, so one down slot stays visible at 1,440 slots. Equal neighbor columns merge into one `<rect>`. A day that is all up is one element. Mark height also differs (down is full height, up is lower), so the strip reads without color. Not observed is an outline, not a fill. This priority is display only. No number comes from it.

**Stall visibility.** The worker line is the first element on the page. A stalled state sets `role="alert"` and puts "STALLED" in the page title, so the browser tab shows it. If the poll itself fails, or the snapshot is older than 3 minutes, the page keeps the old rows, dims them, and shows when they are from. An old green page never looks current.

**Seams for later slices.** Every query filters on `account_id`, and `current_account()` is the one place that the sign-in slice changes. Each panel carries `kind`, so a new check type adds a value, not a route. The worker line is a list with one entry for each probe.

**Interface depth.** The public surface is one HTTP route, one store method (`dashboard_facts`), and one pure function (`build_dashboard`). Behind it are slot math, check life, interval changes, probe folding, the read-only session, snapshot isolation, and the down-sample. The caller of the API passes nothing and gets the whole page.

**What the design does not do.** No write. No cache or rollup table. No per-check route. No websocket. No runtime schema check in TypeScript. No history of intervals or removals.

## Synthesis decision

To be filled in by arena.

## Tradeoffs accepted

- We accept that `store.py` imports `dashboard.py` (to call `check_windows` and to build the facts types) in exchange for one owner of the slot rule and one store call for each page.
- We accept a second implementation of the slot floor in SQL (`date_bin`) in exchange for a week of data in a few rows. A parity test guards it. The expected-slot rule itself stays only in Python.
- We accept the full snapshot every 60 s, even when nothing changed, in exchange for no client state merge and no cache invalidation. Gzip makes the repeated marks small.
- We accept that the TypeScript side trusts the server type with no runtime check, in exchange for no hand-written copy of the shape. The server is this repository's own process.
- We accept `MIXED` as a mark that cannot occur in slice 2, in exchange for a total fold that decides no agreement policy before the alert slice.
- We accept that a slot that the worker skipped at check creation shows as `outside`, not as `not observed`, in exchange for no false gap each time the owner adds a target.
- We accept `started_at + duration_ms` as the write time, in exchange for no change to `check_results`. The error is the time of one INSERT.

## Alternatives considered

- **Several REST routes** (`/api/checks`, `/api/checks/{id}/strip`, `/api/worker`). Lost: a larger surface, many requests per poll, and parts from different instants. The client must join them and handle partial failure.
- **Expected slots in SQL** (a view with `generate_series` and a left join to `check_results`). Lost: it makes SQL a second owner of the slot rule and the check life, and the fold moves into SQL too. A rule change needs a migration. It is harder to test without a database.
- **Raw rows to Python** (all rows of 7 days, Python does everything). Lost: simplest SQL, but 10,080 rows for each 60 s check each minute. It does not scale to many accounts.
- **A rollup table** of counts per check and day. Lost: something must write it. The worker must not change and the web process must not write.
- **A compact string for the strip** (one letter for each slot). Lost: gzip gives the same size, and it adds a codec in both languages.
- **OpenAPI and `openapi-typescript`** in place of the model's JSON schema. Close contender. Lost because the response is one model, and the generated names from the bare schema are plain (`Dashboard`, `Mark`), not `components["schemas"]["Dashboard"]`.
- **Canvas or one `<div>` for each slot.** Canvas has no DOM for tests or screen readers. Divs give 1,440 nodes for each 60 s check.
- **A separate static server** (nginx) for the page. Lost: the brief requires one process.

## Open questions and risks

- Is `up / (up + down)` the right ratio, or should `blocked` count as up (the server answered)? The choice changes one computed field.
- Is 2 times the shortest interval the right stall threshold? At 60 s checks it alarms after 2 minutes of silence.
- A target that is removed and added again keeps its check row and `created_at`. Should the removed period show as not observed? Slice 1 keeps no removal history, so this design shows it as not observed.
- A probe that the owner renames (`SAASX2X_PROBE_ID`) stays in `probes` and shows as stalled for ever. Should the page show only probes with a row in the last 7 days?
- Inside the Compose container, `saasx2x web` binds 0.0.0.0, and the host publish binds 127.0.0.1. Is that acceptable as "bind to 127.0.0.1 only"? A test guards the publish.
- `web` runs no migration. On a new volume it answers 503 until the worker migrates. Is that start order acceptable?
- The strip SQL returns up to 1,441 rows for each 60 s check. At 50 such checks that is 72,000 small rows each minute. Is that the limit at which a per-slot rollup becomes worth it?
- The browser test needs Chromium on disk. Does "offline" allow a one-time `playwright install`?

## Next implementation step

Write `check_windows`, `VerdictTally.fold`, and `MarkCounts` in `dashboard.py` with `tests/test_dashboard.py`, because every other part takes its bounds and marks from them.
