# PLAN v3 — hardening + astro routing

2026-11-21 · follows PLAN.md (v2 complete: 142 tests, 47 endpoints, 11 tools)
Basis: audit run against the live app, not assumptions.

## Audit findings (measured)

| # | Finding | Evidence |
|---|---|---|
| 1 | An unrouted turn closes `runs.status = 'ok'` with `tool_count = 0`, so `ok_rate` reports 100% for turns that answered nothing | `no_route run: status=ok source=none tools=0` → `ok_rate=1.0` |
| 2 | The pipe has 7 intents and **astro is not one of them**; the headline feature is unreachable from chat | `pipe intents: [math_solve, math_calc, project_create, project_verify, plan, news, search]` |
| 3 | `recalls_24h` sums every pattern's lifetime `uses` | `SELECT SUM(uses) FROM patterns WHERE last_used_at IS NOT NULL` |
| 4 | Knowledge has no pipe intent; `ค้นหา` always goes to web search | `search` plan hardcodes `scope: web` |
| 5 | Brave web search still blocked (no reference contract) | `.outworld/plan.md` deviation 1 |

## Tasks

### V1 — Honest stats
**Files:** `backend/app/learning.py`, `backend/tests/test_learning.py`
**Build:** `ok_rate` counts only runs that actually ran (`intent_source <> 'none'`); add `unrouted`
count; `recalls_24h` counts patterns whose `last_used_at` is within 24 hours.
**Verify:** `cd backend; uv run pytest -q tests/test_learning.py`
**Done:** an unrouted turn leaves `ok_rate` at 0 for a database holding only that turn; `recalls_24h`
is 0 for a pattern last used yesterday.

### V2 — Astro in the pipe
**Files:** `data/intent.yaml`, `data/plan_cheat.yaml`, `backend/app/pipe.py`,
`backend/tests/test_pipe.py`, `SPEC.md`
**Build:** three deterministic transforms `extract_date`, `extract_time`, `extract_location`;
one rule `astro` (priority 110) requiring a date **and** (trigger or clock time); one plan that calls
`astro` with the three slots; `_context` renders a `summary` from the four-system payload.
**Verify:** `cd backend; uv run pytest -q tests/test_pipe.py`
**Done:**
```text
ดูดวง 1992-08-08 16:49 ยะลา   -> intent=astro, answer contains "Sun", "Asc", day pillar
17/08/2538 14:30 กรุงเทพ      -> intent=astro, local 1995-08-17
9.8-9.11=?                    -> intent=math_calc (unchanged)
2026-12-01                    -> no_route (a date alone is not a chart request)
```

### V3 — Knowledge intent
**Files:** `data/intent.yaml`, `data/plan_cheat.yaml`, `backend/tests/test_pipe.py`
**Build:** rule `note_search` (priority 70) for `ค้นโน้ต|โน้ต|note` routing to
`search(scope=knowledge)`; generic `ค้นหา` keeps going to web.
**Verify:** `cd backend; uv run pytest -q tests/test_pipe.py`
**Done:** `ค้นโน้ต sympy` → `note_search` with `scope=knowledge`; `ค้นหา sympy` unchanged.

### V4 — UI gaps that block real use
**Files:** `frontend/src/routes/projects/+page.svelte`,
`frontend/src/routes/projects/[id]/+page.svelte`, `frontend/src/routes/+layout.svelte`
**Build:** delete project (with confirm), delete chat from the list pane row, command run with a
parameter prompt instead of an empty object.
**Verify:** `cd frontend; bun run check; bun run build`
**Done:** 0 errors; a project can be created and deleted from the UI without touching curl.

### V5 — Docs and acceptance
**Files:** `SPEC.md` (§14.2, §14.3, §5.10, §10), `.outworld/brief.md` (A35–A39),
`.outworld/plan.md`
**Build:** new rules/transforms documented, new acceptance ids recorded with the commands that prove
them.
**Verify:** `grep -n "A3[5-9]" .outworld/brief.md SPEC.md`
**Done:** every new behaviour has an id and a section.

### V6 — Blocked, not skipped
**Brave web search.** Needs an API contract in `references/`; the execution rule forbids guessing or
web research mid-run. Until then `search(scope="web")` returns `web_search_not_configured`, which is
tested. To unblock: add `references/websearch.md` with endpoint, auth header and response shape, then
implement `app/websearch.py` behind the existing seam.

## Order

```text
V1 (stats)  ->  V2 (astro pipe)  ->  V3 (knowledge)  ->  V5 (docs)
                                          \-> V4 (UI)  (independent)
V6 waits for a reference.
```

## Verify matrix

| Task | Command | Acceptance |
|---|---|---|
| V1 | `pytest -q tests/test_learning.py` | A35 |
| V2 | `pytest -q tests/test_pipe.py` | A36, A37 |
| V3 | `pytest -q tests/test_pipe.py` | A38 |
| V4 | `bun run check && bun run build` | A39 |
| V5 | grep | — |
| all | `pytest -q` + `ruff check .` + `bun run check` | no regressions |
