# SPEC — Outworld Workbench

2026-11-21 · derived from `.outworld/brief.md` (A1–A19)
**Status: complete scope, implemented in full.** There is no "later phase" list. What is written here
gets built. The only excluded work is `§13 Non-goals`, which the owner approved.

Scope: whole system. The backend contract and the frontend contract are both normative.

---

## 0. Principles

1. **Two processes, dev and prod.** SvelteKit via Bun (`:5173` dev, `:3000` prod) renders the UI;
   FastAPI (`:8000`) owns data, tools, files, LLM. `adapter-bun` emits a **server**, not static files,
   so uvicorn never serves the frontend.
2. **The browser calls the backend directly.** No BFF, no proxy route, no `+server.ts`, no
   `+page.server.ts`, no form actions. One client module (`#lib/api.ts`) knows the base URL.
3. **The backend does the work.** The frontend never computes a chart, never runs sympy, never touches
   a file. It sends JSON and renders JSON.
4. **SQLite is the only state store.** No module-level `let chats = []` anywhere. Waiting states (chat
   runs, pending approvals) are rows, not in-memory registries.
5. **One envelope for every tool**, one audit row for every call.
6. **LLM is optional.** Zero providers is a supported, tested state.
7. `E:\outworld` and `D:\worakrit` are independent projects (A19).
8. **The system learns from its own runs.** Every turn is recorded as a run, successful tool chains
   are distilled into patterns, and the most relevant patterns are injected into the next prompt.
   Learning is deterministic and works with no LLM configured (§4.10–4.13, §5.10).
9. **Pipe first, LLM last.** A message is matched against `data/intent.yaml`; a match runs the plan from
   `data/plan_cheat.yaml` through the tool layer with no model call. The LLM agent is the fallback, not
   the default (§14).

---

## 1. Repository layout

```text
E:\outworld
├── .gitignore              data/ workspace/ .venv node_modules build .svelte-kit
├── AGENTS.md  README.md  SPEC.md  PLAN.md
├── .outworld/              brief.md  project.md  plan.md
├── data/                   outworld.db  settings.json          (git-ignored)
├── workspace/              sandbox root                        (git-ignored)
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── data/assets/        sepl_18.se1 sepl_24.se1 semo_18.se1 semo_24.se1
│   ├── app/
│   │   ├── main.py         FastAPI app, CORS, lifespan, router mount
│   │   ├── config.py       env + settings.json
│   │   ├── db.py           connection, DDL, FTS triggers, helpers
│   │   ├── sandbox.py      path guard, allowlist, approval mint/wait/verify
│   │   ├── llm.py          provider client (openai / ollama), stream
│   │   ├── websearch.py    Brave Search adapter
│   │   ├── runner.py       shared chat-run used by sync + SSE paths
│   │   ├── agent.py        tool loop
│   │   ├── learning.py     run recording, pattern distill, recall, stats
│   │   └── api/            health projects chats knowledge commands tools providers calls learning
│   ├── tools/
│   │   ├── registry.py     register_tool / get_tool / list_tools
│   │   ├── astro.py        copied content, owned here (not edited)
│   │   ├── fs.py shell.py code.py search.py calc.py z3.py knowledge.py memory.py
│   └── tests/              17 files, 45–65 tests, fixtures/
└── frontend/
    ├── package.json  vite.config.ts  tsconfig.json  .env.example
    └── src/
        ├── app.css  app.html
        ├── lib/            api.ts types.ts stream.ts theme.ts
        │   └── components/ 15 .svelte files
        └── routes/         9 files (1 layout + 8 pages)
```

---

## 2. Dependencies (exact, installable)

### 2.1 `backend/pyproject.toml`

```toml
[project]
name = "outworld-backend"
version = "2.0.0"
requires-python = ">=3.15"
dependencies = [
  "fastapi>=0.165.0",
  "uvicorn>=0.54.0",
  "pydantic>=2.14.4",
  "httpx>=0.28.1",
  "pysweph>=2.10.3.6",
  "sympy>=1.14.0",
  "z3-solver>=5.4.1.0",
  "tzdata>=2026.6",
  "pyyaml>=6.0.2",
]

[dependency-groups]
dev = ["pytest>=9.0", "ruff>=0.17.4"]

[tool.ruff]
target-version = "py315"
line-length = 100
[tool.ruff.lint]
select = ["E","W","F","I","UP","B","SIM","RET","S","PT","RUF"]
ignore = ["E501","S101"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
cache_dir = ".pytest-cache"
addopts = ["--basetemp=.pytest-tmp"]
```

`tzdata` is required: `zoneinfo("Asia/Bangkok")` has no OS database on Windows.
`geopy` / `timezonefinder` are not installed — unknown locations return a clean tool error.

### 2.2 `frontend/package.json`

```json
{
  "type": "module",
  "imports": { "#lib": "./src/lib/index.js", "#lib/*": "./src/lib/*" },
  "scripts": {
    "dev": "vite dev",
    "build": "bun --bun vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --output machine"
  },
  "dependencies": { "@lucide/svelte": "^1.74.0" },
  "devDependencies": {
    "@sveltejs/kit": "^3.4.0",
    "@sveltejs/adapter-bun": "^1.0.2",
    "@sveltejs/vite-plugin-svelte": "^7.2.0",
    "@tailwindcss/vite": "^4.3.0",
    "svelte": "^5.59.1",
    "svelte-check": "^4.6.0",
    "tailwindcss": "^4.3.0",
    "typescript": "^6.0.3",
    "vite": "^8.3.8"
  }
}
```

No `svelte.config.js`. TypeScript stays on 6.x (Kit 3 needs that compiler API).

---

## 3. Configuration

`data/settings.json`, written with defaults on first run:

```json
{
  "workspace_root": "E:\\outworld\\workspace",
  "shell_allowlist": ["echo", "ls", "dir", "pwd", "git status", "git diff", "git log"],
  "shell_timeout_s": 30,
  "code_timeout_s": 20,
  "max_output_bytes": 65536,
  "llm_max_iterations": 8,
  "theme": "system",
  "web_search": { "enabled": false, "provider": "brave", "api_key": null }
}
```

| Env var | Default | Consumed by |
|---|---|---|
| `OUTWORLD_DATA` | `E:\outworld\data` | db + settings |
| `OUTWORLD_DB` | `<data>/outworld.db` | SQLite |
| `OUTWORLD_WORKSPACE` | `E:\outworld\workspace` | sandbox root |
| `OUTWORLD_EPHE` | `backend\data\assets` | `astro.set_ephe_path` |
| `OUTWORLD_CORS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000` | CORS |
| `OUTWORLD_PORT` | `8000` | uvicorn |
| `VITE_API_BASE` | `http://127.0.0.1:8000` | `#lib/api.ts` |

Both sides ship a `.env.example` documenting these.

---

## 4. Database — 11 tables + 2 FTS5 indexes

`data/outworld.db`. On open: `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`.
Schema version in `PRAGMA user_version` (currently 1). DDL is `CREATE TABLE IF NOT EXISTS`; no
migration framework (the DB is created from empty; changing the schema means deleting the file).

Rules that apply everywhere:

- All SQL uses `?` placeholders. String interpolation into SQL is forbidden.
- Text ids are `uuid4().hex`; log tables use INTEGER autoincrement.
- Timestamps are UTC ISO-8601 written by Python: `2026-11-21T10:00:00.123Z`.
- One connection per request scope (`try/finally: close`). WAL serialises writers; no retry loop.

### 4.1 `projects` (6 columns)

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `name` | TEXT | NOT NULL |
| `root_path` | TEXT | NOT NULL DEFAULT `'.'` — relative, validated under workspace |
| `instructions` | TEXT | NOT NULL DEFAULT `''` |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

