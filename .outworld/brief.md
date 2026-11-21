# Brief: Outworld Workbench (personal agent workstation)

Status: awaiting final sign-off (intent stage).
Written 2026-11-21. Facts came from `.outworld/project.md`.

## Done

Every line is observable. The id is used by `PLAN.md`.

### Foundation

- [ ] **A1** `cd frontend && bun run check` → 0 errors; `bun run build` succeeds.
- [ ] **A2** `cd backend && uv run pytest -q` → all green on Python 3.15.2 (target: 30–50 focused
      tests, not hundreds).
- [ ] **A3** Start both processes, open `http://127.0.0.1:5173/` → app shell renders (rail + list +
      main + panel), empty state, zero console errors.
- [ ] **A4** `GET /api/health` → `{ status: "ok", python: "3.15.2", tools: [9 ids], llm: "disabled" }`.

### Data core

- [ ] **A5** Create a project → appears in the list → restart → still there.
- [ ] **A6** Create a chat inside a project → send a message with no LLM → persisted, reappears after
      reload; URL `/chat/<id>` survives refresh and back.
- [ ] **A7** Create a knowledge note → `GET /api/knowledge/search?q=<word>` returns it via SQLite
      FTS5; editing the note updates the result.

### Tools (callable from the UI with no LLM)

- [ ] **A8** fs: read + write under `workspace/`; `../../AGENTS.md` or an absolute path outside the
      root → **403**, nothing written.
- [ ] **A9** shell: `echo hi` → stdout `hi`, exit 0; a destructive command (`rm -rf`, `del /s`) →
      **409 approval_required** with a token until approved; timeout kills the process.
- [ ] **A10** code: run a Python snippet returning `6*7` → `42`; a snippet with an infinite loop is
      killed at the timeout and reported `timeout`; a JS snippet runs too if a runtime is present,
      otherwise a clear `unsupported` error.
- [ ] **A11** calc: `sympy` solves `x**2 - 4 = 0` → `[-2, 2]`; `simplify(sin(x)**2 + cos(x)**2)` → `1`.
- [ ] **A12** z3: unsatisfiable formula → `unsat`; satisfiable → `sat` with a model.
- [ ] **A13** astro: `backend/tools/astro.py` is outworld's own file (its content was taken once from
      a previous personal project) and provides the 4 systems (BaZi, Vedic, Western, Human Design),
      registered as `astro_all`. `backend/tools/registry.py` supplies the `register_tool` /
      `get_tool` / `list_tools` contract the file imports. Three pinned inputs — J2000 noon,
      `1992-08-08 16:49 ยะลา`, and `17/08/2538 14:30 Bangkok` (พ.ศ. + tz) — match fixtures committed
      in `backend/tests/fixtures/`, including `cusps[1..12]` and ASC/MC.
