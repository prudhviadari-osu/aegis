# Aegis — Personal AI Agent Platform (PRD v2, streamlined)

Local-first personal AI assistant for macOS (Apple Silicon). One agent, a set of
**skills** (job finder is the first), persistent memory, and a **propose → you
approve → act** safety rule for anything consequential.

This is a trimmed, build-ready version of the original PRD. Each section notes
**what changed and why**, so the reasoning is visible — not hidden in my head.

- **Hardware target:** MacBook Pro M3 Pro, 18 GB unified memory.
- **Rules you set, kept as hard constraints:** local-first, free, private, runs in
  the background without taking over your desktop, remembers context, and **never
  acts on anything consequential without your approval.**

---

## 0. What changed from your original PRD, and why

Your PRD is a strong vision doc. The changes below cut roughly half the day-one
build without dropping anything you care about.

| Area | Your PRD | v2 decision | Why |
|---|---|---|---|
| **Agent core** | Hermes is the mandatory core | Hermes behind an **adapter**, optional; **Qwen3-direct is the always-works default** | Hermes is young + churny (its 64K check blocks boot for many); don't bet the platform on it. You still get Hermes as "smart mode." |
| **Frontend** | React + TS + Vite + Tailwind + shadcn | **Plain HTML + a little CSS**, served by FastAPI | You asked for exactly this. Far less to build; upgrade later only if needed. |
| **Skill registry** | Custom registry + lifecycle | Start with a **simple skills folder + a Python interface**; adopt Hermes `SKILL.md` when Hermes is on | Don't duplicate what Hermes provides; don't over-build before you have 3+ skills. |
| **Memory** | Custom 5-category memory system | **SQLite memory table** (your §9 model) + use Hermes' native memory when on | One lean store now; the 5 categories become tags, not subsystems. |
| **Resource governor** | Full governor: profiles, battery, memory-pressure | v1: **inference one-at-a-time, one browser, skip heavy work when RAM is tight**; full governor later | 18GB is tight, but the simple rules cover 90% of the risk. |
| **MCP / Alembic / APScheduler / Playwright** | Day-one stack | **Deferred** until a skill needs them | Add infrastructure when there's a concrete need, not before. |
| **jobify** | A skill to be built | **Integrate the existing `jobify` repo as the first skill** | It's already a clean, tested module with the right interface. |

Everything cut is **deferred, not deleted** — it moves to "later phases."

---

## 1. Architecture (streamlined)

```
            YOU
             │
             ▼
   Plain-HTML dashboard  ◄── served by ──┐
             │                            │
             ▼                            │
   ┌─────────────────────────────────────┴───────┐
   │             FastAPI backend                   │
   │   task manager · approvals · memory · skills  │
   └───────────────┬───────────────────────────────┘
                   │
            ┌──────▼───────┐   swappable
            │ ModelAdapter │   (interface)
            └──────┬───────┘
         ┌─────────┴──────────┐
         ▼                    ▼
   Qwen3 via Ollama      Hermes Agent
   (DEFAULT, always      (OPTIONAL "smart mode":
    works)                learning loop, skills, memory)
                   │
                   ▼
         Skills (job-finder first) · SQLite · filesystem
```

**The key principle (from your §4.2, kept):** the *model/agent* decides HOW to do a
task; **Aegis decides whether it's allowed, when it runs, and whether it needs your
approval.** Those guardrails live in Aegis, never in the model.

**Why the adapter matters:** `jobify` already proved this exact pattern — a
`ModelClient` interface with an Ollama backend and a fake backend for tests. Aegis's
`ModelAdapter` is the same idea, with Qwen3-direct and Hermes as two backends.

---

## 2. Tech stack (trimmed)

| Layer | Choice | Note |
|---|---|---|
| Backend | Python 3.12 + FastAPI | business logic separated from routes |
| Frontend | **Plain HTML + CSS** (served by FastAPI) | no React/build step |
| Database | SQLite (WAL, foreign keys) | single source of truth |
| DB access | sqlite3 stdlib or SQLAlchemy | start simple; SQLAlchemy only if models grow |
| Model (default) | Ollama + `qwen3:8b` | reuse jobify's `llm/` interface |
| Model (optional) | Hermes Agent | behind the same adapter, "smart mode" |
| First skill | the `jobify` repo | job discovery + application prep |
| Tests | pytest | mock the model; no live model needed for tests |
| Deferred | Playwright, MCP, Alembic, APScheduler, React | add when a milestone needs them |

