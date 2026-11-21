# Project facts — outworld

Generated 2026-11-21 from this machine. Every version below was queried from a registry or
actually installed and imported. Nothing here is remembered.

## Repository

- Path: `E:\outworld`
- Git: yes, 1 commit (`0e800ef Create README.md`)
- Contents: `README.md`, `AGENTS.md` — **no `package.json`, no code yet**

## Runtimes (verified on this machine)

| Tool | Version | Note |
|---|---|---|
| Node | v26.13.0 | |
| Bun | 1.4.4 | use this. `npm.ps1` is blocked by PowerShell ExecutionPolicy |
| uv | 0.13.8 | manages the Python venv |
| Python | **3.15.2** | target interpreter — full stack verified on it |
| Python (uv) | 3.13.18 | fallback only (prebuilt `pysweph` wheel) |
| MSVC | 14.44.35207 (VS 2022 Community) | `cl.exe` present; required to build `pysweph` |

## Swiss Ephemeris decision (measured)

`pysweph` is a maintained fork of `pyswisseph`. It ships wheels for cp38–cp313, and the sdist
**builds cleanly on Python 3.15.2** with the installed MSVC. Verified 2026-11-21:

```
Python 3.15.2 (MSC v.1951 64 bit)
swisseph.cp315-win_amd64.pyd   771 KB, built by setuptools 84.2.1
sun longitude at J2000      = 280.3689   (reference ~280.37)
moon longitude at J2000     = 223.3238
swe.houses(jd, lat, lon,'P') returns 13 cusps + ascmc
```

| Package | Latest | Windows wheels | Verdict |
|---|---|---|---|
| `pysweph` (fork) | 2.10.3.6 | cp38–cp313, sdist builds on 3.15 | **chosen** |
| `pyswisseph` (original) | 2.10.3.2 (2023-06) | cp36–cp311 only | rejected, unmaintained |
| `kerykeion` | 6.1.0 | wraps `pyswisseph` | rejected |
| `flatlib` | 0.2.3 | pins `pyswisseph==2.08.00-1` | rejected |
| `immanuel` | 1.8.0 | wraps `pysweph` | rejected |
| `ephem` | 4.2.1 | cp38–cp314, no houses | rejected |
| `skyfield` | 1.55 | pure, no houses | fallback only |

API details to remember:

- module name is `swisseph`, not `pysweph`
- `swe.houses()` returns `cusps` with a **dummy `cusps[0]`**; real houses are `cusps[1..12]`
- `ascmc[0]` = Ascendant, `ascmc[1]` = Midheaven

## Full backend stack, installed and imported on Python 3.15.2

```
python    3.15.2        fastapi   0.165.0     uvicorn   0.54.0
pydantic  2.14.4        httpx     0.28.1      sympy     1.14.0
z3        5.4.1         swisseph  2.10.03     sqlite    3.53.1
FTS5      create virtual table ... using fts5(x) + match  -> OK
```

## Package versions (registry check, 2026-11-21)

Frontend:

- `@sveltejs/kit` 3.4.0
- `svelte` 5.59.1
- `vite` 8.3.8
- `typescript` 6.x — **not 7**, Kit 3 needs the 6.x compiler API

## Commands (created by the plan)

```sh
# frontend
cd frontend
bun install
bun run dev          # vite dev
bun run check        # svelte-kit sync && svelte-check
bun run build        # bun --bun vite build

# backend
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
uv run pytest -q
```

## Hard constraints discovered, not assumed

1. `pysweph` has no cp315 wheel → the first `uv sync` compiles it from the sdist and needs MSVC
   14.44 (present). uv caches the built wheel, so later installs are fast. A machine without MSVC
   must fall back to Python 3.13 + the prebuilt cp313 wheel.
2. SvelteKit 3 removed `svelte.config.js` and `$lib`; config lives in `vite.config.ts`; aliases are
   `#lib/*` in `package.json#imports`; TypeScript must be 6.x.
3. `adapter-bun` only builds under the Bun runtime.
4. `npm` is unusable in this shell → all frontend work goes through `bun`.

## Previous project: `D:\worakrit` (separate, one-time content source)

`E:\outworld` and `D:\worakrit` are independent projects. Content was taken once and now belongs to
this repo; there is no path, import, symlink or build reference back. The A19 search check proves it,
so deleting `D:\worakrit` cannot break this repo.

- Stack of that project: `requires-python = ">=3.15"`, `pysweph>=2.10.3.6`, SvelteKit 3 +
  adapter-bun + Tailwind 4 + TS 6.
- Size: `api.py` 445 LOC, `core/` ~1.5k, `pipe/` ~1.3k, `tools/` ~4k, frontend ~20 components,
  **165 tests**.
- Tool contract there: `@register_tool(name=..., description=...)` in `tools/registry.py`; tools return
  `{ok, data, meta, error}`. This repo keeps only that decorator contract, reimplemented locally.
- Content taken once: `tools/astro.py` and `data/assets/{sepl,semo}_{18,24}.se1`.
- Owner's verdict: "รก, เทสมันเยอะเกิน" — hence a separate, leaner project.
- `tools/astro.py` is self-contained: it imports `swisseph` + `tools.registry` only; `geopy` and
  `timezonefinder` are optional (inside `try`). It already carries a `sys.path` shim for standalone
  runs, so no edit is needed on copy.
