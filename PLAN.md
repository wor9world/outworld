# PLAN — Outworld Workbench

2026-11-21 · implements `SPEC.md` (34 acceptance ids, 47 endpoints, 11 tables + 2 FTS, 11 tools,
16 components, 9 pages)
Execution rule: one task at a time, run its verify command, quote the output, commit, then next.

---

## 0. Order and dependencies

```text
T0  skeleton + deps ──┬─ T1 config/db/health ──┬─ T2 projects+chats ── T3 chat turn (no LLM)
                      │                        ├─ T4 knowledge + FTS
                      │                        ├─ T5 fs ── T6 shell+approval ── T7 code
                      │                        ├─ T8 search ── T13b web adapter
                      │                        ├─ T9 calc ── T10 z3 ── T11 astro
                      │                        ├─ T12 project tool ── T13 planner+pipe
                      │                        └─ T16 learning (needs T3 + T13)
                      └─ T14 LLM + SSE ── T15 agent loop
T17 frontend scaffold ── T18 shell/theme ── T19 chat UI ── T20 remaining pages ── T21 backup+audit
```

Anything may be reordered inside a branch. `T3` and `T13` must exist before `T16`; `T14` before `T15`.

Progress is tracked in `.outworld/plan.md` as a checklist of task ids with the verify output quoted.

---

## 1. Task list

### T0 — Skeleton and dependencies
**Files:** `.gitignore`, `README.md`, `backend/pyproject.toml`, `backend/.env.example`,
`frontend/package.json`, `frontend/.env.example`, `backend/app/__init__.py`, `backend/tools/__init__.py`
**Build:** create the directory tree from SPEC §1; `uv sync` in `backend`; `bun install` in `frontend`.
**Verify:**
```sh
cd backend;  uv sync; uv run python -c "import fastapi, sympy, z3, swisseph, yaml; print('deps ok')"
cd frontend; bun install; bun run check
```
**Done:** `deps ok` printed (proves `pysweph` compiled on 3.15), `bun run check` exits 0 on the
untouched skeleton.

### T1 — Config, database, health
**Files:** `backend/app/config.py`, `backend/app/db.py`, `backend/app/api/health.py`,
`backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`
**Build:** settings loader with the six `OUTWORLD_*` vars; DDL for all 11 tables + 2 FTS + triggers in
one `SCHEMA` string; `GET /api/health`; CORS from `OUTWORLD_CORS`; lifespan opens the DB.
**Verify:** `cd backend; uv run pytest -q tests/test_health.py` → `9 passed`
**Done:** DB file created on first start; `health` returns `tools` (11 ids), `llm:"disabled"`,
`schema:1`; deleting the DB recreates it.

### T2 — Projects and chats CRUD
**Files:** `app/api/projects.py`, `app/api/chats.py`, `tests/test_projects.py`, `tests/test_chats.py`
**Build:** endpoints 4–14; root_path validated under workspace; cascade deletes proven.
**Verify:** `cd backend; uv run pytest -q tests/test_projects.py tests/test_chats.py`
**Done:** create → restart → still there (A5); delete project removes its chats (A5).

### T3 — Chat turn without LLM
**Files:** `app/runner.py`, `app/api/chats.py`, `tests/test_chat_turn.py`, `tests/test_chat_paging.py`
**Build:** `runner.run_chat()` steps 0–6 without a provider; `runs` row opened and closed; message
paging `?limit=&before=` with `has_more`.
**Verify:** `cd backend; uv run pytest -q tests/test_chat_turn.py tests/test_chat_paging.py`
**Done:** `POST /chat/{id}` → `201 {assistant_message:null, warnings:["llm_disabled"]}`; two messages
persisted; `runs` row `intent_source:"none"` (A6); paging returns oldest-first with `has_more` (A6).

### T4 — Knowledge + FTS5
**Files:** `app/api/knowledge.py`, `tools/knowledge.py`, `tests/test_knowledge_fts.py`
**Build:** endpoints 17–21; triggers; `bm25` ordering; `<mark>` snippets; `knowledge` tool.
**Verify:** `cd backend; uv run pytest -q tests/test_knowledge_fts.py`
**Done:** insert → search by a word in the body → hit; edit → old word misses, new word hits (A7);
Thai text matches (unicode61).