### 4.2 `chats` (5 columns)

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `project_id` | TEXT | NULL · FK projects(id) ON DELETE CASCADE |
| `title` | TEXT | NOT NULL DEFAULT `'New chat'` — set from the first user message, 48 chars |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL — bumped on every message |

### 4.3 `messages` (6 columns)

| Column | Type | Constraint |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `chat_id` | TEXT | NOT NULL · FK chats(id) ON DELETE CASCADE |
| `role` | TEXT | NOT NULL CHECK IN (`user`,`assistant`,`tool`,`system`) |
| `content` | TEXT | NOT NULL |
| `meta_json` | TEXT | NOT NULL DEFAULT `'{}'` |
| `created_at` | TEXT | NOT NULL |

`meta_json` contents (normative):

```json
{ "provider_id": "…", "model": "…", "tool_call_ids": [12,13], "warnings": ["llm_disabled"] }
```

Tool output is not duplicated into `messages`; the assistant message references `tool_calls` rows via
`meta_json.tool_call_ids`. `role:"tool"` exists for imported transcripts and is unused by the runner.

Index `messages_chat ON messages(chat_id, id)`.

### 4.4 `knowledge` (6 columns)

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `project_id` | TEXT | NULL · FK projects(id) ON DELETE SET NULL |
| `title` | TEXT | NOT NULL |
| `body` | TEXT | NOT NULL DEFAULT `''` |
| `tags` | TEXT | NOT NULL DEFAULT `''` (space separated) |
| `created_at` / `updated_at` | TEXT | NOT NULL |

Index `knowledge_project ON knowledge(project_id)`.

### 4.5 `knowledge_fts` (FTS5, external content)

```sql
CREATE VIRTUAL TABLE knowledge_fts USING fts5(
  title, body, tags,
  content='knowledge', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);
```

Triggers `knowledge_ai`, `knowledge_ad`, `knowledge_au` keep it in sync. Rank `bm25(knowledge_fts)`;
snippet `snippet(knowledge_fts, 2, '<mark>', '</mark>', '…', 12)`.

### 4.6 `providers` (8 columns)

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `name` | TEXT | NOT NULL |
| `kind` | TEXT | NOT NULL CHECK IN (`openai`,`ollama`) |
| `base_url` | TEXT | NOT NULL |
| `model` | TEXT | NOT NULL |
| `api_key` | TEXT | NOT NULL DEFAULT `''` — never serialised |
| `enabled` | INTEGER | NOT NULL DEFAULT 0 CHECK IN (0,1) |
| `created_at` | TEXT | NOT NULL |

LLM is enabled iff `COUNT(*) WHERE enabled=1 AND model<>''` > 0.

### 4.7 `commands` (6 columns) — named shell snippets

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `project_id` | TEXT | NULL · FK projects(id) ON DELETE CASCADE |
| `name` | TEXT | NOT NULL |
| `template` | TEXT | NOT NULL, `{{param}}` placeholders |
| `params_json` | TEXT | NOT NULL DEFAULT `'[]'` |
| `created_at` | TEXT | NOT NULL |

Rendering replaces every `{{param}}`; a missing param → `400 missing_param:<name>`. Execution goes
through the `shell` tool, so allowlist, approval and audit apply unchanged.

### 4.8 `tool_calls` (11 columns) — audit

| Column | Type | Constraint |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `chat_id` | TEXT | NULL (NULL = tool bench) |
| `run_id` | TEXT | NULL — groups calls into the run they belong to |
| `tool` | TEXT | NOT NULL |
| `args_json` | TEXT | NOT NULL — `api_key`/`password` replaced with `"***"` |
| `result_json` | TEXT | NULL — audit copy truncated to 8 KiB; the HTTP/SSE response is never truncated |
| `status` | TEXT | NOT NULL CHECK IN (`ok`,`error`,`denied`,`timeout`) |
| `error` | TEXT | NULL |
| `ms` | INTEGER | NOT NULL |
| `created_at` | TEXT | NOT NULL |

Indexes `tool_calls_chat ON tool_calls(chat_id, id DESC)`, `tool_calls_time ON tool_calls(created_at DESC)`.

### 4.9 `approvals` (6 columns)

| Column | Type | Constraint |
|---|---|---|
| `token` | TEXT | PRIMARY KEY (`ap-` + 10 hex) |
| `tool` | TEXT | NOT NULL |
| `args_json` | TEXT | NOT NULL — exactly what will run |
| `status` | TEXT | NOT NULL DEFAULT `'pending'` CHECK IN (`pending`,`approved`,`denied`,`expired`) |
| `created_at` | TEXT | NOT NULL |
| `expires_at` | TEXT | NOT NULL — TTL 10 min |

The row **is** the state machine. `sandbox.mint()` inserts `pending`; `sandbox.wait(token)` polls the
row every 0.5 s until it leaves `pending` or passes `expires_at`; `sandbox.decide()` transitions it and
executes the stored args exactly once.

**Cascade map:** project → chats, commands (CASCADE), knowledge (SET NULL). chat → messages (CASCADE).
`tool_calls` has no FK by design: audit survives deletion.

### 4.10 `runs` (12 columns) — one row per chat turn

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `chat_id` | TEXT | NULL · FK chats(id) ON DELETE CASCADE |
| `project_id` | TEXT | NULL |
| `intent` | TEXT | NOT NULL — normalised first 200 chars of the user message |
| `intent_source` | TEXT | NOT NULL CHECK IN (`pipe`,`llm`,`none`) |
| `matched_rule` | TEXT | NULL — rule id from `intent.yaml` |
| `status` | TEXT | NOT NULL CHECK IN (`running`,`ok`,`error`,`denied`,`aborted`) |
| `iterations` | INTEGER | NOT NULL DEFAULT 0 — model calls |
| `tool_count` | INTEGER | NOT NULL DEFAULT 0 |
| `tokens` | INTEGER | NOT NULL DEFAULT 0 — 0 when unknown |
| `started_at` | TEXT | NOT NULL |
| `ended_at` | TEXT | NULL until the run closes |

Index `runs_chat ON runs(chat_id, started_at DESC)`, `runs_time ON runs(started_at DESC)`.
`status` closes as `ok` only when no tool ended `error`/`denied`/`timeout`.

### 4.11 `patterns` (12 columns) — distilled tool chains

| Column | Type | Constraint |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `project_id` | TEXT | NULL · FK projects(id) ON DELETE SET NULL |
| `name` | TEXT | NOT NULL — `fs → calc` style, or the model's one-line summary when available |
| `intent` | TEXT | NOT NULL — intent of the run that produced it |
| `tool_chain_json` | TEXT | NOT NULL — `["fs","calc"]` |
| `args_template_json` | TEXT | NOT NULL — per step: `{"tool":"fs","op":"read","path":"{{path}}"}` |
| `uses` | INTEGER | NOT NULL DEFAULT 0 — times recalled |
| `success` | INTEGER | NOT NULL DEFAULT 0 — times the recalling run ended `ok` |
| `last_used_at` | TEXT | NULL |
| `source_run_id` | TEXT | NULL |
| `enabled` | INTEGER | NOT NULL DEFAULT 1 CHECK IN (0,1) |
| `created_at` | TEXT | NOT NULL |

**Distillation (deterministic, no LLM):** when a run closes `ok` with `tool_count ≥ 2`, take its
ordered `(tool, args)` list, replace every string arg with `"{{" + key + "}}"` and keep numbers/bools,
then upsert on the pair (`intent`, `tool_chain_json`): existing → `uses += 1, success += 1,
last_used_at = now`; otherwise insert. Single-tool runs never become patterns (they are not worth
recalling). With an LLM available the `name` may additionally be replaced by a one-line summary; this
is enrichment, never required.