No Docker, no cloud, no paid APIs — same as your original.

---

## 3. Data model (SQLite — kept from your §9, lean)

```
Task(id, title, description, status, priority, skill, created_at, updated_at,
     started_at, completed_at, checkpoint, result, error)
  status: created → pending_approval → queued → running → waiting_input
          → paused → completed | failed | cancelled

TaskEvent(id, task_id, type, timestamp, details)     -- execution log

Approval(id, task_id, action, description, status, requested_at, resolved_at)
  -- the propose→approve→act gate; nothing consequential runs without a resolved row

Memory(id, category, content, source, confidence, created_at, updated_at)
  -- category is a TAG: profile | project | task | reference | procedural

Skill(id, name, description, path, enabled, version)

Setting(key, value, updated_at)
```

**A task is never "done" just because a model call returned.** Completion is an
explicit state with a stored result — so interrupted work resumes safely (your §4.3).

---

## 4. The approval gate (your non-negotiable, made concrete)

Three permission levels, exactly your §7.2:

- **Observe** — search, read approved files, analyze, report. No approval needed.
- **Prepare** — draft responses, fill a form in an isolated browser, organize files
  in approved dirs. Produces something for you to review. No approval to *prepare*.
- **Execute** — submit an application, send an email, delete files, change settings.
  **Always requires a resolved `Approval` row.** Aegis texts/notifies you first; you
  approve in the dashboard; only then does it act.

Default posture: **Aegis suggests and prepares; you approve before any action.**
Job applications are never auto-submitted (same rule jobify already enforces).

---

## 5. Skills

A skill is a self-contained capability Aegis can run. v1 skill interface (simple):
a Python module exposing `run(task, context) -> result` plus a small manifest
(name, description, permission level, inputs/outputs). When Hermes "smart mode" is
on, skills can also be exposed as Hermes `SKILL.md` skills.

**Planned skills (your list), in priority order:**
1. **Job finder** (integrate `jobify`) — discovery + fit-ranking + application prep.
2. **Research** — search, extract, summarize, save findings locally.
3. **Learn++ items** — study scheduling / lesson tracking (ties into your lesson-engine world).
4. **Calendar** — read/suggest schedule (read-first; events are Execute-level).
5. **Email** (maybe) — summarize/draft; sending is Execute-level.
6. **Habit tracking** — log + nudge toward goals.

Only #1 ships in the MVP. The rest are stubs with the same interface.

---

## 6. Resource rules for 18 GB (v1 — simple, honest)

Not the full governor yet. v1 rules that cover the real risk:
- **One model inference at a time** (no concurrent LLM calls).
- **One browser context at a time** (when browser skills exist).
- **Check free memory before heavy work**; if RAM is tight, queue instead of run.
- **Qwen3 8B at the context Hermes needs (64K) is tight on 18GB** — the model
  compatibility check (below) reports the real numbers before anything runs.

**Model compatibility check (kept from your §3.3):** before using a model, report
its params, quantization, context window, estimated weights + KV-cache memory, and a
pass/fail for the 18GB budget. If nothing fits reliably at 64K, **say so plainly** —
don't silently drop context or reach for a paid cloud model.

---

## 7. Background execution (your §5.6, kept)

- Manually launched and stopped (no always-on daemon).
- Headless work only — **never** moves your cursor, types into your apps, or touches
  your primary browser/desktop.
- On stop: refuse new tasks, interrupt workers, save checkpoints, close browsers,
  persist DB, exit clean.
- The dashboard is a control panel; the backend keeps working when it's closed.

---

## 8. Dashboard (plain HTML)

