# Outworld Workbench

ระบบงานส่วนตัวในเครื่องเดียว: Projects · Chat · Tools · Knowledge · Learning
backend เป็น Python (FastAPI + SQLite) frontend เป็น SvelteKit — **LLM เป็น optional**

## Requirements

| Tool | Version |
|---|---|
| Python | 3.15.x (uv-managed) |
| uv | 0.13+ |
| Bun | 1.4+ |
| MSVC | 14.4x — ต้องมีเฉพาะครั้งแรก เพื่อ compile `pysweph` |

## Run (two processes)

```sh
# terminal 1 — backend
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# terminal 2 — frontend
cd frontend
bun install
bun run dev
```

เปิด `http://127.0.0.1:5173`

frontend เรียก backend ตรงที่ `http://127.0.0.1:8000` (ตั้งได้ด้วย `VITE_API_BASE`) และ backend
อนุญาต CORS เฉพาะ origin ของ dev (ดู `.env.example` ทั้งสองฝั่ง)

## Verify

```sh
cd backend;  uv run pytest -q          # 142 tests
cd backend;  uv run ruff check .        # 0 issues
cd frontend; bun run check              # 0 errors, 0 warnings
cd frontend; bun run build               # adapter-bun
```

## What it does

| Area | Endpoint | Note |
|---|---|---|
| Chat | `POST /api/chat/{id}` · `POST /api/chat/{id}/stream` | pipe ก่อน, LLM เป็น fallback |
| Pipe | `POST /api/pipe/route` · `POST /api/pipe/run` | intent จาก YAML, ไม่ต้องมี LLM |
| Tools | `POST /api/tools/{tool}` | 11 tools, ทุกครั้งถูก audit |
| Knowledge | `GET/POST /api/knowledge` | FTS5 (trigram) ค้นไทยได้ |
| Learning | `GET /api/learning/stats` · `GET /api/patterns` | pattern จาก run ที่สำเร็จ |
| Backup | `GET /api/backup` | snapshot ผ่าน SQLite backup API |

Tools: `fs` `shell` `code` `search` `astro` `calc` `z3` `knowledge` `memory` `project` `planner`

## Pipe (deterministic routing)

`data/intent.yaml` = กฎจับ intent, `data/plan_cheat.yaml` = tool chain ต่อ intent
แก้ YAML แล้ว `POST /api/pipe/reload` ไม่ต้องรีสตาร์ท

ตัวอย่างที่รองรับ:

```
9.8-9.11=?          → calc        → 0.69  (exact 69/100)
3^x=x^9             → calc solve  → x = 1.1508248213, 27
วางแผน ...           → planner
สร้างโปรเจค hello    → project scaffold + verify
ตรวจโปรเจค hello     → project verify
ข่าวเอไอล่าสุด        → search (web, ต้องตั้ง key)
ค้นหา ...            → search
```

## Safety

- ทุก tool ทำงานใน `workspace/` เท่านั้น — path ที่ออกนอกได้ `403`
- `shell` รันได้เฉพาะคำสั่งใน allowlist; นอกนั้นต้องอนุมัติ (token ใช้ครั้งเดียว, TTL 10 นาที)
- ไม่มี auth: server bind `127.0.0.1` สำหรับเจ้าของเครื่องคนเดียว

## Layout

```
backend/app/   config, db, sandbox, llm, agent, pipe, runner, learning, api/
backend/tools/ registry + 11 tools (astro.py คือสำเนาที่ไม่ถูกแก้)
backend/tests/ 17 ไฟล์
data/          outworld.db, settings.json, intent.yaml, plan_cheat.yaml
workspace/     พื้นที่ทำงานของ tools
frontend/src/  9 routes, 16 components, lib/{api,stream,theme,types}.ts
```