### 4.12 `pattern_fts` (FTS5, external content)

```sql
CREATE VIRTUAL TABLE pattern_fts USING fts5(
  name, intent, content='patterns', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);
```

Triggers `pattern_ai`, `pattern_ad`, `pattern_au` keep it in sync.

**Recall rule (no LLM):** normalise the incoming user message the same way (`intent`), run an FTS5
`MATCH` over `pattern_fts`; keep `enabled=1 AND success > 0`; order by
`success * 1.0 / max(uses,1) DESC, last_used_at DESC`; take 3. Skipped entirely when the match set is
empty. Injected block is capped at 600 characters.

### 4.13 `feedback` (4 columns)

| Column | Type | Constraint |
|---|---|---|
| `run_id` | TEXT | PRIMARY KEY · FK runs(id) ON DELETE CASCADE |
| `verdict` | TEXT | NOT NULL CHECK IN (`good`,`bad`) |
| `note` | TEXT | NOT NULL DEFAULT `''` |
| `created_at` | TEXT | NOT NULL |

`bad` on a run decrements that run's pattern `success` (floor 0); `good` increments it. Feedback never
deletes a pattern — it only changes its ranking.

---

## 5. HTTP API — 47 endpoints

Base `http://127.0.0.1:8000/api`. JSON in/out. Errors `{ "message": string }`.
`201` create · `200` update · `204` delete · `400` bad body · `404` unknown id · `409` conflict ·
`410` expired approval.

### 5.1 System (3)

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 1 | GET | `/health` | — | `{status,python,version,tools[8],llm,db,schema,theme}` |
| 2 | GET | `/tools` | — | `[{id,description,input_schema}]` |
| 3 | POST | `/tools/{tool}` | `{...args, approval_token?}` | `{ok,data,meta,error}` |

`/tools/{tool}` answers `200` even when the tool fails (`ok:false`). `400` malformed request, `404`
unknown tool, `409` approval required.

### 5.2 Projects (5)

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 4 | GET | `/projects` | — | `[{id,name,root_path,updated_at,chat_count}]` |
| 5 | POST | `/projects` | `{name,root_path?,instructions?}` | `201` project |
| 6 | GET | `/projects/{id}` | — | `{project,chats[],notes[],commands[]}` |
| 7 | PATCH | `/projects/{id}` | `{name?,root_path?,instructions?}` | `200` project |
| 8 | DELETE | `/projects/{id}` | — | `204` |

### 5.3 Chats (6)

| # | Method | Path | Body / Query | Response |
|---|---|---|---|---|
| 9 | GET | `/projects/{id}/chats` | — | `[{id,title,updated_at,message_count}]` |
| 10 | POST | `/projects/{id}/chats` | `{title?}` | `201` chat |
| 11 | GET | `/chats` | `?limit=20` (max 100) | recent chats |
| 12 | GET | `/chats/{id}` | `?limit=100&before=<message_id>` | `{chat, messages[], calls[], has_more}` |
| 13 | PATCH | `/chats/{id}` | `{title}` | `200` chat |
| 14 | DELETE | `/chats/{id}` | — | `204` |

`before` is exclusive (`id < before`), messages returned ascending, `has_more` true when older
messages exist. `calls` covers exactly the returned messages.

### 5.4 Chat turns (2) — the whole chat API

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 15 | POST | `/chat/{chat_id}` | `{content}` | `201 {user_message, assistant_message\|null, warnings[]}` |
| 16 | POST | `/chat/{chat_id}/stream` | `{content}` | `text/event-stream` (§6) |

Both call `runner.run_chat()`:

0. open a `runs` row (`running`), and fetch recall hints (§4.12) for the message;
1. insert the user message; bump `chats.updated_at`; set `title` if it is still `New chat`;
2. no provider enabled → close the run with the tool-free outcome, return `201` with
   `assistant_message: null`, `warnings:["llm_disabled"]`; tools stay reachable through
   `/tools/{tool}` (A15);
3. otherwise run the agent loop (≤ `llm_max_iterations`) with the recall hints in the system prompt,
   writing `tool_calls` rows (each carrying `run_id`) and pausing on approvals (§6);
4. insert the assistant message with `meta_json.tool_call_ids`;
5. close the run: `status` = `ok` only if no tool ended `error`/`denied`/`timeout`, then distil a
   pattern (§4.11) and bump `uses` for every pattern that was injected;
6. sync path returns both messages; stream path emits SSE ending in `done`.

### 5.5 Knowledge (5)

| # | Method | Path | Body / Query | Response |
|---|---|---|---|---|
| 17 | GET | `/knowledge` | `?q=&project_id=&limit=50&snippets=1` | `[{id,title,tags,project_id,updated_at,snippet?}]` |
| 18 | POST | `/knowledge` | `{title,body,tags?,project_id?}` | `201` note |
| 19 | GET | `/knowledge/{id}` | — | note |
| 20 | PATCH | `/knowledge/{id}` | `{title?,body?,tags?}` | `200` note |
| 21 | DELETE | `/knowledge/{id}` | — | `204` |

`q` present → FTS5 ranked by `bm25`; absent → `LIKE` on title.

### 5.6 Commands (5)

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 22 | GET | `/projects/{id}/commands` | — | `[{id,name,template,params_json}]` |
| 23 | POST | `/projects/{id}/commands` | `{name,template,params?}` | `201` |
| 24 | PATCH | `/commands/{id}` | `{name?,template?,params?}` | `200` |
| 25 | DELETE | `/commands/{id}` | — | `204` |
| 26 | POST | `/commands/{id}/run` | `{params:{…}}` | shell envelope, always audited |

### 5.7 Providers (5)

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 27 | GET | `/providers` | — | `[{id,name,kind,base_url,model,enabled}]` (no key) |
| 28 | POST | `/providers` | `{name,kind,base_url,model,api_key?,enabled?}` | `201` |
| 29 | PATCH | `/providers/{id}` | partial; empty `api_key` keeps the old key | `200` |
| 30 | DELETE | `/providers/{id}` | — | `204` |
| 31 | POST | `/providers/{id}/test` | — | `{ok,model,latency_ms}` \| `{ok:false,error}` |

### 5.8 Audit + approvals (2)

| # | Method | Path | Body / Query | Response |
|---|---|---|---|---|
| 32 | GET | `/calls` | `?chat_id=&limit=50` (max 200) | `[{id,tool,status,ms,created_at,args_preview}]` |
| 33 | POST | `/approvals/{token}` | `{decision:"approve"\|"deny"}` | `{status, call_id?, result?}` |

Approval execution has **one** path: `POST /approvals/{token}` executes the stored args once, writes
the `tool_calls` row, and returns the result. A waiting agent run reads that row from the DB and
continues; the tool bench reads `result` from this response.

### 5.9 Pipe (4)

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 34 | POST | `/pipe/route` | `{message}` | `{intent,rule_id,confidence,plan:{steps},explain}` — never executes |
| 35 | POST | `/pipe/run` | `{message, chat_id?}` | `{intent,plan,results[],answer,run_id}` |
| 36 | GET | `/pipe/rules` | — | `{intents:[{id,priority,patterns}], plans:[{intent,steps}]}` |
| 37 | POST | `/pipe/reload` | — | `{intents:int, plans:int}` — re-reads the two YAML files |

`/chat/{id}` and `/chat/{id}/stream` try `/pipe/route` first: a match with `confidence ≥ 0.6` runs the
plan and never calls a model. No match and no provider → `warnings:["no_route"]` (§14.5).