One local page at `127.0.0.1`, server-rendered, minimal CSS:
- **Status:** agent/model, current backend (Qwen3 or Hermes), rough memory use.
- **Chat box:** submit a natural-language objective.
- **Tasks:** list with status, pause/cancel/resume, and the execution log.
- **Approvals:** pending items with approve/reject.
- **Memory:** view/edit/delete stored context.
- **Settings:** model, backend toggle, data dirs, permission defaults.

No React, no build step — FastAPI returns HTML; a little vanilla JS for the chat
stream and button actions.

---

## 9. Security (your §7, kept)

Bind to `127.0.0.1` only; never expose publicly. Secrets in macOS Keychain, never in
logs. Validate file paths; restrict filesystem to approved directories. Isolated
browser profile. Audit trail of consequential actions. No unrestricted shell/FS/
browser access by default.

---

## 10. Milestones (resequenced for a useful-early slice)

Each milestone ends with a **working app.**

- **M1 — Shell.** FastAPI + SQLite + plain-HTML dashboard + start/stop scripts +
  health check + config. *Done when:* app launches, dashboard loads, DB self-inits,
  clean shutdown, zero cloud deps.
- **M2 — Model path.** `ModelAdapter` with Qwen3/Ollama default (reuse jobify `llm/`)
  + the compatibility check + a chat endpoint. *Done when:* you chat with a local
  model from the dashboard; no paid endpoint is ever silently used.
- **M3 — Tasks + approvals.** Task lifecycle, queue, worker, checkpoints, the
  Approval gate. *Done when:* you submit an objective, it runs as a task, interrupting
  it keeps progress, Execute-level actions block on approval.
- **M3.5 — Battery/thermal/resource safety layer (NEW, user priority).** A
  self-governor that protects the user's hardware investment. The user saw real
  battery degradation (93% → 86%) from sustained training load, and the main culprit
  is **sustained heat + high charge**, not one-off hard use. Aegis monitors battery
  %, charging state, thermal pressure, and memory, and voluntarily backs off *before*
  it adds to those conditions: pause heavy work when hot; throttle on battery power;
  avoid holding the battery hot at ~100% while plugged in; enforce relaxed bursts with
  long cooldown rests; cap daily heavy compute. **Honest scope:** software cannot
  control charging or physically protect hardware (macOS does), so the promise is
  "Aegis never contributes to the sustained-heat conditions that age the battery" —
  paired with the user enabling macOS Optimized/Limited Charging. *Done when:* under
  simulated hot/on-battery/high-charge conditions, the worker defers work and resumes
  when conditions clear; the dashboard surfaces battery + thermal state.
- **M4 — Self-checking optimization (ORIGINAL plan, kept).** The model verifies its
  own work (self-critique/validation of outputs) and consults a "safe to proceed?"
  gate before acting. Builds on M3.5's governor. *Done when:* the model can catch and
  revise its own bad output, and won't act when the governor says conditions are unsafe.
- **M5 — First skill = jobify.** Integrate the job finder as a callable skill.
  *Done when:* "find me medtech jobs" runs jobify and results land in the dashboard/sheet.
- **M6 — Hermes smart mode + memory.** Hermes as a second backend (64K-gated) +
  persistent context. *Done when:* you can toggle Hermes on and it works, Aegis still
  runs with it off, and it recalls prior context.
- **M7 — Polish.** Approval UX, resource visualization, docs, tests.

**First deliverable:** M1 — the shell. Build the foundation before any skill.

**Progress:** M1 (shell) and M2 (model layer: Qwen3/Ollama default, Hermes optional,
fake backend, compatibility check, chat endpoint + dashboard) are **built and tested.**

---

## 11. Non-goals for MVP (your §11, kept)

No custom LLM/training, no custom agent loop, no always-on daemon, no cloud, no
mobile, no voice, no desktop computer-vision control, no auto-submit of applications,
no paid APIs, no vector DB, no Docker. Deferred, reconsidered later.

---

## 12. Definition of success (your §13, kept)

Launch locally → talk to a local model → give it an objective → it breaks it into
steps → runs approved work → you watch in the dashboard → you keep using your Mac →
pause/cancel/resume → shut down without losing state → restart and recover. It should
feel like **one assistant**, with the job finder as its first real skill.
