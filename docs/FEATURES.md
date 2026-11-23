# Aegis — Features & Workflow (living doc)

The running reference for what Aegis is, every feature, and how the pieces work
together. Kept up to date as features land — when you add/change a feature, update
this file. (Companion: [USER_GUIDE.md](USER_GUIDE.md) = how to *use* each feature;
[../PRD.md](../PRD.md) = the original product spec.)

**Last updated:** after the two-search + multi-page dashboard work.
**Status:** Milestones 1–6 + the Jobs review page (M5.5) + dashboard rebuild — done,
77 tests passing. Hermes "smart mode" is optional (guide: [HERMES_SETUP.md](HERMES_SETUP.md)).

---

## 1. What Aegis is

A **local-first personal AI assistant for macOS**. One assistant, a set of **skills**
(the job finder is the first), persistent **memory**, and a **propose → you approve →
act** rule for anything consequential. Everything runs on your Mac — no cloud, no paid
APIs. Tuned to stay cool and spare your battery.

---

## 2. The end-to-end workflow

```
          ┌─────────────────────────────────────────────┐
  YOU ───▶│  Dashboard (4 pages, 127.0.0.1:8777)         │
          │  Home · Job Search · Model Metrics · Settings│
          └───────────────┬─────────────────────────────┘
                          │  create a task / chat / search
                          ▼
          ┌─────────────────────────────────────────────┐
          │  FastAPI backend                             │
          │   • Task manager (state machine, resumable)  │
          │   • Governor (battery/thermal/memory safety) │
          │   • Memory (remembers you across sessions)   │
          │   • Skill registry (job_finder = first skill)│
          └───────────────┬─────────────────────────────┘
                          │  one task at a time (gentle)
                          ▼
          ┌─────────────────────────────────────────────┐
          │  Model adapter  →  Qwen3 via Ollama (default)│
          │                    or Hermes (optional)      │
          └───────────────┬─────────────────────────────┘
                          ▼
              Skills do the work (e.g. job_finder calls
              the jobify repo), results land in SQLite,
              shown back on the dashboard.
```

**Typical job-search flow:**
1. On **Job Search**, hit **Find new jobs** with keywords.
2. A background task runs: model **expands** the keywords → jobify **fetches** jobs
   (US + student-level filtered) → model **analyzes** each (fit, have/missing, draft)
   → stored in the DB.
3. The governor keeps it gentle (one at a time; pauses if the Mac is hot/low battery).
4. Results appear in the ranked table (medicine-first), revealed in **tiers**.
5. You open a job → see why it fits, what you have/miss, steps, and a draft → mark
   **Applied/Skip**. Clearing a tier unlocks the next.

---

## 3. Features

### 3.1 The dashboard (4 pages)
A clean plain-HTML UI with a shared clickable header. No build step.
- **Home** — status summary (model, device, jobs, running tasks) + chat + quick links.
- **Job Search** (`/jobs`) — the job workspace (see 3.6). *Job tasks start only here.*
- **Model Metrics** (`/metrics`) — model details, memory-fit estimate, device safety.
- **Settings** (`/settings`) — model, context, RAM, KV cache, API keys.

### 3.2 Local model + adapter
- Talks to a local model via an adapter, so the backend is swappable in one setting.
- **Ollama + Qwen3 8B** by default (free, offline). **Hermes** optional "smart mode".
  **Fake** backend exists for tests only — never shows fabricated data to you.
- **Compatibility check** estimates whether your model + context fits your Mac's RAM
  (weights + KV cache + system reserve) and warns before you run.

### 3.3 Chat
Chat with the local model from Home. Remembered facts (3.7) are injected so it
"knows" you. Per-task temperature (low for analysis, higher for prose).

### 3.4 Tasks (the agent backbone)
- Objectives run as **tasks** with a state machine (`queued → running → completed`…),
  illegal transitions blocked, full event log.
- **Resumable:** state lives in SQLite; a task interrupted by shutdown re-queues and
  resumes on restart (nothing lost, nothing falsely "done").