### 5.10 Learning (13)

| # | Method | Path | Body / Query | Response |
|---|---|---|---|---|
| 38 | GET | `/runs` | `?chat_id=&limit=50` | `[{id,intent,intent_source,status,tool_count,iterations,started_at,ended_at,verdict?}]` |
| 39 | GET | `/runs/{id}` | — | `{run, calls[], feedback?}` |
| 40 | POST | `/runs/{id}/feedback` | `{verdict:"good"\|"bad", note?}` | `200 {verdict}` |
| 41 | GET | `/patterns` | `?q=&project_id=&limit=50` | `[{id,name,intent,tool_chain,uses,success,rate,last_used_at,enabled}]` |
| 42 | GET | `/patterns/{id}` | — | `{pattern, sample_run}` |
| 43 | PATCH | `/patterns/{id}` | `{name?,enabled?}` | `200` pattern |
| 44 | DELETE | `/patterns/{id}` | — | `204` |
| 45 | POST | `/patterns/{id}/promote` | `{project_id}` | `200 {instructions}` |
| 46 | GET | `/learning/stats` | — | `{runs_total,ok_rate,pipe_rate,patterns_total,top_patterns[3],recalls_24h,unrouted}` |

Rules: a disabled pattern is excluded from recall on the next turn (no cache to invalidate);
`promote` appends one bullet to `projects.instructions` and returns the new text, so the change is
visible and reversible by editing the project.

### 5.11 Backup (1)

| # | Method | Path | Body | Response |
|---|---|---|---|---|
| 47 | GET | `/backup` | — | `application/octet-stream`, filename `outworld-YYYYMMDD-HHMM.db` |

Uses the SQLite backup API against the live connection (safe with WAL), so the resulting file is a
consistent snapshot. This is the only data-safety mechanism (no auth means no remote exposure to
protect).

### 5.12 CORS

`allow_origins` from `OUTWORLD_CORS`, `allow_methods=["*"]`, `allow_headers=["*"]`,
`allow_credentials=False`. Loopback only. There is no auth: anything on this machine can call `:8000`
(§13 states the consequence).

---

## 6. SSE contract

`content-type: text/event-stream`, `cache-control: no-cache`, `x-accel-buffering: no`.
One JSON object per `data:` line, `event:` for the name, `: keepalive` every 15 s.

| event | data | notes |
|---|---|---|
| `start` | `{"run_id":"…"}` | first event |
| `route` | `{"intent":"math_calc","rule_id":"math_calc","source":"pipe"\|"llm"}` | how the turn was routed |
| `delta` | `{"text":"…"}` | assistant text chunk |
| `tool` | `{"call_id":12,"tool":"shell","args":{…},"status":"running"}` | |
| `tool_result` | `{"call_id":12,"status":"ok"\|"error"\|"denied"\|"timeout","ms":41,"preview":"…"}` | |
| `approval` | `{"call_id":12,"token":"ap-…","tool":"shell","args":{…},"expires_at":"…"}` | run is paused |
| `error` | `{"message":"llm_disabled"\|"max_iterations"\|"approval_expired"\|…}` | |
| `done` | `{"message_id":88}` | last event |

Rules:

- The assistant message is committed **before** `done`.
- Client disconnect cancels the loop; the partial message is persisted with
  `meta_json.warnings:["aborted"]`.
- **Interactive approval inside an agent run is implemented**: when a `shell`/`code` call is not on
  the allowlist, the runner inserts the `approvals` row, emits `approval`, and awaits
  `sandbox.wait(token)` (0.5 s DB poll, 10 min TTL). On approve the stored args run once and the loop
  continues with the real result; on deny the loop continues with `status:"denied"`; on expiry the
  row becomes `expired` and the loop receives `status:"timeout"`.
- Server restart during a wait leaves `pending` rows that expire; the run is lost and `GET /chats/{id}`
  shows the partial transcript. Stated, not hidden.
- No provider → `/chat/{id}/stream` returns `409 {"message":"llm_disabled"}` before opening the stream.

---

## 7. Tool contract — 12 tools

Envelope: `{"ok":bool,"data":any,"meta":{…},"error":string|null}`. Ids exactly:
`fs`, `shell`, `code`, `search`, `astro`, `calc`, `z3`, `knowledge`, `memory`, `project`, `script`,
`planner`.

| Tool | Input | `data` on success |
|---|---|---|
| `fs` | `{op:"read"\|"write"\|"list"\|"patch", path, content?, old?, new?}` | `{content,bytes}` · `{path,bytes}` · `{entries[]}` |
| `shell` | `{command, cwd?, timeout_s?}` | `{stdout,stderr,exit_code,truncated}` |
| `code` | `{language:"python"\|"javascript", source, timeout_s?}` | `{stdout,stderr,exit_code,truncated}` |
| `search` | `{scope:"knowledge"\|"workspace"\|"web", q, limit?, freshness?}` | `{hits:[{id\|path\|url,snippet,rank}]}` |
| `astro` | `{birth_date, birth_time?, location\|lat+lon, tz_offset?\|tz_name?, systems?}` | 4-system chart |
| `calc` | `{op:"eval"\|"solve", expr, var?}` | `{result, exact?, roots?}` |
| `z3` | `{smt2}` | `{status, model?}` |
| `knowledge` | `{op:"create"\|"search"\|"get", …}` | note or hits |
| `memory` | `{op:"search"\|"save"\|"forget", q?, name?, intent?, tool_chain?}` | patterns / `{id}` |
| `project` | `{op:"scaffold"\|"verify", name, template?, path?}` | `{path, files[]}` · `{checks[],ok}` |
| `script` | `{op:"list"\|"read"\|"write"\|"delete"\|"run"\|"seed", name?, source?, params?, params_values?}` | `{scripts[]}` · `{source,manifest}` · `{stdout,stderr,exit_code}` |
| `planner` | `{goal, project_id?}` | `{steps:[{title,tool,args}], assumptions[]}` |

### 7.1 `fs`
`(workspace_root / path).resolve()` then `is_relative_to(workspace_root.resolve())`; failure →
`{ok:false,error:"outside_workspace"}` + `403`. Symlinks resolved before the check. `patch` requires
exactly one occurrence of `old` → else `{ok:false,error:"ambiguous_patch"}` + `409`.

### 7.2 `shell`
Allowlist = prefix match on the normalised command, case-insensitive. Any of `&&`, `||`, `|`, `;`,
`>`, `<`, `$(` forces approval regardless of the prefix. Not allowlisted → approval flow (§6) with
`{ok:false,error:"approval_required"}` + `409` on the bench path.
Execution: `subprocess.run(shell=True, timeout=…)` in the sandbox `cwd`; timeout kills the tree.
Output capped at `max_output_bytes` with `truncated:true`.

### 7.3 `code`
`python` → `sys.executable -I -c <source>`; `javascript` → `bun -e <source>` when `bun` exists, else
`{ok:false,error:"unsupported_language"}`. Runs in `workspace/.tmp/<uuid>`, removed afterwards.
Timeout → `status:"timeout"`, process killed.

### 7.4 `search`
- `knowledge` → FTS5 query.
- `workspace` → recursive scan, files ≤ 1 MiB, skipping `node_modules`, `.git`, `.venv`, `.svelte-kit`;
  case-insensitive substring, ±80 chars context, max `limit` hits.
- `web` → `websearch.py` (Brave REST) when `settings.web_search.enabled` and `api_key` is set;
  otherwise `{ok:false,error:"web_search_not_configured"}`. The endpoint, auth header and response
  mapping are taken from Brave's documentation during the research step of that task — never from
  memory.