- [ ] **A13b** `python -m tools.astro` (the file's own `__main__` block) runs and prints the 4-system
      JSON without a traceback.
- [ ] **A14** search: local search finds knowledge notes and workspace text files; web search stays
      `disabled` unless a provider/key is configured.

### Agent + LLM (optional)

- [ ] **A15** No provider configured → UI shows `LLM: disabled`, an agent run is refused with a clear
      message, and every tool above still works manually.
- [ ] **A16** Add an OpenAI-compatible provider (base_url + model + key) → `llm: "enabled"`; one agent
      run streams tokens over SSE and performs at least one tool call, shown in the step log.
- [ ] **A17** Every tool call is written to `tool_calls` (tool, args, result, status, ms) and appears
      in the step log after restart.

### Layout

- [ ] **A18** At 360 / 768 / 1440 px nothing overflows horizontally; below 768 the rail becomes a
      drawer and the list pane becomes a sheet.
- [ ] **A19** Independence is checkable: searching `backend/` and `frontend/` for the string
      `worakrit` returns no matches, and no file in this repo points at a path outside `E:\outworld`.

### Learning (works with no LLM)

- [ ] **A20** A completed turn writes one `runs` row (intent, tool chain, outcome, duration) and it is
      visible at `/learning`.
- [ ] **A21** Repeating a successful request that used ≥ 2 tools produces exactly one pattern with
      `uses` and `success` counters, not a new row per run.
- [ ] **A22** With zero providers configured, distillation, FTS5 recall and the `/learning` page all
      work; the next prompt shows `Known patterns for similar requests:` with ≤ 3 entries.
- [ ] **A23** A `bad` verdict lowers the pattern's success rate; a pattern with `success = 0` is never
      injected into a prompt.
- [ ] **A24** `POST /patterns/{id}/promote` appends a bullet to `projects.instructions`, the next run's
      system prompt contains it, and the change is visible and reversible in the project page.
- [ ] **A25** Patterns never execute on their own; setting `enabled = 0` removes a pattern from the
      very next recall.

### Hardening (v3)

- [ ] **A35** `ok_rate` counts only turns that actually ran; an unrouted turn increments `unrouted` and
      leaves the rate at 0; `recalls_24h` counts patterns used in the last 24 hours only.
- [ ] **A36** `ดูดวง 1992-08-08 16:49 ยะลา` routes to `astro` and the answer shows Sun, Asc and the
      BaZi day pillar — the chart is reachable from chat, not only from the tool bench.
- [ ] **A37** `17/08/2538 14:30 กรุงเทพ` resolves to 1995-08-17, and `2026-12-01` alone is not routed
      (a bare date must never be evaluated as `2026-12-1`).
- [ ] **A38** `ค้นโน้ต …` searches knowledge; `ค้นหา …` still searches the web.
- [ ] **A39** A project and a chat can be deleted from the UI, and a command with parameters asks for
      them instead of running with an empty object.

## Users

One person (the owner) on this Windows machine, browser on the same machine. No accounts, no remote
users.

## Independence policy (decided)

- `E:\outworld` and `D:\worakrit` are **separate projects**. After the one-time content copy there is
  no link between them: no path, no import, no symlink, no shared venv, no shared build step.
- One-time copy: the text of `astro.py` and the 4 `.se1` assets land in this repo. From then on they
  are outworld's own files and are edited here only. `D:\worakrit` may be deleted and nothing breaks.
- No runtime or test-time read of `D:\worakrit`. Astro tests assert against fixtures committed under
  `backend/tests/fixtures/`.
- Everything else is written fresh in this repo.
- New code is written small and legible: one module per concern, no framework of frameworks, no
  generated layers.

## Constraints

- Frontend: SvelteKit 3.4.0, Svelte 5 runes, Vite 8, TypeScript 6, Tailwind v4 (no config file),
  `#lib` imports, `@lucide/svelte`. No `svelte.config.js`, no `$lib`.
- Backend: Python **3.15.2** (uv), FastAPI + uvicorn + pydantic. SQLite via stdlib `sqlite3` + FTS5.
- Astro: `pysweph` 2.10.3.6 (module `swisseph`), built from sdist once (MSVC 14.44 present), with the
  copied `.se1` files so results are Swiss-Ephemeris-grade, not Moshier.
- Tool execution stays inside `workspace/`; the repo source is outside that root.
- Server binds `127.0.0.1` only. shell/code need an approval token.
- Windows host, PowerShell shell, `bun` for JS, `uv` for Python.

## Non-goals

- Copying or extending worakrit's architecture (agent, pipe, 165 tests, remote tools, subagents,
  patterns, research recall, skills, todos).
- Multi-user, login, roles, sharing, cloud/hosted deploy.
- Mobile native app, offline PWA, push notifications.
- Embeddings / vector RAG (knowledge search is FTS5 keyword only).
- Voice, image generation, TTS.
- Plugin marketplace or third-party tool SDK.
- Editing the repo source tree through agent tools.
- Training or fine-tuning models.

## Assumptions (confirm or reject)

- **AS1** UI labels are English; Thai used for explanations and for the astro output labels (the port
  already carries Thai sign names). Dark and light themes.
- **AS2** No proxy and no BFF: the browser calls the Python backend directly. Dev: vite on `:5173`
  calls `http://127.0.0.1:8000` with CORS allowing the two `:5173` origins. Prod: `uvicorn` serves the
  built SvelteKit output on the same origin, so CORS is a no-op.
- **AS3** Delivered in phases — foundation → data core → tools → agent/LLM → layout. Green after
  every phase.
- **AS4** Chat history is text-only in v1.
- **AS5** A project owns its chats, notes, and script commands.

## Open questions

1. **Shell policy** — approval on every command, or an allowlist (`echo`, `ls`, `git status`) that
   runs without approval?
2. **Knowledge** — notes only, or also attach files (md/pdf) with text extraction?
3. **Scripts/commands** — plain parameterised shell snippets, or multi-step recipes that can call
   tools/LLM?