### T5 — `fs` tool
**Files:** `app/sandbox.py`, `app/api/tools.py`, `tools/fs.py`, `tests/test_tools_fs.py`
**Build:** path guard, read/write/list/patch, audit row, dispatch endpoint 3.
**Verify:** `cd backend; uv run pytest -q tests/test_tools_fs.py`
**Done:** `../../AGENTS.md` and `C:\Windows\...` → 403 and no write; patch with 0 or 2 matches → 409 (A8).

### T6 — `shell` + approvals
**Files:** `app/sandbox.py` (approval), `tools/shell.py`, `tests/test_tools_shell.py`
**Build:** allowlist prefix match, chain detection, approval mint (`409`), `POST /approvals/{token}`
single-use execution, `sandbox.wait()` poll for the SSE path, audit for `denied`/`timeout`.
**Verify:** `cd backend; uv run pytest -q tests/test_tools_shell.py`
**Done:** `echo hi` runs; `rm -rf x` → 409 + token; approve → runs once, second approve → 410;
`a && b` always needs approval (A9).

### T7 — `code` tool
**Files:** `tools/code.py`, `tests/test_tools_code.py`
**Build:** python via `sys.executable -I -c`, javascript via `bun -e`, temp dir, timeout kill.
**Verify:** `cd backend; uv run pytest -q tests/test_tools_code.py`
**Done:** `print(6*7)` → `42`; infinite loop → `status:"timeout"` within `code_timeout_s + 2`; no `bun`
→ `unsupported_language` (A10).

### T8 — `search` tool (local)
**Files:** `tools/search.py`, `app/api/tools.py`, `tests/test_tools_search.py`
**Build:** knowledge FTS branch, workspace scan with skips and 1 MiB cap, `limit`.
**Verify:** `cd backend; uv run pytest -q tests/test_tools_search.py`
**Done:** a Thai word in `workspace/notes.md` is found; `node_modules` never scanned (A14).

### T9 — `calc` tool
**Files:** `tools/calc.py`, `tests/test_calc_z3.py`
**Build:** `parse_expr` + `rationalize`; `op:"eval"`; `op:"solve"` = solve → evalf → real filter →
grid scan → dedupe.
**Verify:** `cd backend; uv run pytest -q tests/test_calc_z3.py`
**Done:** `9.8-9.11` → `exact:"69/100"`; `3**x - x**9` → `["27", "1.150824821..."]`; `simplify(
sin(x)**2+cos(x)**2)` → `1` (A11, A26, A27).

### T10 — `z3` tool
**Files:** `tools/z3.py`, `tests/test_calc_z3.py` (same file, second class)
**Build:** `parse_smt2_string` → `Solver` → `check()`; model to strings.
**Verify:** `cd backend; uv run pytest -q tests/test_calc_z3.py`
**Done:** `(assert false)` → `unsat`; `(declare-const x Int)(assert (> x 5))` → `sat` + model (A12).

### T11 — `astro` (copy) + fixtures
**Files:** `backend/tools/astro.py` (copied content), `backend/data/assets/*.se1`,
`backend/tools/registry.py`, `app/api/tools.py`, `tests/test_astro_fixtures.py`,
`tests/fixtures/astro_*.json`
**Build:** copy the file and the four `.se1` assets byte-for-byte; write `registry.py`; call
`set_ephe_path` in lifespan; generated fixtures (commit them).
**Verify:**
```sh
cd backend; uv run python -m tools.astro            # 4-system JSON, exit 0
cd backend; uv run pytest -q tests/test_astro_fixtures.py
```
**Done:** J2000 Sun `280.3689 ± 0.01`; Lahiri ayanamsa `≈ 23.85°`; `17/08/2538` → 1995-08-17;
`cusps[1..12]` present (A13, A13b).

### T12 — `project` tool (scaffold + verify)
**Files:** `tools/project.py`, `tests/test_project_tool.py`
**Build:** three templates; refuse non-empty target; verify dispatches `shell` checks.
**Verify:** `cd backend; uv run pytest -q tests/test_project_tool.py`
**Done:** `สร้างโปรเจค` path creates `workspace/<name>/` with the expected files; second run on the same
name → `target_exists`; verify returns `checks[]` with `ok` (A29, A30).