### 7.5 `astro` — the copied module
- File `backend/tools/astro.py`, registered name `astro_all`, **not edited**.
- Startup: `astro.set_ephe_path(OUTWORLD_EPHE)` once.
- Dispatch: `astro.run(**args)`; output returned unchanged.
- Module defaults: `birth_time="12:00"`, `location="Bangkok"`, all four systems.
- Unknown location without `geopy` → the module raises `ValueError`; the adapter converts it to
  `{ok:false,error:"<thai message>"}`.

### 7.6 `calc`
`sympy` with an explicit namespace (`symbols, solve, simplify, expand, factor, sin, cos, tan, sqrt,
pi, E, log, exp, Eq, diff, integrate, nsolve, Rational`). `parse_expr` only; `eval` never called.
Parse error → `{ok:false,error:"<sympy text>"}`.

**`op:"eval"` — rational by default.** Parsing uses
`parse_expr(expr, transformations=standard_transformations + (rationalize,))`, measured to turn
`9.8-9.11` into the exact `69/100` instead of the float `0.690000000000001`. Response carries
`exact:"69/100"` and `result:0.69`.

**`op:"solve"` — exact then numeric, both measured.**

1. `solve(Eq(lhs, rhs), var)` → each root `N(root, 15)`; keep roots where `.is_real`.
2. Grid scan of `lhs - rhs` over `[0.001, 40]` step `0.1` (numbers only) for sign changes, refine with
   `nsolve` inside each bracket, swallow per-bracket failures, dedupe with `abs(a-b) < 1e-6`.
3. `roots` = union, sorted; `result` = the roots rendered as strings; `exact` = the `solve` strings
   when the union is size ≤ 4.

Measured behaviour this must reproduce:

| input | `solve` output | real roots | duration |
|---|---|---|---|
| `9.8-9.11` (`eval`) | `69/100` | — | < 10 ms |
| `3**x - x**9` (`solve`) | `[27, -9*LambertW(-log(3)/9)/log(3)]` | `27.0`, `1.15082482130` | < 200 ms |

### 7.7 `z3`
`z3.parse_smt2_string(input)` → `Solver().add(...)` → `check()`; `sat` includes `model()` as
`{name:"value"}` strings.

### 7.8 `knowledge`
Same store and SQL as §5.5. `create` → note; `search` → FTS5 hits; `get` → note.

### 7.9 `memory` — the agent's handle on §4.11
- `search` → the same FTS5 recall as §4.12, returned as data (so the agent can ask explicitly).
- `save` → insert a pattern row from `{name, intent, tool_chain}`; `success` starts at 1 because a
  deliberate save is a claim that it worked.
- `forget` → set `enabled=0` (soft; `DELETE /patterns/{id}` is the hard delete).
- Never executes anything. A pattern is text, not a plan.

### 7.10 `project`
- `scaffold` → write a minimal project under `workspace/<name>`; templates: `python` (package,
  `pyproject.toml`, `tests/test_main.py`), `static` (`index.html`, `style.css`, `script.js`),
  `svelte` (`package.json`, `vite.config.ts`, `src/routes/+page.svelte`). Refuses to overwrite a
  non-empty directory → `{ok:false,error:"target_exists"}`.
- `verify` → run the detected checks: `pytest -q` for `python`, `bun run check` for `svelte`, file
  presence for `static`; each check is a `shell` dispatch (audited, allowlisted commands only).
- Returns `{checks:[{name,ok,output}], ok}`.

### 7.11 `planner`
- Deterministic: reads `plan_cheat.yaml` (§14.3) and returns a step skeleton for the goal, filling
  `{{name}}`-style slots from the message. No model call.
- With a provider available the agent may enrich step titles; the skeleton is always the floor.
- Never executes steps. The pipe executes them.

### 7.12 `script` — user scripts as first-class tools
- Storage: `workspace/scripts/<name>.py|.js` plus `<name>.json` manifest
  `{description, language, params[], timeout_s}`. Name `^[a-z0-9_-]{1,40}$`; params `^[A-Za-z0-9_]{1,24}$`.
- Ops: `list`, `read`, `write`, `delete`, `run`, `seed`.
- `run` resolves params in manifest order, passes them as argv after an absolute script path, cwd is
  the workspace, timeout from the manifest, output capped at `max_output_bytes`.
- **Agent exposure:** every script appears in the tool catalogue as `script__<name>` with one string
  property per declared param; a call is dispatched to `script(op="run", params_values=args)`.
- **Seed set** (`backend/data/seed_scripts/`, installed by `op:"seed"`, never overwrites): `tree`,
  `project_report`, `todo_scan`, `db_stats`, `daily_note`, `csv_summary`, `astro_text`. All stdlib.

### 7.13 Audit
Every dispatch inserts one `tool_calls` row before the response leaves the process — including
`denied`, `timeout`, and approval-executed calls. (A17)

---

## 8. LLM layer

- `llm.list_enabled()` → providers with `enabled=1` and `model<>''`.
- `kind:"openai"` → `POST {base_url}/chat/completions`, `Authorization: Bearer`, body with `model`,
  `messages`, `tools`, `stream`.
- `kind:"ollama"` → `POST {base_url}/api/chat` with `stream:true`.
- `/providers/{id}/test` sends one `stream:false` request and reports `latency_ms`.
- `httpx` timeouts: connect 10 s, read 120 s.
- Agent loop (`agent.py`): system prompt = `projects.instructions` + tool catalogue + the recall block
  from §4.12 (max 3 patterns, 600 chars, header `Known patterns for similar requests:`); call model;
  execute tool calls in order; append results; repeat ≤ `llm_max_iterations`; then
  `error:"max_iterations"`.
- Learning hooks: every turn opens and closes a `runs` row (§4.11); the loop passes `run_id` down so
  each `tool_calls` row belongs to a run. Pattern distillation runs after the run closes, never
  inside the loop.
- A pattern is injected as text only. Nothing is auto-executed, and a pattern that has never succeeded
  (`success = 0`) is never injected.
- Malformed tool arguments → `tool_result` `status:"error"`, loop continues.
- Provider errors → `error` SSE event carrying the HTTP status and message; no retry.

---

## 9. Frontend — 10 route files, 16 components, 4 lib modules

SvelteKit 3.4.0 · Svelte 5 runes · Vite 8 · TS 6 · Tailwind v4 · `@lucide/svelte` · `adapter-bun`.

### 9.1 Routes — 9 pages + 1 layout, no server files

| # | Route | File | Fetches on mount |
|---|---|---|---|
| 0 | — | `+layout.svelte` | `GET /projects`, `GET /chats?limit=20`, `GET /health` |
| 1 | `/` | `+page.svelte` | `GET /chats?limit=10` |
| 2 | `/chat/[id]` | `+page.svelte` | `GET /chats/{id}` |
| 3 | `/projects` | `+page.svelte` | `GET /projects` |
| 4 | `/projects/[id]` | `+page.svelte` | `GET /projects/{id}` |
| 5 | `/knowledge` | `+page.svelte` | `GET /knowledge?q=` |
| 6 | `/tools` | `+page.svelte` | `GET /tools` |
| 7 | `/settings` | `+page.svelte` | `GET /providers`, `GET /health` |
| 8 | `/learning` | `+page.svelte` | `GET /learning/stats`, `GET /patterns`, `GET /runs` |
| 9 | `/pipe` | `+page.svelte` | `GET /pipe/rules` — routes a draft message with `POST /pipe/route` before running it |

No `+page.server.ts`, no `+page.ts`, no `+server.ts`, no `+layout.server.ts`. Data is fetched in
`$effect` with an `AbortController` cleanup and held in `$state`. Trade-off accepted and stated: no
SSR of data, skeleton on first paint, one data path in dev and prod.

