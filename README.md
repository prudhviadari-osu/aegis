# Aegis

A local-first personal AI agent platform for macOS (Apple Silicon). One assistant,
a set of **skills** (the job finder is the first), persistent memory, and a
**propose → you approve → act** rule for anything consequential.

Full spec: [`PRD.md`](PRD.md).

**Status: Milestones 1–2 — done.** M1: FastAPI shell + SQLite + plain-HTML dashboard.
M2: swappable model layer (Qwen3/Ollama default, Hermes optional, fake for dry runs),
a Mac memory-compatibility check, and a working chat box. No cloud, no paid APIs,
runs entirely on your Mac.

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

## What works now (M1 + M2)
- Local web dashboard at `127.0.0.1:8777` (plain HTML + CSS, no build step).
- SQLite database that self-initializes with the full schema.
- `/api/health`, `/api/model`, `/api/chat` endpoints.
- **Chat with a local model** from the dashboard.
- **Swappable model backend** (`AEGIS_MODEL_BACKEND`): `ollama` (default), `hermes`,
  or `fake` (try the UI with no model installed).
- **Memory-compatibility check** — estimates whether your model fits your Mac's RAM
  at the target context, and warns if a model is below Hermes' 64K requirement.
- Clean startup/shutdown; all data local under `data/` (gitignored).

### Using it with a real model
```bash
# install Ollama from https://ollama.com/download, then:
ollama pull qwen3:8b
./scripts/start.sh            # open http://127.0.0.1:8777 and chat
```
Try the UI with no model: `AEGIS_MODEL_BACKEND=fake ./scripts/start.sh`.
Use Hermes once it's set up: `AEGIS_MODEL_BACKEND=hermes ./scripts/start.sh`.

### Tuned for 8B @ 64K on an 18 GB Mac
Aegis defaults make an 8B model punch above its weight and fit comfortably:
- **8-bit KV cache** (`AEGIS_KV_CACHE=q8_0`) — roughly halves context memory, so
  8B @ 64K needs ~14 GB instead of ~18 GB. Big headroom win, no noticeable quality loss.
- **Thinking mode** (`AEGIS_THINKING=true`) — the model reasons step-by-step before
  answering, which sharply improves a small model's accuracy on hard tasks.
- Set `AEGIS_RAM_GB` to your Mac's memory and the compatibility check tells you,
  before you run, whether your chosen model + context actually fits.

### Runs cool and quiet (not fast)
Aegis is tuned to keep your Mac cool rather than maximize speed — right for a
background assistant that's on a lot:
- **One inference at a time** — never two model calls at once (parallel inference is
  what pegs the chip and spins the fans). Enforced by a lock.
- **Gentle pacing** (`AEGIS_INTENSITY=gentle`) — a short rest between queued
  background tasks so work happens in relaxed bursts, not a sustained grind.
- **Per-task temperature** — low (0.2) for analysis/scoring (steadier *and* a touch
  cooler), higher for drafting prose.
- Deliberately skipped the speed tricks that generate heat (speculative decoding,
  running the model many times per answer).

## What's next (per PRD §10)
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
