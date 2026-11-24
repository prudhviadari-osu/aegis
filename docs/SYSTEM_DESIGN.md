# System Design — how Aegis, jobify, and aegis-browser fit together

The bird's-eye view of the whole system: three repos, clear responsibilities, and
how they connect. (Per-repo detail lives in each repo's README + docs; this is the
map showing the parts working together.)

---

## The three repos

| Repo | Role | Knows about… |
|---|---|---|
| **aegis** | The **brain + environment**. Orchestrates skills, runs the dashboard, owns tasks/memory/governor/model. | generic agent concerns — *not* any domain |
| **jobify** | A **domain skill: jobs**. Finds jobs, filters, ranks, and owns application **prep** (requirements + drafting). | everything job-specific (Workday, filters, fit) |
| **aegis-browser** | A **shared capability**: a general, headless Playwright wrapper (read public pages) + the fill-and-review extension. | how to drive a browser — *not* any domain |

Future skills (e.g. **learn++** for studying) slot in beside jobify as separate
domain repos, using the same pattern.

---

## How they connect

```
                       ┌──────────────────────────────────────┐
                       │                AEGIS                  │
                       │  brain + environment                  │
                       │  • dashboard (Home/Jobs/Tasks/…)      │
                       │  • tasks, queue, worker (resumable)   │
                       │  • governor (battery/thermal safety)  │
                       │  • memory (remembers you)             │
                       │  • model adapter (Qwen3 / Hermes)     │
                       │  • skill registry                     │
                       └───────┬───────────────────┬───────────┘
                               │ runs as a skill    │ uses directly
                               ▼                    ▼
                  ┌─────────────────────┐   ┌─────────────────────┐
                  │   jobify (skill)    │   │   aegis-browser     │
                  │  job search + rank  │   │  general headless   │
                  │  + application prep │──▶│  browser wrapper    │
                  │                     │uses│  (Playwright)       │
                  └─────────────────────┘   │  + fill extension   │
                                            └─────────────────────┘
      Aegis imports jobify as a skill.   Both jobify and Aegis can call
      jobify imports aegis-browser for   aegis-browser; it stays domain-agnostic.
      reading application pages.
```

**Dependency direction (important):** Aegis → jobify → aegis-browser, and Aegis →
aegis-browser directly. Nothing points back up: jobify doesn't know about Aegis's
internals; aegis-browser knows about neither. That's what keeps them cleanly separable.

---

## A job, end to end (which repo does what)

1. **You** (in Aegis's dashboard) start a job search. — *aegis*
2. The **worker** runs the `job_finder` skill, gently and resumably. — *aegis*
3. jobify **fetches** jobs from public APIs (Workday/Greenhouse/Lever JSON),
   filters to US + student-level, and ranks them with the model. — *jobify*
   (model provided by *aegis*)
4. For a job you want, jobify **gathers application requirements** by reading the
   job's public page — *jobify* calling *aegis-browser*.
5. jobify **drafts** the application from your profile + those requirements. — *jobify*
6. Aegis shows it on the **/jobs** review page (ranked, have/missing, draft). — *aegis*
7. When you apply, the **extension** fills the live form in your real browser; **you
   review and submit.** — *aegis-browser (extension)*, you

The **governor** (aegis) keeps all heavy steps gentle on your Mac; **memory** (aegis)
keeps context across sessions. Neither is job-specific.

---

## A non-job task, end to end (why the split pays off)

1. You ask Aegis to research a topic. — *aegis*
2. Aegis uses **aegis-browser** to read relevant public pages. — *aegis → aegis-browser*
3. Aegis summarizes with the local model and (optionally) saves to memory. — *aegis*

No jobify involved — because browsing is a general capability, not a job thing. That's
the whole reason aegis-browser is separate from jobify.

---

## Safety boundaries (hold across all repos)

- **Headless = public-page reading only.** No login, no form-fill, no submit.
- **The fill-and-review extension** is the only thing that touches a live
  application form — in *your* real session, *you* review and submit.
- **Local-first:** your data stays in `~/.aegis`; the local model keeps resume
  analysis on your machine.
- **Propose → you approve → act** for anything consequential.

---

## Status
- **aegis** — M1–M6 + dashboard + Tasks page. Working.
- **jobify** — search/filter/rank working; application **prep** (via aegis-browser)
  is the next build.
- **aegis-browser** — designed (`aegis-browser/DESIGN.md`); build starts with the
  headless wrapper, then jobify's prep, then the extension.