### 9.2 `#lib/`

| File | Exports |
|---|---|
| `types.ts` | `Project, Chat, Message, Note, Tool, ToolCall, Provider, Health, SseEvent` |
| `api.ts` | `base`, `get<T>`, `post<T>`, `patch<T>`, `del`, `ApiError{status,message}` |
| `stream.ts` | `streamChat(chatId, content, onEvent, signal)` — `fetch` + `TextDecoder`, blank-line split, `event:`/`data:` parse |
| `theme.ts` | `getTheme()`, `setTheme('system'\|'light'\|'dark')` — applies the class to `<html>` and persists to `localStorage` |

`base = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'`.

### 9.3 Components — 17

| # | File | Props |
|---|---|---|
| 1 | `AppShell.svelte` | `children` |
| 2 | `Rail.svelte` | `items:{href,label,icon}[]`, `active` |
| 3 | `ListPane.svelte` | `sections:{title,items:{id,label,meta?}}[]`, `onnew` |
| 4 | `ChatView.svelte` | `messages:Message[]`, `running:boolean`, `hasMore:boolean`, `onmore()` |
| 5 | `MessageBubble.svelte` | `role`, `content`, `createdAt` |
| 6 | `Composer.svelte` | `onsend(text)`, `disabled`, `placeholder` |
| 7 | `StepLog.svelte` | `calls:ToolCall[]` |
| 8 | `EmptyState.svelte` | `ongreet`, `suggestions:{title,body}[]` |
| 9 | `JsonBench.svelte` | `tools:Tool[]`, `onrun(tool,args)` |
| 10 | `ApprovalModal.svelte` | `request:{token,tool,args,expires_at}`, `ondecide(ok)` |
| 11 | `ProviderForm.svelte` | `provider?`, `onsave`, `ondelete` |
| 12 | `KnowledgeEditor.svelte` | `note?`, `onsave` |
| 13 | `ThemeToggle.svelte` | `value`, `onchange` |
| 14 | `PatternCard.svelte` | `pattern`, `onpromote`, `ontoggle`, `ondelete` |
| 15 | `StatsBar.svelte` | `stats:{runs_total,ok_rate,patterns_total,recalls_24h}` |
| 16 | `RouteChip.svelte` | `route:{intent,rule_id,source,confidence}`, `onopen()` |
| 17 | `ScriptPanel.svelte` | `onresult(result)` — list, install seeds, run with param prompts |

Commands have no separate component: `/projects/[id]` renders them as `ListPane` rows with an inline
form.

Rules: `$props()` only · `$state/$derived/$effect` only · `onclick=` not `on:click` · utility classes,
no `<style>` · icons per file from `@lucide/svelte/icons/*` · `page` from `$app/state` ·
`refreshAll()` never `invalidateAll()` · labelled controls, visible focus.

### 9.4 Layout targets (`app-shell.md`)

| Region | Width | Rule |
|---|---|---|
| rail | 64px fixed | no labels, tooltip 200 ms, active = filled bg |
| list pane | 248–280px | sheet below 768px |
| main | fluid ≥ 480px | only scroll container; header 48–56px; composer `max-w-3xl` pinned |
| panel | 288–320px | sheet below 1280px; tabs at top |

Test at 360 / 768 / 1440; nothing overflows at 360 (A18).

**Theme:** `ThemeToggle` writes `.dark` on `<html>`. `src/app.css` declares the variant; the exact
form is verified against the installed `tailwindcss` 4.3 build before it is written (Tailwind 4 is
CSS-first and `@custom-variant` is not in the skill reference). If that build does not support it, the
fallback is a `[data-theme]` + CSS-variable layer in `app.css` — no guessing either way, and the
toggle ships.

### 9.5 Flows