### T13 — Planner + pipe
**Files:** `data/intent.yaml`, `data/plan_cheat.yaml`, `app/pipe.py`, `app/api/pipe.py`,
`tools/planner.py`, `tests/test_pipe.py`
**Build:** YAML loader with validation (rejects a rule with no conditions, a plan with an unknown tool
or slot); matcher (priority, tie = file order, confidence, `explain`); slot transforms; executor that
runs steps through the tool layer; `answer` renderer.
**Verify:**
```sh
cd backend; uv run pytest -q tests/test_pipe.py
curl -s 127.0.0.1:8000/api/pipe/route -H "content-type: application/json" -d '{"message":"9.8-9.11=?"}'
```
**Done:** every row of SPEC §14.6 passes; `/pipe/route` executes nothing and writes no `tool_calls`;
`/pipe/reload` picks up an edited YAML without a restart (A26–A28, A31–A34).

### T14 — LLM providers + SSE
**Files:** `app/llm.py`, `app/websearch.py`, `app/api/providers.py`, `app/api/chats.py`
**Build:** provider CRUD (key never returned, empty key keeps old), `/providers/{id}/test`, SSE writer
with the seven events, `route` event, keepalive.
**Verify:** `cd backend; uv run pytest -q tests/test_providers.py tests/test_agent_no_llm.py`
**Done:** health flips `disabled → enabled`; `/chat/{id}/stream` with no provider → 409 before the
stream; provider test reports latency (A15, A16).

### T15 — Agent loop
**Files:** `app/agent.py`, `app/runner.py`
**Build:** system prompt = project instructions + tool catalogue + recall block; ≤ 8 iterations; tool
execution in order with `run_id`; malformed args tolerated.
**Verify:** `cd backend; uv run pytest -q tests/test_agent_no_llm.py`
**Done:** a fake provider that requests one tool call produces `delta` → `tool` → `tool_result` →
`done`; iteration cap returns `error:"max_iterations"` (A16).

### T16 — Learning
**Files:** `app/learning.py`, `app/api/learning.py`, `tools/memory.py`, `tests/test_learning.py`,
`tests/test_patterns.py`
**Build:** run open/close, distillation (ok + ≥ 2 tools), upsert on (intent, tool_chain), recall query,
`uses` bump for injected patterns, feedback counters, promote to project instructions.
**Verify:** `cd backend; uv run pytest -q tests/test_learning.py tests/test_patterns.py`
**Done:** A20–A25; a repeated request yields exactly one pattern row; `bad` lowers the rate; disabled
is excluded from the next recall.

### T17 — Frontend scaffold
**Files:** `frontend/vite.config.ts`, `tsconfig.json`, `src/app.html`, `src/app.css`,
`src/routes/+layout.svelte`, `src/lib/api.ts`, `types.ts`, `stream.ts`, `theme.ts`,
`components/AppShell.svelte`, `Rail.svelte`, `ListPane.svelte`, `ThemeToggle.svelte`
**Build:** adapter-bun config, `#lib` imports, Tailwind import, four-region shell, theme apply.
**Verify:** `cd frontend; bun run check; bun run build`
**Done:** shell renders at `/` with a skeleton; zero type errors; `@custom-variant` verified against
the installed tailwindcss or the `[data-theme]` fallback used (A1, A3).

### T18 — Shared UI pieces
**Files:** `components/Composer.svelte`, `MessageBubble.svelte`, `ChatView.svelte`, `StepLog.svelte`,
`EmptyState.svelte`, `ApprovalModal.svelte`, `RouteChip.svelte`, `StatsBar.svelte`,
`PatternCard.svelte`
**Build:** each as specified in SPEC §9.3, runes only, utility classes only.
**Verify:** `cd frontend; bun run check`
**Done:** every component compiles; no `export let`, no `on:click`, no `<style>` block (grep check).

### T19 — Chat page + streaming
**Files:** `src/routes/chat/[id]/+page.svelte`, `src/routes/+page.svelte`
**Build:** load chat, render transcript, send via `streamChat`, route chip, step log, abort on leave.
**Verify:** `cd frontend; bun run check` + manual: send `9.8-9.11=?` → answer `0.69` with a
`math_calc` route chip and no provider configured.
**Done:** stream renders deltas, tool rows appear, abort stops generation (A6, A26).