- **One at a time**, with gentle pacing — a thermal safeguard.

### 3.5 Device safety governor (protects your hardware)
- Reads battery %, power state, thermal pressure, and memory.
- **Defers heavy work** when the Mac is warm, on low battery, or near-full-and-warm
  while plugged in (the conditions that age a battery), and when memory is tight.
- Honest scope: software can't control charging — pair with macOS Optimized/80%
  charging. Aegis just never *adds* to the harmful conditions.

### 3.6 The Jobs workspace (`/jobs`)
- **Two searches:**
  - **Search my jobs (Local)** — instant keyword filter over the DB. No network/model.
  - **Find new jobs (Public)** — background fetch: model expands keywords → jobify
    fetches (US + student-level filtered) → model analyzes → stores. Live progress line.
- **Ranked table** — medicine/medical-AI first, by fit × path. (Unranked + a "no model"
  banner if no model is running — raw matches, never fake scores.)
- **Per-job detail** — why it fits, the description, **what you have**, **what you're
  missing**, **steps to strengthen**, and a **suggested application draft to review**.
- **Tiered reveal** — top tier shows first; mark Applied/Skip; next tier unlocks when
  the current one is cleared.
- **Add a job source** (on the dashboard) — paste a Workday careers URL to register a
  company without editing config.

### 3.7 Memory (remembers you across sessions)
- Stores facts (profile/project/reference…) in SQLite; injects the relevant ones into
  each chat so the model knows you between sessions.
- You can view/add/forget memories. Honest limit: keyword recall (matches words, not
  meaning) — semantic recall is a future upgrade.

### 3.8 Self-checking
- For answers, the model **critiques its own output** against fit criteria and revises
  once if it falls short. Governor-gated (skips the extra passes if the Mac is hot).

### 3.9 The job finder (jobify integration)
- The first skill. **Imports** the standalone `jobify` repo (not copied) — jobify stays
  usable on its own. Sources: Workday (primary), Greenhouse, Lever, Arbeitnow, and
  LangSearch for company *discovery*. Filters to **US + student-level** by default.
  Read-only: it never applies or submits.

---

## 4. Architecture (code map)

```
backend/app/
  main.py              app + routes + lifespan (worker start/stop, skill loading)
  config.py            local-first config (model, context, RAM, governor thresholds)
  database.py          SQLite schema; persistent store at ~/.aegis (outside repo)
  models/              adapter: base, ollama_backend, hermes_backend, fake_backend,
                       compat (memory-fit), prompting (temps + inference lock), selfcheck
  tasks/               repository (state machine), worker (gentle, resumable)
  resources/           monitor (battery/thermal/mem) + governor (safe-to-proceed?)
  memory/              store (remember/recall/inject)
  jobs/                repository (tiered reveal) + analyzer (per-job fit detail)
  skills/              registry + job_finder (wraps jobify)
  api/                 health, chat, tasks, resources, skills, sources, memory, jobs, settings
  static/              plain-HTML dashboard (home/jobs/metrics/settings + css/js)
```

---

## 5. Milestones (status)

| # | Feature | Status |
|---|---|---|
| M1 | App shell (FastAPI + SQLite + dashboard) | ✅ |
| M2 | Model adapter + compat check + chat | ✅ |
| M3 | Task backbone + approval gate | ✅ |
| M3.5 | Battery/thermal/resource governor | �� |
| M4 | Self-checking optimization | ✅ |
| M5 | First skill: jobify | ✅ |
| M5.5 | Jobs review page (ranked + detail + tiered reveal) | ✅ |
| M6 | Persistent memory | ✅ |
| — | Dashboard rebuild (4 pages) + two-search | ✅ |
| M6+ | Hermes "smart mode" | optional — guide written |
| M7 | Polish (ongoing) | in progress |

### Known rough edges / next
- Settings page stores keys/model, but the running code still reads model/keys from
  env vars + jobify config — wiring saved settings into live config is pending.
- Keyword-based memory + company discovery are blunt (no semantic search yet).
- Task result summaries can over-state when no model is running (being tightened).