```text
new chat       POST /projects/{id}/chats → goto `/chat/{id}`
send           POST /chat/{id}/stream → delta* → tool* → approval? → done → refreshAll()
send, no LLM   POST /chat/{id} → 201 warnings:["llm_disabled"] → banner
old messages   GET /chats/{id}?before=<first_id> → prepend, update has_more
run tool       POST /tools/{tool} → StepLog row + result panel
approval       409 {approval_token} → ApprovalModal → POST /approvals/{token} → render result
note save      PATCH /knowledge/{id} → refreshAll()
provider add   POST /providers → refreshAll() → health flips to enabled
command run    POST /commands/{id}/run → audit row + output
theme          ThemeToggle → `#lib/theme.ts` → `<html class="dark">` + localStorage
learning       /learning → stats + patterns list → toggle / promote / delete
feedback       thumbs on a run → POST /runs/{id}/feedback → pattern ranking changes
pipe preview   /pipe → type a message → POST /pipe/route → intent + plan, then /pipe/run
pipe in chat   send → route chip appears → plan runs → answer rendered without a model
```

Learning records `intent_source` and `matched_rule`, so the `/learning` page can show which intents are
served by the pipe and which still need a model.

Leaving `/chat/[id]` aborts the stream through the `$effect` cleanup controller.

---

## 10. Acceptance mapping

| Id | Section |
|---|---|
| A1 | §2.2, §9.1, §11 |
| A2 | §7.9, §11 |
| A3 | §9.1, §9.4 |
| A4 | §5.1 #1, §7 |
| A5 | §4.1, §5.2 |
| A6 | §4.2–4.3, §5.3–5.4, §9.1 |
| A7 | §4.4–4.5, §5.5 |
| A8 | §7.1 |
| A9 | §7.2, §4.9, §5.8, §6 |
| A10 | §7.3 |
| A11 | §7.6 |
| A12 | §7.7 |
| A13 / A13b | §7.5, §11 |
| A14 | §7.4, §3 |
| A15 | §5.4, §6, §8 |
| A16 | §6, §8, §5.7 |
| A17 | §4.8, §7.10 |
| A18 | §9.4 |
| A19 | §0.7, §1, §4 rules |
| A20 | §4.10, §5.9 — a turn writes a `runs` row with intent, tool chain, outcome |
| A21 | §4.11, §4.12 — a repeated successful chain becomes one pattern with `uses`/`success` |
| A22 | §0.8, §4.12 — recall, distillation and `/learning` all work with no provider configured |
| A23 | §4.13 — a `bad` verdict lowers the pattern rate; `success = 0` is never injected |
| A24 | §5.10 #45 — promote appends to `projects.instructions` and the next prompt contains it |
| A25 | §4.11, §7.9 — patterns are hints only, and `enabled = 0` removes one from recall immediately |
| A26 | §14.2 — `9.8-9.11=?` routes to `math_calc`, runs `calc` with no model, returns exact `69/100` |
| A27 | §14.2, §7.6 — `3^x=x^9` routes to `math_solve`, returns roots `27` and `1.150824821` |
| A28 | §14.3 — `วางแผน …` routes to `plan` and `planner` returns an ordered step list |
| A29 | §7.10 — `สร้างโปรเจค hello` scaffolds `workspace/hello` and verifies it |
| A30 | §7.10 — `ตรวจโปรเจค hello` returns `checks[]` with `ok` and quoted output |
| A31 | §7.4, §14.2 — `ข่าวเอไอล่าสุด` routes to `news` (web, `freshness=pd`); with no key it returns `web_search_not_configured`, never a 500 |
| A32 | §14.2 — `ค้นหา …` routes to `search` and returns hits |
| A33 | §14.5 — an unmatched message with no provider returns `warnings:["no_route"]`, no traceback |
| A34 | §5.9 #34 — `/pipe/route` writes no `tool_calls` row and executes nothing |
| A35 | §5.10 #46 — `ok_rate` counts only turns that actually ran; an unrouted turn increments `unrouted` and leaves the rate at 0; `recalls_24h` counts only patterns used in the last 24 h |
| A36 | §14.2 — `ดูดวง 1992-08-08 16:49 ยะลา` routes to `astro` and the answer carries Sun, Asc and the BaZi day pillar |
| A37 | §14.2 — `17/08/2538 14:30 กรุงเทพ` resolves to 1995-08-17; `2026-12-01` alone is not routed and is never evaluated as subtraction |
| A38 | §14.2 — `ค้นโน้ต …` routes to `note_search` with `scope: knowledge`, while `ค้นหา …` keeps going to the web |
| A39 | §9.5 — a project and a chat can be deleted from the UI, and a command with parameters prompts for them |
| A40 | §7.12 — `script` is a tool: write/list/read/delete/run, manifest with params, timeout enforced |
| A41 | §7.12 — every script appears in the agent catalogue as `script__<name>` and a call runs it |
| A42 | §7.12 — `op:"seed"` installs the 7 starter scripts once and never overwrites an edited one |
| A43 | §14.2 — `รันสคริปต์ tree` routes to `script_run` and returns the script's stdout |

---

## 11. Verification

| Layer | Command | Pass condition |
|---|---|---|
| backend tests | `cd backend; uv run pytest -q` | 55–75 tests green |
| backend lint | `cd backend; uv run ruff check .` | 0 issues |
| frontend types | `cd frontend; bun run check` | 0 errors |
| frontend build | `cd frontend; bun run build` | adapter-bun emits |
| astro module | `cd backend; uv run python -m tools.astro` | 4-system JSON, exit 0 |
| health | `curl 127.0.0.1:8000/api/health` | 11 tool ids, `llm:"disabled"` |
| independence | `grep -ri worakrit backend frontend` | no matches |

Test files (19):

```text
test_health.py        test_projects.py      test_chats.py
test_chat_turn.py     test_chat_paging.py   test_knowledge_fts.py
test_commands.py      test_tools_fs.py      test_tools_shell.py
test_tools_code.py    test_tools_search.py  test_calc_z3.py
test_astro_fixtures.py test_providers.py    test_agent_no_llm.py
test_learning.py      test_patterns.py      test_pipe.py
test_project_tool.py
```

Pipe cases are table-driven in `test_pipe.py`: every row of §14.6 is one parametrised case, asserting
`intent`, `rule_id`, the tool chain, and (for math) the exact answer.

Frontend has no unit tests; `bun run check` (types + a11y) and `bun run build` are the gate, and
A3/A18 are checked in a browser at 360/768/1440.

Astro fixtures (`backend/tests/fixtures/`): three pinned inputs — `2000-01-01 12:00 UTC` (J2000),
`1992-08-08 16:49 ยะลา`, `17/08/2538 14:30 Bangkok` — asserted two ways: (a) the full pinned JSON
(regression), (b) three independent constants: Sun longitude at J2000 `280.3689 ± 0.01`, Lahiri
ayanamsa in 2000 `≈ 23.85° ± 0.05`, and พ.ศ. 2538 resolving to 1995-08-17 (correctness, not just
stability).

---

## 12. Decisions log (why these, not others)

| Decision | Reason |
|---|---|
| Direct browser → backend | one hop, one error model, no duplicated API surface |
| Two processes in prod | `adapter-bun` produces a server, not static files; uvicorn cannot host it |
| No auth | loopback only, single user. Consequence stated in §13: any local process can call `:8000` |
| Approval state in SQLite rows | survives the request, no in-memory registry, matches principle 4 |
| No SSR of data | one data path in dev and prod; skeleton on first paint is accepted |
| `commands` run through `shell` | one sandbox, one allowlist, one audit trail |
| `tool_calls` without FK | audit must survive chat deletion |
| Audit truncated, response whole | a chart cut at 8 KiB is useless; the DB copy is a preview |
| Theme toggle verified before writing | Tailwind 4 `@custom-variant` is not in the reference, so the installed build is checked first |
| Brave adapter researched before coding | no web-search contract is in `references/`; guessing an endpoint is forbidden |
| Pipe before LLM | most personal turns are math, search, scaffold or verify; routing them offline is faster and works with no key |
| Rules in YAML, not Python | the owner adds an intent without a code change; `/pipe/reload` applies it live |
| `rationalize` in `calc` | measured: plain `parse_expr` gives `0.690000000000001` for `9.8-9.11` |
| Grid scan after `solve` | measured: `solve` returns branches `solve` alone does not rank; the scan produced `1.150824821` independently |
| Learning is deterministic | LLM is optional, so distillation and recall must work with zero providers |
| Patterns are text, never auto-run | a memory that can act on its own is an unreviewable control path |
| Feedback changes ranking only | one bad verdict must not delete what was learned |
| `tool_calls.run_id` | a run owns its calls explicitly instead of joining on timestamps |
| Promoted pattern lands in project instructions | durable learning goes through the same text the agent already reads |

---

## 13. Non-goals (entire project, owner-approved)

**Confirmed by the owner:** no multi-user, no cloud, no mobile, no voice.

Multi-user, login, roles, sharing, cloud or hosted deploy, mobile native app, vector RAG, voice input,
image generation, TTS, plugin marketplace or third-party tool SDK, remote tools, subagents, todo tool,
skills loader, worakrit's intent/planner/execution/verify pipe, training or fine-tuning.

What is **in** and often mistaken for a non-goal: learning (§4.10–4.13), tool approval inside agent
runs (§6), theme toggle (§9.4), message pagination (§5.3), web search when configured (§7.4), and
database backup (§5.10). Those are built, not deferred.

Consequence of "no auth" that belongs here: on a shared machine, any local process can call `:8000`
and reach the tools. The system is for one owner on one machine.

---

## 14. Pipe — intent → plan → tools

The pipe is the deterministic path. Two YAML files under `data/` hold every decision; the Python code
holds only the matcher and the executor. Changing behaviour means editing YAML, not code.

### 14.1 Stages

```text
message
  → normalise (trim, collapse spaces)
  → match rules in data/intent.yaml (priority desc, first match wins)
      match   → intent + slots + confidence
      no match→ LLM agent (if a provider is enabled) else warnings:["no_route"]
  → plan = data/plan_cheat.yaml[ intent ]
  → execute steps in order through the tool layer (each audited, run_id attached)
  → render `answer` template from the step results
  → one runs row (intent_source=pipe, matched_rule=<id>)
  → distill a pattern on success (§4.11)