### T20 — Remaining pages
**Files:** `routes/projects/+page.svelte`, `projects/[id]/+page.svelte`, `knowledge/+page.svelte`,
`tools/+page.svelte`, `settings/+page.svelte`, `learning/+page.svelte`, `pipe/+page.svelte`
**Build:** CRUD screens, command rows inside the project page, tool bench, provider form, learning
stats + pattern actions, pipe inspector.
**Verify:** `cd frontend; bun run check; bun run build` + manual walk of the 7 flows in SPEC §9.5.
**Done:** every page fetches its endpoint; a mutation is followed by `refreshAll()`; nothing overflows
at 360 px (A3, A18).

### T21 — Backup, README, full verification
**Files:** `app/api/calls.py` (backup + calls), `README.md`, `.outworld/plan.md`
**Build:** `GET /backup` via the SQLite backup API; README with the two run commands; quote every
verify output in `.outworld/plan.md`.
**Verify:**
```sh
cd backend;  uv run ruff check .; uv run pytest -q
cd frontend; bun run check; bun run build
grep -ri worakrit backend frontend
```
**Done:** all green; grep returns nothing (A19); backup file opens with `sqlite3` and contains the
same row counts.

---

## 2. Definition of done per task

A task is done only when all four hold:

1. the verify command was run **after** the last edit and its output quoted;
2. the acceptance ids it claims are demonstrably passing;
3. the diff touches only the files listed for that task;
4. one commit, message `T<n>: <summary>`.

No task is "done" because the code looks right.

---

## 3. Known risks and the stop condition

| Risk | Trigger | Action |
|---|---|---|
| `pysweph` compile fails | T0 `uv sync` | report the compiler error; do not pin 3.13 silently |
| Tailwind 4 `@custom-variant` unsupported | T17 | use the `[data-theme]` fallback; report it |
| SvelteKit 3 API not in the reference | any frontend task | `MISSING REF: sveltekit/references/<file>: <what>` and stop |
| Brave response shape unknown | T13b/T14 | fetch the live docs during research, never from memory |
| `solve` returns a branch the scan misses | T9 | the union of both methods is the contract; a missed root is a test failure, not a note |
| SQLite locked under concurrent writes | T6/T15 | WAL + `busy_timeout=5000`; if it still fails, serialise with one write lock and record why |

---

## 4. Verification matrix

| Task | Command | Acceptance |
|---|---|---|
| T0 | `uv sync` + `bun install` | A1 partial |
| T1 | `pytest tests/test_health.py` | A4 |
| T2 | `pytest tests/test_projects.py tests/test_chats.py` | A5 |
| T3 | `pytest tests/test_chat_turn.py tests/test_chat_paging.py` | A6 |
| T4 | `pytest tests/test_knowledge_fts.py` | A7 |
| T5 | `pytest tests/test_tools_fs.py` | A8 |
| T6 | `pytest tests/test_tools_shell.py` | A9, A17 |
| T7 | `pytest tests/test_tools_code.py` | A10 |
| T8 | `pytest tests/test_tools_search.py` | A14 |
| T9 | `pytest tests/test_calc_z3.py` | A11, A26, A27 |
| T10 | `pytest tests/test_calc_z3.py` | A12 |
| T11 | `python -m tools.astro` + `pytest tests/test_astro_fixtures.py` | A13, A13b |
| T12 | `pytest tests/test_project_tool.py` | A29, A30 |
| T13 | `pytest tests/test_pipe.py` | A26–A28, A31–A34 |
| T14 | `pytest tests/test_providers.py tests/test_agent_no_llm.py` | A15, A16 |
| T15 | `pytest tests/test_agent_no_llm.py` | A16 |
| T16 | `pytest tests/test_learning.py tests/test_patterns.py` | A20–A25 |
| T17 | `bun run check && bun run build` | A1, A3 |
| T19 | manual send | A6, A26 |
| T20 | manual walk | A3, A18 |
| T21 | full suite + grep | A2, A19 |
