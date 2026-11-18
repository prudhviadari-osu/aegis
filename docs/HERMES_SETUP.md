# Hermes "smart mode" setup (macOS, 18 GB M3 Pro)

This connects **Hermes Agent** (Nous Research's self-improving agent) to Aegis, using
your **local Ollama Qwen3 8B** at the 64K context Hermes needs — tuned for an 18 GB
Mac. Everything stays local and free.

> **Mental model:** Ollama runs the model. Hermes wraps it with the agent loop,
> skills, and memory. Aegis points at Hermes instead of at Ollama directly. You are
> not replacing Ollama — Hermes *uses* it.

Based on the official Nous guide (nousresearch.com → Run Hermes Locally with Ollama),
adapted for your hardware. *Content rephrased for compliance.*

---

## The one gotcha that breaks most setups

Ollama defaults to a tiny context (~2K tokens). **Hermes refuses to start with any
model under 64,000 tokens** and checks at launch. So you cannot point Hermes at plain
`qwen3:8b` — you must first create a 64K variant (Step 2). Skip that and Hermes won't
boot.

---

## Before you start — turn on battery protection

You saw real battery wear from sustained load. Hermes at 64K is a heavier, longer-
running workload, so **first**: System Settings → Battery → enable **Optimized Battery
Charging** (or the **80% limit** if your Mac has it). Aegis's governor handles its own
load; this handles the charging half it can't control.

---

## Step 1 — Ollama + Qwen3 (you likely did this already)

```bash
# install Ollama (if not already):
curl -fsSL https://ollama.com/install.sh | sh
ollama --version

# pull the model:
ollama pull qwen3:8b

# confirm it responds:
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Say hello"}],"max_tokens":20}'
```

---

## Step 2 — Make a 64K context variant (THE critical step)

Create an Ollama "Modelfile" that bakes in the 64K context Hermes requires, plus the
8-bit KV cache that keeps it fitting in 18 GB (≈14 GB instead of ≈18 GB):

```bash
mkdir -p ~/aegis-models
cat > ~/aegis-models/Modelfile <<'EOF'
FROM qwen3:8b
PARAMETER num_ctx 64000
EOF

ollama create qwen3-8b-64k -f ~/aegis-models/Modelfile
```

Enable the 8-bit KV cache (halves the context memory — this is what makes 64K fit on
18 GB). Set it for the Ollama service and restart it:

```bash
# tell Ollama to use an 8-bit KV cache + flash attention
launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0
launchctl setenv OLLAMA_FLASH_ATTENTION 1
# restart Ollama so it picks these up (quit the menubar app and relaunch,
# or if you run it manually:  pkill ollama && ollama serve)
```

Verify the 64K variant loads and check memory with Activity Monitor open:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-8b-64k","messages":[{"role":"user","content":"hi"}],"max_tokens":20}'
ollama ps   # shows the loaded model + size
```

If your Mac gets hot or memory is pegged, drop to `q4_0` KV cache
(`launchctl setenv OLLAMA_KV_CACHE_TYPE q4_0`) or use `phi4-mini` instead.

---

## Step 3 — Install and configure Hermes

```bash
# install Hermes Agent per Nous's instructions (nousresearch.com / the hermes-agent repo)
# then run its setup wizard:
hermes setup
```

When it asks for a provider, choose **Custom Endpoint**:
- **Base URL:** `http://localhost:11434/v1`
- **API Key:** leave empty (or `no-key`)
- **Model:** `qwen3-8b-64k`   ← the 64K variant from Step 2, NOT plain qwen3:8b

Or edit `~/.hermes/config.yaml` directly:

```yaml
model:
  default: "qwen3-8b-64k"
  provider: "custom"
  base_url: "http://localhost:11434/v1"
providers:
  ollama:
    base_url: "http://localhost:11434/v1"
```

On a CPU/low-VRAM Mac the first response can take a while (the model processes the big
prompt before replying). Widen the timeout so it isn't mistaken for a hang:

```bash
# ~/.hermes/.env
HERMES_API_TIMEOUT=1800
```

Keep the model loaded so it doesn't reload every 5 minutes:

```bash
launchctl setenv OLLAMA_KEEP_ALIVE 24h
```

---

## Step 4 — Confirm Hermes works on its own

```bash
hermes
# then try:  "List the files in this folder and summarize the README."
```

If that works, Hermes is correctly driving your local model. If it complains about
context < 64,000, Step 2 didn't take — re-check that you pointed it at `qwen3-8b-64k`.

---

## Step 5 — Point Aegis at Hermes

Find the port Hermes exposes its OpenAI-compatible API on (its config/docs; commonly
`http://localhost:8080`). Then start Aegis in Hermes mode:

```bash
cd aegis
AEGIS_MODEL_BACKEND=hermes \
AEGIS_HERMES_HOST=http://localhost:8080 \
AEGIS_OLLAMA_MODEL=qwen3-8b-64k \
./scripts/start.sh
```

Open http://127.0.0.1:8777 — the Status card should show backend **hermes**. The
Device-safety card still governs it (Hermes work is heavier, so the governor matters
more here). If Hermes isn't reachable, Aegis says so clearly and you can fall back to
`AEGIS_MODEL_BACKEND=ollama` anytime.

---

## If it's too heavy on 18 GB

Hermes + 64K is genuinely demanding. In order of what to try:
1. Make sure the **8-bit KV cache** (Step 2) is actually on — biggest memory saver.
2. Close Chrome tabs / other apps before a Hermes session.
3. Use `q4_0` KV cache (smaller, slight quality cost).
4. Fall back to plain Ollama mode for everyday use; use Hermes only when you want the
   agent loop/skills. **Aegis runs fine either way** — that's why the backend is
   swappable.

Honest note: everyday chat and job-fit scoring don't need Hermes — plain Qwen3 handles
them. Hermes earns its cost when you want multi-step autonomous *agent* behavior.