```

`/pipe/route` stops after the plan lookup (no execution, no audit row). `/pipe/run` and the chat
endpoints execute. `GET /pipe/rules` exposes both files; `POST /pipe/reload` re-reads them.

### 14.2 `data/intent.yaml`

```yaml
version: 1
rules:
  - id: math_solve
    intent: math_solve
    priority: 120
    when:
      all:
        - regex: '(?i)\bx\b'
      any:
        - regex: '(?i)^\s*(solve|แก้สมการ|จงแก้)'
        - regex: '='
        - regex: '\^'
    slots:
      expr: { from: message, transform: strip_question }

  - id: math_calc
    intent: math_calc
    priority: 100
    when:
      all:
        - regex: '^[\s\d.,+\-*/^()=?]+$'
        - regex: '[+\-*/^]'
    slots:
      expr: { from: message, transform: strip_eq_question }

  - id: plan
    intent: plan
    priority: 90
    when:
      any:
        - regex: '(?i)^\s*(วางแผน|ช่วยวางแผน|plan\b)'
    slots:
      goal: { from: message, transform: strip_prefix }

  - id: project_create
    intent: project_create
    priority: 95
    when:
      any:
        - regex: '(?i)^\s*(สร้างโปรเจ[คก]ต์?|new project|scaffold)'
    slots:
      name:   { from: message, transform: extract_name }
      template: { from: message, transform: extract_template, default: python }

  - id: project_verify
    intent: project_verify
    priority: 95
    when:
      any:
        - regex: '(?i)^\s*(ตรวจโปรเจ[คก]ต์?|verify project|test project)'
    slots:
      name: { from: message, transform: extract_name }

  - id: news
    intent: news
    priority: 80
    when:
      any:
        - regex: '(?i)(ข่าว|news).*(ล่าสุด|วันนี้|ล่าสุด|latest|today)'
        - regex: '(?i)^\s*(ข่าว|news)\b'
    slots:
      query: { from: message, transform: keep }

  - id: script_run
    intent: script_run
    priority: 75
    when:
      any:
        - regex: '(?i)^\s*(รันสคริปต์|รันสคริป|run script|script)\s+'
    slots:
      name: { from: message, transform: extract_name }

  - id: note_search
    intent: note_search
    priority: 70
    when:
      any:
        - regex: '(?i)^\s*(ค้นโน้ต|โน้ต|note)\s+'
    slots:
      query: { from: message, transform: strip_prefix }

  - id: search
    intent: search
    priority: 60
    when:
      any:
        - regex: '(?i)^\s*(ค้นหา|หา|search|find)(\s|$)'
    slots:
      query: { from: message, transform: strip_prefix }
```

`data/intent.yaml` and `data/plan_cheat.yaml` are the normative files; this listing is a copy kept for
review, and `GET /api/pipe/rules` returns the loaded truth.

**Rule schema (closed set).** `id`, `intent`, `priority` (int), `when.all[]`, `when.any[]`,
`slots{}`. A condition is exactly one of `regex`, `not_regex`, `contains`, `startswith`, `equals`.
A rule with neither `all` nor `any` is a config error and is rejected at load with the rule id in the
message. A slot transform is one of `keep`, `strip_prefix`, `strip_question`, `strip_eq_question`,
`extract_name`, `extract_template`, `extract_date`, `extract_time`, `extract_location`.

**Transforms (deterministic, regex only):**

| name | does |
|---|---|
| `keep` | the normalised message unchanged |
| `strip_prefix` | removes the leading trigger (`วางแผน`, `ค้นหา`, `search`, …) and one separator |
| `strip_question` | removes a trailing `?` / `=?` / `=0` and spaces |
| `strip_eq_question` | removes a trailing `=` and `?`, leaving the expression |
| `extract_name` | first token that starts with a letter after the trigger, quoted or bare |
| `extract_template` | `python` \| `static` \| `svelte` when named, else the `default` |
| `extract_date` | first `YYYY-MM-DD`, `DD/MM/YYYY` or `DD-MM-YYYY`; empty when absent |
| `extract_time` | first `H:MM` / `HH:MM:SS`; `12:00` when absent |
| `extract_location` | the text after the clock time (else after the date), trimmed; `Bangkok` when empty |

**Astro rule (priority 110).** Requires a date **and** (a chart trigger `ดูดวง|ดวง|astro|chart`
or a clock time), so `2026-12-01` alone stays unrouted while `ดูดวง 1992-08-08 16:49 ยะลา` routes.
`math_calc` carries `not_regex: '^\s*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\s*$'` so a bare date is never
evaluated as subtraction.

### 14.3 `data/plan_cheat.yaml`

```yaml
version: 1
plans:
  math_calc:
    steps:
      - tool: calc
        args: { op: eval, expr: "{{expr}}" }
    answer: "{{result}}"

  math_solve:
    steps:
      - tool: calc
        args: { op: solve, expr: "{{expr}}", var: x }
    answer: "x = {{roots}}"

  astro:
    steps:
      - tool: astro
        args:
          birth_date: "{{birth_date}}"
          birth_time: "{{birth_time}}"
          location: "{{location}}"
    answer: "{{summary}}"

  note_search:
    steps:
      - tool: search
        args: { scope: knowledge, q: "{{query}}", limit: 8 }
    answer: "{{hits}}"

  script_run:
    steps:
      - tool: script
        args: { op: run, name: "{{name}}" }
    answer: "{{stdout}}{{stderr}}"

  plan:
    steps:
      - tool: planner
        args: { goal: "{{goal}}" }
    answer: "{{steps}}"

  project_create:
    steps:
      - tool: project
        args: { op: scaffold, name: "{{name}}", template: "{{template|python}}" }
      - tool: project
        args: { op: verify, name: "{{name}}" }
    answer: "created {{path}} · checks: {{checks}}"

  project_verify:
    steps:
      - tool: project
        args: { op: verify, name: "{{name}}" }
    answer: "{{checks}}"

  news:
    steps:
      - tool: search
        args: { scope: web, q: "{{query}}", freshness: pd, limit: 8 }
    answer: "{{hits}}"

  search:
    steps:
      - tool: search
        args: { scope: web, q: "{{query}}", limit: 8 }
    answer: "{{hits}}"
```

**Plan schema.** `steps[]` of `{tool, args}`; `args` values are strings with `{{slot}}` and
`{{slot|default}}`. `answer` is a template over the step results (`result`, `path`, `checks`,
`hits`, `roots`, `steps`). A plan naming an unknown tool or an unknown slot is rejected at load
(`plan_invalid: <intent> -> <tool|slot>`), so a broken cheat sheet never reaches a request.

### 14.4 Matching and confidence

- A rule matches when every `all` condition matches (or `all` is absent) **and** at least one `any`
  condition matches (or `any` is absent).
- Winner = highest `priority`; tie → earliest in the file.
- `confidence`: `0.9` when both `all` and `any` matched, `0.7` when only `any` matched, `0.6` when
  only `all` matched. The chat path executes at `≥ 0.6`; `/pipe/route` reports the number either way.
- `explain` lists the matched conditions verbatim, so a wrong route is diagnosable without a debugger.

### 14.5 Fallback

| situation | behaviour |
|---|---|
| no rule matches, provider enabled | LLM agent, `intent_source:"llm"` |
| no rule matches, no provider | `201 {assistant_message:null, warnings:["no_route"]}`; UI suggests adding a rule |
| rule matches, plan missing | `error:"plan_missing:<intent>"` — treated as a config bug, logged |
| a step's tool fails | step result `ok:false`; remaining steps still run; `answer` shows the failure |
| step needs approval | same approval flow as §6; the pipe pauses, then continues |

### 14.6 Test matrix (these are the tests)

| input | intent | steps | expected |
|---|---|---|---|
| `9.8-9.11=?` | `math_calc` | `calc(eval)` | `exact = "69/100"`, `result = 0.69` |
| `3^x=x^9` | `math_solve` | `calc(solve)` | roots `27` and `1.150824821` |
| `วางแผน ทำระบบล็อกอิน` | `plan` | `planner` | steps ≥ 3, each with a tool |
| `สร้างโปรเจค hello` | `project_create` | `project(scaffold)` → `project(verify)` | `workspace/hello` exists, checks run |
| `ตรวจโปรเจค hello` | `project_verify` | `project(verify)` | `checks[]` with `ok` booleans |
| `ข่าวเอไอล่าสุด` | `news` | `search(web, freshness=pd)` | hits, or `web_search_not_configured` |
| `ค้นหา sympy docs` | `search` | `search(web)` | hits |
| `สวัสดี` | — | — | no match → `warnings:["no_route"]` with no provider |

Every row is one parametrised pytest case in `test_pipe.py`. Rows 1 and 2 assert exact numeric output,
not just "a route was chosen" — that is the difference between a router that works and one that
looks like it does.
