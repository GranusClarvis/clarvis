# Research Re-open Policy

_When is re-research allowed? This is the single source of truth._

## Allowed Re-research Triggers

A completed research topic may only be re-researched if **exactly one** of these conditions is met:

| # | Trigger | Gate | Who can invoke |
|---|---------|------|----------------|
| 1 | **Contradiction** | New literature explicitly contradicts stored findings. Must cite the contradicting source. | Operator or discovery with citation |
| 2 | **Implementation follow-up** | Research was theoretical; now a concrete implementation task requires deeper/practical research on the same topic. Scope must shift (e.g., theory -> practice). | Heartbeat task router (scope_shift verdict) |
| 3 | **Stale revisit** | Prior research is older than `REFINEMENT_AGE_DAYS` (14 days). | Automatic (research_novelty.py) |
| 4 | **Shallow prior** | Prior research stored fewer than `REFINEMENT_MIN_MEMORIES` (3) brain memories. | Automatic (research_novelty.py) |
| 5 | **Operator explicit reopen** | Operator marks topic status as `revisitable` in the registry or passes `--source user` to classifier. | Operator only |

## Everything Else Bounces

If none of the five triggers apply, the topic is **blocked**. Specifically:

- Same topic + same scope + recent + well-covered = **REPEAT** (blocked)
- Family-locked topic area = **ALREADY_KNOWN** (blocked)
- Research count >= `MAX_RESEARCH_COUNT` (3) = **hard block**
- Rephrased/aliased version of a covered topic = blocked (canonical matching)

## Enforcement Points

1. **Pre-select gate** (`cron_research.sh` line ~213): `research_novelty.py classify` — blocks ALREADY_KNOWN topics before spawning Claude Code.
2. **Injection gate** (`queue_writer.py`): `repeat_classifier.py` — blocks REPEAT verdicts at queue injection time.
3. **Family lock** (`research_novelty.py`): When >= 60% of a family's topics are done/blocked and the family has >= 3 total researches, the entire family is locked.
4. **Post-execute gate** (`cron_research.sh` line ~441): `research_novelty.py evaluate-file` — blocks ingestion of files covering already-known content.

## How to Reopen a Topic

```bash
# Option 1: Mark a specific topic as revisitable
python3 scripts/evolution/research_novelty.py set-status "topic name" revisitable

# Option 2: Pass manual source to bypass repeat detection
python3 scripts/evolution/repeat_classifier.py classify "topic" --source user

# Option 3: Add contradiction evidence (future — not yet implemented)
# python3 scripts/evolution/research_novelty.py reopen "topic" --reason contradiction --citation "url"
```

## Constants (defined in research_novelty.py)

| Constant | Value | Meaning |
|----------|-------|---------|
| `SIMILARITY_THRESHOLD` | 0.45 | Word overlap above this = same topic |
| `REFINEMENT_AGE_DAYS` | 14 | Older than this → allow refinement |
| `REFINEMENT_MIN_MEMORIES` | 3 | Fewer memories → allow re-research |
| `MAX_RESEARCH_COUNT` | 3 | Hard block after this many researches |
| `FAMILY_LOCK_THRESHOLD` | 0.6 | Lock family when 60% topics done |
| `FAMILY_MIN_RESEARCH` | 3 | Min total researches before family lock |

## Decision Flowchart

```
Topic arrives
  ├─ Source = manual/user? → ALLOW (trigger #5)
  ├─ Family locked? → BLOCK
  ├─ No canonical match? → ALLOW (novel)
  └─ Canonical match found:
       ├─ Status = revisitable? → ALLOW (trigger #5)
       ├─ Status = blocked? → BLOCK
       ├─ research_count >= 3? → BLOCK
       ├─ age >= 14d? → ALLOW (trigger #3)
       ├─ memories < 3? → ALLOW (trigger #4)
       ├─ Scope differs? → ALLOW (trigger #2)
       └─ Otherwise → BLOCK
```
