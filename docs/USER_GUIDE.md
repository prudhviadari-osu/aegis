# Aegis — User Guide (how to use it)

Practical, step-by-step how-to for each feature. (Companion:
[FEATURES.md](FEATURES.md) = what each feature is and how it works internally.)

---

## 0. First-time setup

```bash
# clone both repos as siblings
cd ~/Documents/GitHub
git clone https://github.com/prudhviadari-osu/aegis.git
git clone https://github.com/prudhviadari-osu/jobify.git

# set up Aegis (Python 3.12+)
cd aegis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# (optional, for real model replies) install Ollama + pull the model
#   https://ollama.com/download
ollama pull qwen3:8b
```

**Launch** (recommended settings for an 18 GB Mac):
```bash
cd ~/Documents/GitHub/aegis
source .venv/bin/activate
AEGIS_OLLAMA_MODEL=qwen3:8b \
AEGIS_TARGET_CONTEXT=16000 \
AEGIS_JOBIFY_PATH=~/Documents/GitHub/jobify/jobfinder \
./scripts/start.sh
```
Open **http://127.0.0.1:8777**. Stop with **Ctrl+C** (exits within ~3s).

> No model installed yet? Launch with `AEGIS_MODEL_BACKEND=fake` to click around the
> UI (you'll see a "no model" state — no real answers or fake scores).

---

## 1. Home

The landing page shows live status — model, device (battery/thermal), job count,
running tasks — and a **chat box**. Type a question, get a reply from your local model.
Aegis folds in anything it remembers about you (see §5).

---

## 2. Job Search (`/jobs`) — the main workspace

### Find new jobs (the real search)
1. In the **🌐 Find new jobs** box, type comma-separated keywords, e.g.
   `intern, biomedical, clinical research`. (Blank = your default keywords.)
2. Hit **Find**. A background search starts — it can take a few minutes.
3. Watch the **progress line** (“⏳ Search running… (scoring 12/37)”). The table fills
   live; you don't have to wait on a frozen screen.
4. What happens under the hood: the model expands your keywords → jobify fetches jobs
   (filtered to **US + student-level**) → the model analyzes each → they're stored and
   ranked (medicine/medical-AI first).

### Search my jobs (instant)
Use the **🔎 Search my jobs** box to filter what's *already been found* — no network,
no waiting. Great for "find that job from earlier." Clear the box and press Filter to
return to the full ranked view.

### Reviewing a match
Click any row to open its detail panel:
- **Why it fits** + fit/path scores + **ring** (medicine / medical-AI / tech / off-path).
- The **job description** and a link to the posting.
- **What you have**, **what you're missing**, and **steps to strengthen** your app.
- A **suggested submission draft** — review/edit it; it's never sent for you.
- **Mark applied / Skip.** When every job in the current tier is marked, the **next
  tier unlocks** (so you work through the best matches first).

### Add a job source
On the dashboard **Add a job source** box, paste a company's Workday careers URL
(e.g. `https://medtronic.wd1.myworkdayjobs.com/MedtronicCareers`). It's registered and
searched on the next run — no config editing.

> **Jobs not showing?** Use **Search my jobs** with a blank/common term to check the
> DB. If it's empty, your last public search found 0 that passed the US + student-level
> filter — try broader keywords, or add a job source. If the progress line is still
> running, just wait.

---

## 3. Model Metrics (`/metrics`)

At-a-glance tiles:
- **Model** — backend, model name, whether it's running, and estimated memory vs. your
  RAM. If it says "tight," close apps or lower the context in Settings.
- **Device safety** — battery %, power, thermal, memory, and whether Aegis is OK to
  work or holding off (with the reason). This is the governor protecting your hardware.

---

## 4. Settings (`/settings`)

Edit and **Save** each field (secrets show "••• set" once saved and are never shown
back; leave a key blank to keep the current one):
- **Model** (e.g. `qwen3:8b` or `qwen3:4b` for a lighter/faster run)
- **Context window**, **Mac RAM (GB)**, **KV cache** (`q8_0` recommended on 18 GB)
- **LangSearch API key** (free, company discovery), **Adzuna** keys (optional)

> Note: today, model/context/keys are read from the launch environment + jobify's
> config; the Settings page stores them for a pending wiring step. For now, set the
> model/context via the launch command (§0) and keys in jobify's config.

---

## 5. Chat memory — making Aegis remember you

Aegis remembers facts across sessions.
- It auto-uses stored **profile** facts in every chat.
- Add a memory via the API: `POST /api/memory {"content":"I prefer remote roles","category":"profile"}`
  (a dashboard memory box is on the roadmap).
- Recall is keyword-based, so phrase memories with words you'd naturally search.

---

## 6. Keeping your battery healthy

Aegis is tuned to run cool and defer work when your Mac is warm or on battery — but
**software can't control charging.** Also turn on, in **System Settings → Battery**:
**Optimized Battery Charging** (or the **80% limit**). Aegis limits its load; macOS
limits the charge; together they spare the battery.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'finder'` (jobify) | `cd` into `jobify/jobfinder` (the code is one level in) |
| Install fails, "multiple top-level packages" | fixed — `git pull`; it declares `backend` explicitly now |
| Ctrl+C hangs | fixed — now exits within ~3s; state is saved and resumes next launch |
| Jobs page empty | see the box in §2 — usually "0 passed filters" or still running |
| Model "not running" | start Ollama and `ollama pull qwen3:8b`; check `ollama list` |
| Mac struggles / fans spin | lower `AEGIS_TARGET_CONTEXT` (e.g. 8000), ensure 8-bit KV cache on, close Chrome tabs, or use `qwen3:4b` |
| "no model used" banner on Jobs | expected with no model — raw matches, not analyzed; start Ollama and re-run |

Read the terminal where Aegis runs — real errors print there (last line names the cause).
