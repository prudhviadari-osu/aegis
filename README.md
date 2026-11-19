# Aegis

A local-first personal AI agent platform for macOS (Apple Silicon). One assistant,
a set of **skills** (the job finder is the first), persistent memory, and a
**propose → you approve → act** rule for anything consequential.

Full spec: [`PRD.md`](PRD.md).

**Status: Milestones 1–6 + the Jobs review page (M5.5) — done.** M1: shell. M2: model layer + Mac memory-fit check
+ chat. M3: task backbone (resumable tasks, gentle pacing, approval gate). M3.5:
battery/thermal/resource governor. M4: self-checking (governor-gated). M5: first real
skill — the `jobify` job finder. **M6: persistent memory — Aegis remembers you across
sessions (stored locally, injected into chat), no Hermes or 64K strain needed.** No
cloud, no paid APIs, runs entirely on your Mac.

### Memory (M6)
Aegis stores facts about you in SQLite and injects the relevant ones into each reply,
so it remembers you between sessions. Add/view/forget memories on the dashboard's
Memory card, or via `/api/memory`. **Honest limit:** recall is keyword-based (local,
no vector DB) — it matches shared words, not meaning, so phrase memories with words
you'd search for. Semantic recall (e.g. an embedding model) is a possible future upgrade.

### The Jobs page (`/jobs`) — your job-match review workspace
Run a `job_finder` task, then open **http://127.0.0.1:8777/jobs**:
```bash
AEGIS_JOBIFY_PATH=/path/to/jobfinder ./scripts/start.sh
# dashboard → add a task with skill "job_finder" (description = keywords)
```
The skill searches (US + student-level filtered), stores jobs in Aegis's DB, and the
model analyzes each one. The `/jobs` page then shows:
- **A ranked table** (medicine/medical-AI first, by fit × path).
- **Click a job → a detail panel**: why it fits, the description, **what you have**,
  **what you're missing**, **steps to strengthen your application**, and a **suggested
  submission draft to review** (never auto-sent).
- **Tiered reveal:** only the top tier shows first; mark each **Applied/Skip**, and the
  next tier unlocks when the current one is cleared.

Scoring is one job at a time and governor-gated, so a big batch stays cool — the page
updates live as jobs finish analyzing.

## ⚠️ Protecting your battery (read this)
Aegis is tuned to avoid the conditions that age a laptop battery — **sustained heat
and holding a hot battery at full charge** (the main culprits, worse than one-off hard
use). Its governor automatically defers heavy work when your Mac is warm, on low
battery, or near-full-and-warm while plugged in. It trades speed for gentleness on
purpose.

**But software can't control charging — that's macOS's job.** For real battery
protection, also turn on, in **System Settings → Battery**:
- **Optimized Battery Charging** (or, on supported Macs, the **80% charge limit**).

Aegis limiting its load + macOS limiting the charge = the two halves of sparing your
battery. Aegis does the first; please enable the second.

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

**Setting up Hermes "smart mode"?** Follow [`docs/HERMES_SETUP.md`](docs/HERMES_SETUP.md)
— a Mac-specific, step-by-step guide (Qwen3 8B at 64K with an 8-bit KV cache, tuned
for 18 GB). The critical step most people miss: Hermes requires a 64K-context model,
so you must create a `qwen3-8b-64k` Ollama variant first — the guide walks through it.

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
- **Hermes "smart mode"** (optional) — the self-improving agent loop + built-in
  skills, when you want autonomous multi-step work. Setup guide:
  [`docs/HERMES_SETUP.md`](docs/HERMES_SETUP.md). (Heavier: forces 64K context.)
- **M7** — polish.

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
