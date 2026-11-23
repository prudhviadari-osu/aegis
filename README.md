# Aegis

A **local-first personal AI assistant for macOS**. One assistant, a set of skills
(the job finder is the first), persistent memory, and a **propose → you approve → act**
rule for anything consequential. Everything runs on your Mac — no cloud, no paid APIs.
Tuned to run cool and spare your battery.

**Status:** Milestones 1–6 + the Jobs review page + a 4-page dashboard — working, 77
tests passing. Hermes "smart mode" is optional.

## Documentation
- **[docs/FEATURES.md](docs/FEATURES.md)** — living reference: what every feature is,
  the end-to-end workflow, architecture, and milestone status. *(Kept up to date as
  features change.)*
- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** — how to actually use each feature,
  step by step, plus troubleshooting.
- **[docs/HERMES_SETUP.md](docs/HERMES_SETUP.md)** — optional Hermes "smart mode" setup.
- **[PRD.md](PRD.md)** — the original product spec.

## Quick start

```bash
# clone Aegis + jobify as siblings
cd ~/Documents/GitHub
git clone https://github.com/prudhviadari-osu/aegis.git
git clone https://github.com/prudhviadari-osu/jobify.git

cd aegis
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# optional, for real replies: install Ollama (ollama.com) then:
ollama pull qwen3:8b

# launch (good defaults for an 18 GB Mac)
AEGIS_OLLAMA_MODEL=qwen3:8b AEGIS_TARGET_CONTEXT=16000 \
AEGIS_JOBIFY_PATH=~/Documents/GitHub/jobify/jobfinder ./scripts/start.sh
```
Open **http://127.0.0.1:8777**. Stop with **Ctrl+C**. No model yet? Add
`AEGIS_MODEL_BACKEND=fake` to click around the UI.

Full setup, usage, and troubleshooting: **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**.

## ⚠ Battery note
Aegis defers heavy work when your Mac is warm or on battery — but software can't
control charging. Also enable **System Settings → Battery → Optimized Battery
Charging** (or the 80% limit). Details in the user guide.

## Tests
```bash
.venv/bin/python -m pytest backend/tests/ -q
```

## Requirements
macOS (Apple Silicon); **Python 3.12+**. Runs anywhere with Python, but the
battery/thermal governor reads macOS-specific signals (degrades gracefully elsewhere).
