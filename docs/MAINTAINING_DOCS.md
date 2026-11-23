# Keeping the docs current

These three docs are meant to stay in sync with the code — treat updating them as
part of "done" for any feature change:

- **FEATURES.md** — when you add/change/remove a feature: update §3 (the feature
  list), the workflow (§2) if the flow changed, the code map (§4) if files moved, and
  the milestone table + "known rough edges" (§5).
- **USER_GUIDE.md** — when a feature's *usage* changes (new button, new endpoint, new
  step): update the relevant section and the troubleshooting table.
- **README.md** — only the status line and quick-start; keep it short and point at the
  two docs above.

Rule of thumb: **FEATURES.md answers "what is it / how does it work," USER_GUIDE.md
answers "how do I use it."** If you're unsure which, a feature's existence goes in
FEATURES, its click-path goes in USER_GUIDE.

Bump the "Last updated" line in FEATURES.md when you touch it.
