# Seed Data

Reusable fixtures and definitions for fresh installs. These files are committed
to the repo so new users get working defaults. Instance-specific runtime state
(challenge completion tracking, eval results) lives under `data/` which is
gitignored.

| File | Purpose |
|------|---------|
| `challenge_feed.json` | External challenge definitions for the evolution loop |
| `prompt_eval_taskset.json` | Representative prompt-eval taskset for golden fixture tests |
