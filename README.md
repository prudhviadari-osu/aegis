# Aegis

A local-first personal AI agent platform for macOS (Apple Silicon). One assistant,
a set of **skills** (the job finder is the first), persistent memory, and a
**propose → you approve → act** rule for anything consequential.

Full spec: [`PRD.md`](PRD.md).

**Status: Milestone 1 (the shell) — done.** FastAPI backend, SQLite, a plain-HTML
dashboard, start/stop scripts, health check. No cloud, no paid APIs, runs entirely
on your Mac.

## Requirements
- macOS (Apple Silicon) — though it runs anywhere with Python
- **Python 3.12+**

## Run it

```bash
git clone https://github.com/prudhviadari-osu/aegis.git
cd aegis
./scripts/start.sh          # creates a venv, installs, launches
```

Then open **http://127.0.0.1:8777** in your browser. You'll see the status card go
"online" with the database "ready".

Stop it with `./scripts/stop.sh`, and check it with `./scripts/health_check.sh`.

### Manual run (without the script)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m backend.app.main
```

## Tests
```bash
.venv/bin/python -m pytest backend/tests/ -q
```
Covers DB init, schema, WAL/foreign-key pragmas, cascade deletes, the health
endpoint, and the dashboard — all without a model or network.

## What works now (M1)
- Local web dashboard at `127.0.0.1:8777` (plain HTML + CSS, no build step).
- SQLite database that self-initializes with the full schema (tasks, events,
  approvals, memory, skills, settings).
- `/api/health` endpoint the dashboard polls.
- Clean startup/shutdown; all data stored locally under `data/` (gitignored).

## What's next (per PRD §10)
- **M2** — local model via Ollama (Qwen3 8B) behind a swappable adapter + chat.
- **M3** — tasks, queue, worker, checkpoints, the approval gate.
- **M4** — first skill: integrate the `jobify` job finder.
- **M5** — Hermes "smart mode" as an optional second backend.
- **M6–M7** — memory, a second skill, polish.

## Layout
```
aegis/
├── PRD.md                  # product spec (v2, streamlined)
├── pyproject.toml
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app + lifespan (M1)
│   │   ├── config.py       # local-first config
│   │   ├── database.py     # SQLite schema + connection
│   │   ├── api/health.py   # /api/health
│   │   └── static/         # plain-HTML dashboard
│   └── tests/
├── scripts/                # start / stop / health_check
└── data/                   # local runtime data (gitignored)
```
