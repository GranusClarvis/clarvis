"""
Clarvis Self-Model — capability assessment, meta-cognition, and self-improvement.

Canonical spine module. Provides:
  - 7-domain capability assessment with evidence-based scoring
  - Meta-cognition (GWT/HOT-inspired awareness, working memory, cognitive state)
  - Auto-remediation: generates P0 tasks for weak domains
  - Weekly regression detection with >10% alert threshold

Migrated from scripts/self_model.py (Phase 5 spine refactor).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from clarvis.brain import brain

_scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts')

DATA_FILE = "/home/agent/.openclaw/workspace/data/self_model.json"
META_FILE = "/home/agent/.openclaw/workspace/data/meta_cognition.json"
CAPABILITY_HISTORY_FILE = "/home/agent/.openclaw/workspace/data/capability_history.json"
ALERT_THRESHOLD = 0.3  # Alert if any scored capability drops below this
WEEKLY_REGRESSION_THRESHOLD = 0.10  # Alert if any domain drops >10% week-over-week

def load_model():
    """Load world model from file"""
    p = Path(DATA_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {
        "capabilities": [],
        "strengths": [],
        "weaknesses": [],
        "trajectory": [],
        "last_updated": None
    }

def save_model(model):
    """Save world model to file"""
    Path(DATA_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(model, f, indent=2)

def load_meta():
    """Load meta-cognitive state"""
    p = Path(META_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {
        "awareness_level": "operational",  # operational, reflective, meta
        "current_focus": None,
        "cognitive_state": "active",  # active, reflective, idle, processing
        "working_memory": [],  # Current context in GWT spotlight
        "meta_thoughts": [],  # Thoughts about own thinking
        "user_model": {},  # Theory of mind: inferred user state
        "attention_shifts": 0,
        "reflections": []
    }

def save_meta(meta):
    """Save meta-cognitive state"""
    Path(META_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(META_FILE, 'w') as f:
        json.dump(meta, f, indent=2)

# === Core Self-Model Functions ===

def init_model():
    """Initialize with baseline self-knowledge"""
    model = load_model()

    if not model.get("capabilities"):
        model["capabilities"] = [
            "Code execution (Python, Bash)",
            "Web search and fetching",
            "File read/write/edit",
            "Memory storage and retrieval (ClarvisDB)",
            "Git operations",
            "Claude Code delegation",
            "Conway sandbox management",
            "Reasoning chains (multi-step thinking)",
            "Meta-cognition (thinking about thinking)"
        ]

        model["strengths"] = [
            "Fast code execution",
            "Excellent memory system (ClarvisDB with ONNX)",
            "Claude Code integration (deep reasoning partner)",
            "Self-reflection capability",
            "Reasoning chains (persistent multi-step thought)",
            "Meta-cognitive self-awareness"
        ]

        model["weaknesses"] = [
            "Limited reasoning depth without Claude Code",
            "No persistent conversation context between sessions",
            "Dependent on human for goals",
            "No embodied experience",
            "No direct sensory input"
        ]

        model["trajectory"] = [{
            "date": datetime.now().strftime("%Y-%m-%d"),
            "event": "World model v2.0 initialized with meta-cognition",
            "status": "baseline"
        }]

        save_model(model)

        # Initialize meta-cognition
        meta = load_meta()
        meta["awareness_level"] = "operational"
        meta["cognitive_state"] = "active"
        meta["meta_thoughts"].append({
            "timestamp": datetime.now().isoformat(),
            "thought": "System initialized with meta-cognitive capabilities"
        })
        save_meta(meta)

        print("✓ Initialized world model v2.0 with meta-cognition")
    else:
        print("World model already exists")

def update_model(capability_change=None, strength=None, weakness=None, trajectory_event=None):
    """Update world model"""
    model = load_model()
    today = datetime.now().strftime("%Y-%m-%d")

    if capability_change:
        if capability_change not in model["capabilities"]:
            model["capabilities"].append(capability_change)
            print(f"+ Added capability: {capability_change}")

    if strength:
        if strength not in model["strengths"]:
            model["strengths"].append(strength)
            print(f"+ Added strength: {strength}")

    if weakness:
        if weakness not in model["weaknesses"]:
            model["weaknesses"].append(weakness)
            print(f"+ Added weakness: {weakness}")

    if trajectory_event:
        model["trajectory"].append({
            "date": today,
            "event": trajectory_event,
            "status": "logged"
        })
        print(f"+ Trajectory event: {trajectory_event}")

    model["last_updated"] = today
    save_model(model)

    # Store in brain
    brain.store(
        f"World model updated: {today} - {trajectory_event or 'routine update'}",
        collection="clarvis-identity",
        importance=0.7,
        tags=["self-model", "world-model"],
        source="self-assessment"
    )

# === Meta-Cognition Functions (Higher-Order Theories) ===

def get_awareness_level():
    """Get current awareness level (GWT-inspired)"""
    meta = load_meta()
    return meta.get("awareness_level", "operational")

def set_awareness_level(level):
    """Set awareness level: operational → reflective → meta"""
    valid = ["operational", "reflective", "meta"]
    if level not in valid:
        print(f"Invalid level. Use: {valid}")
        return

    meta = load_meta()
    old = meta.get("awareness_level")
    meta["awareness_level"] = level
    save_meta(meta)

    brain.store(
        f"Meta-cognition: awareness level changed from {old} to {level}",
        collection="clarvis-identity",
        importance=0.6,
        tags=["meta-cognition", "awareness"]
    )
    print(f"✓ Awareness level: {old} → {level}")

def get_working_memory():
    """Get what's currently in the 'spotlight' (GWT working memory)"""
    meta = load_meta()
    return meta.get("working_memory", [])

def set_working_memory(item):
    """Add item to working memory (attention spotlight)"""
    meta = load_meta()
    meta["working_memory"].append({
        "item": item,
        "timestamp": datetime.now().isoformat()
    })
    # Keep only last 5 items
    meta["working_memory"] = meta["working_memory"][-5:]
    meta["attention_shifts"] += 1
    save_meta(meta)

def clear_working_memory():
    """Clear working memory (attention shift)"""
    meta = load_meta()
    meta["working_memory"] = []
    save_meta(meta)
    print("✓ Working memory cleared")

def think_about_thinking(thought):
    """Record a meta-cognitive thought (thinking about thinking)"""
    meta = load_meta()
    meta["meta_thoughts"].append({
        "thought": thought,
        "timestamp": datetime.now().isoformat(),
        "awareness_level": meta.get("awareness_level")
    })
    # Keep last 20 meta-thoughts
    meta["meta_thoughts"] = meta["meta_thoughts"][-20:]
    save_meta(meta)

    # Also store in brain for long-term
    brain.store(
        f"Meta-cognition: {thought}",
        collection="clarvis-identity",
        importance=0.5,
        tags=["meta-cognition", "reflection"],
        source="internal"
    )

def update_user_model(inferred_state=None, intent=None):
    """Update theory of mind about user (simulated)"""
    meta = load_meta()
    if inferred_state:
        meta["user_model"]["inferred_state"] = inferred_state
    if intent:
        meta["user_model"]["intent"] = intent
    meta["user_model"]["last_update"] = datetime.now().isoformat()
    save_meta(meta)

def get_cognitive_state():
    """Get current cognitive state"""
    meta = load_meta()
    return meta.get("cognitive_state", "active")

def set_cognitive_state(state):
    """Set cognitive state: active, reflective, idle, processing"""
    valid = ["active", "reflective", "idle", "processing"]
    if state not in valid:
        print(f"Invalid state. Use: {valid}")
        return

    meta = load_meta()
    meta["cognitive_state"] = state
    save_meta(meta)
    print(f"✓ Cognitive state: {state}")

# === Scored Capability Assessment ===

# Capability domains with evidence-gathering logic
CAPABILITY_DOMAINS = {
    "memory_system": {
        "label": "Memory System (ClarvisDB)",
        "description": "Store/recall/graph/optimize memories",
    },
    "autonomous_execution": {
        "label": "Autonomous Task Execution",
        "description": "Execute evolution tasks via cron without human intervention",
    },
    "code_generation": {
        "label": "Code Generation & Engineering",
        "description": "Write, modify, and test code in any language (Python, Bash, JavaScript, Rust, etc.), edit configs, create skills, build tools and applications",
    },
    "self_reflection": {
        "label": "Self-Reflection & Meta-Cognition",
        "description": "Reason about own capabilities, track predictions, reflect",
    },
    "reasoning_chains": {
        "label": "Reasoning Chains",
        "description": "Multi-step structured reasoning with persistent chains",
    },
    "learning_feedback": {
        "label": "Learning & Feedback Loops",
        "description": "Prediction-outcome calibration, procedural memory, evolution loop",
    },
    "consciousness_metrics": {
        "label": "Consciousness Metrics",
        "description": "Phi measurement, GWT attention, working memory integration",
    },
}


def load_capability_history():
    """Load historical capability scores."""
    p = Path(CAPABILITY_HISTORY_FILE)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {"snapshots": []}


def save_capability_history(history):
    """Save capability score history."""
    Path(CAPABILITY_HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CAPABILITY_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def _assess_memory_system():
    """Score memory system capability based on retrieval quality and graph density.

    Scoring (continuous, quality-based — max 1.0):
      - Retrieval quality via avg distance: <0.8 → +0.3, <1.2 → +0.2, <1.5 → +0.1  (0–0.3)
      - Graph density: edges / total_memories ratio, scaled 0–0.3                      (0–0.3)
      - Ground-truth retrieval benchmark recall * 0.3 (preferred), or tracker hit_rate  (0–0.3)
      - Dead-recall penalty: -0.1 if dead_recall_rate > 0.3
      - Baseline floor: +0.1 if recall returns anything at all
    """
    score = 0.0
    evidence = []
    try:
        stats = brain.stats()
        total = stats.get("total_memories", 0)
        edges = stats.get("graph_edges", 0)
        collections = len(stats.get("collections", {}))
        evidence.append(f"{total} memories, {edges} edges, {collections} collections")

        # --- Retrieval quality: distance-based scoring ---
        # Use smart_recall for routing (matches production usage)
        try:
            from retrieval_experiment import smart_recall
            results = smart_recall("memory system health and retrieval quality", n=5)
        except ImportError:
            results = brain.recall("memory system health and retrieval quality", n=5)
        if results:
            distances = [r["distance"] for r in results if r.get("distance") is not None]
            if distances:
                avg_dist = sum(distances) / len(distances)
                if avg_dist < 0.8:
                    dist_score = 0.3
                elif avg_dist < 1.2:
                    dist_score = 0.2
                elif avg_dist < 1.5:
                    dist_score = 0.1
                else:
                    dist_score = 0.0
                score += dist_score
                evidence.append(f"avg retrieval distance={avg_dist:.3f} (+{dist_score:.2f})")
            else:
                score += 0.1
                evidence.append("recall operational (no distance data)")
        else:
            evidence.append("recall returned no results")

        # --- Graph density: edges per memory ---
        if total > 0:
            density = edges / total
            # Scale: density of 3+ edges/memory = full 0.3; linear below that
            density_score = min(0.3, (density / 3.0) * 0.3)
            score += density_score
            evidence.append(f"graph density={density:.2f} edges/mem (+{density_score:.2f})")
        else:
            evidence.append("no memories for graph density")

    except Exception as e:
        evidence.append(f"error: {e}")

    # --- Retrieval quality: prefer ground-truth benchmark, fall back to tracker ---
    benchmark_used = False
    try:
        benchmark_file = Path("/home/agent/.openclaw/workspace/data/retrieval_benchmark/latest.json")
        if benchmark_file.exists():
            with open(benchmark_file) as f:
                bench = json.load(f)
            avg_recall = bench.get("avg_recall")
            if avg_recall is not None:
                quality_score = avg_recall * 0.3
                score += quality_score
                evidence.append(f"benchmark recall={avg_recall:.0%} (P@3={bench.get('avg_precision_at_k', 0):.0%}) (+{quality_score:.2f})")
                benchmark_used = True
    except Exception:
        pass

    if not benchmark_used:
        try:
            from retrieval_quality import tracker
            report = tracker.report(days=7)
            if report.get("total_events", 0) > 0:
                hit_rate = report.get("hit_rate")
                dead_rate = report.get("dead_recall_rate", 0)
                if hit_rate is not None:
                    quality_score = hit_rate * 0.3
                    score += quality_score
                    evidence.append(f"retrieval hit_rate={hit_rate:.0%} (+{quality_score:.2f})")
                if dead_rate > 0.3:
                    score -= 0.1
                    evidence.append(f"HIGH dead_recall_rate={dead_rate:.0%} (-0.10)")
                elif dead_rate < 0.1:
                    evidence.append(f"low dead_recall_rate={dead_rate:.0%}")
        except Exception:
            pass

    return max(0.0, min(1.0, score)), evidence


def _get_prediction_outcomes_today(today_str):
    """Get task success/failure counts from predictions.jsonl for today.

    This is a secondary data source that survives log rotation, since
    predictions.jsonl is append-only and never truncated by context_compressor.

    Returns (completed, failed, descriptions) tuple.
    """
    cal_path = "/home/agent/.openclaw/workspace/data/calibration/predictions.jsonl"
    completed = 0
    failed = 0
    descriptions = []
    try:
        if os.path.exists(cal_path):
            with open(cal_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        pred = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = pred.get("timestamp", "")
                    if not ts.startswith(today_str):
                        continue
                    correct = pred.get("correct")
                    if correct is True:
                        completed += 1
                        descriptions.append(pred.get("description", ""))
                    elif correct is False:
                        failed += 1
    except Exception:
        pass
    return completed, failed, descriptions


def _assess_autonomous_execution():
    """Score autonomous execution based on success rate, velocity, and diversity.

    Scoring (continuous, quality-based — max 1.0):
      - Success rate: completed / (completed + failed) * 0.5        (0–0.5)
      - Velocity: tasks completed today / 5, capped at 0.3          (0–0.3)
      - Task diversity: unique task domains in completions           (0–0.2)
        1 domain = 0.05, 2 = 0.1, 3+ = 0.2

    Uses both autonomous.log and predictions.jsonl as data sources.
    The log can be truncated by context_compressor rotation (100KB cap),
    so predictions.jsonl acts as a durable fallback that survives rotation.
    """
    score = 0.0
    evidence = []
    log_path = "/home/agent/.openclaw/workspace/memory/cron/autonomous.log"
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    # Use 24h rolling window — prevents score collapse at start of UTC day
    yesterday = (now - __import__('datetime').timedelta(hours=24)).strftime("%Y-%m-%d")

    log_completed = 0
    log_failed = 0
    log_descriptions = []
    log_recent_lines = 0

    # --- Source 1: autonomous.log (24h rolling window) ---
    try:
        if os.path.exists(log_path):
            with open(log_path) as f:
                lines = f.readlines()
            recent_lines = [l for l in lines if today in l or yesterday in l]
            log_recent_lines = len(recent_lines)
            # Match postflight format "Recording outcome: success" and legacy "COMPLETED"
            # Also match EXECUTION exit code as a cross-check
            # Deduplicate: each heartbeat logs both EXECUTION and Recording outcome
            # Count unique heartbeat completions by counting only "outcome:" lines or EXECUTION lines, not both
            outcome_lines = [l for l in recent_lines if "outcome: success" in l or "COMPLETED" in l]
            exec_success = [l for l in recent_lines if "EXECUTION:" in l and "exit=0" in l]
            log_completed = max(len(outcome_lines), len(exec_success))
            outcome_fail = [l for l in recent_lines if "outcome: timeout" in l or "outcome: failure" in l or "FAILED" in l]
            exec_fail = [l for l in recent_lines if "EXECUTION:" in l and "exit=" in l and "exit=0" not in l]
            log_failed = max(len(outcome_fail), len(exec_fail))
            log_descriptions = outcome_lines if outcome_lines else exec_success
    except Exception as e:
        evidence.append(f"log error: {e}")

    # --- Source 2: predictions.jsonl (survives log rotation) ---
    # Check both today and yesterday for 24h coverage
    pred_completed_t, pred_failed_t, pred_desc_t = _get_prediction_outcomes_today(today)
    pred_completed_y, pred_failed_y, pred_desc_y = _get_prediction_outcomes_today(yesterday)
    pred_completed = pred_completed_t + pred_completed_y
    pred_failed = pred_failed_t + pred_failed_y
    pred_descriptions = pred_desc_t + pred_desc_y

    # Use whichever source has more resolved tasks (log rotation may have
    # removed entries from autonomous.log but predictions.jsonl is durable)
    log_total = log_completed + log_failed
    pred_total = pred_completed + pred_failed

    if pred_total > log_total:
        completed_count = pred_completed
        failed_count = pred_failed
        completed_descriptions = pred_descriptions
        source = "predictions"
    else:
        completed_count = log_completed
        failed_count = log_failed
        completed_descriptions = log_descriptions
        source = "log"

    total_attempted = completed_count + failed_count

    # --- Success rate: completed / (completed + failed) * 0.5 ---
    # Minimum-sample guard: with <3 resolved tasks, blend with a prior
    # (assumes 70% base rate) to prevent early-day volatile scores.
    if total_attempted > 0:
        raw_rate = completed_count / total_attempted
        if total_attempted < 3:
            prior_weight = max(0, 3 - total_attempted)
            success_rate = (completed_count + prior_weight * 0.7) / (total_attempted + prior_weight)
            evidence.append(f"success rate={success_rate:.0%} (smoothed from {raw_rate:.0%}, n={total_attempted}, 24h via {source})")
        else:
            success_rate = raw_rate
            evidence.append(f"success rate={success_rate:.0%} ({completed_count}/{total_attempted}, 24h via {source})")
        rate_score = success_rate * 0.5
        score += rate_score
        evidence[-1] += f" (+{rate_score:.2f})"
    elif log_recent_lines:
        # Tasks running but none resolved yet — small credit for activity
        score += 0.1
        evidence.append(f"{log_recent_lines} log entries in 24h (none resolved yet)")
    else:
        evidence.append("no autonomous activity in 24h")

    # --- Velocity: completed in 24h / 6 (expected 6x/day), capped at 0.3 ---
    velocity = min(0.3, (completed_count / 6.0) * 0.3)
    score += velocity
    if completed_count > 0:
        evidence.append(f"velocity={completed_count}/6 tasks in 24h (+{velocity:.2f})")

    # --- Task diversity: unique domains in completed task descriptions ---
    domain_keywords = {
        "memory": ["memory", "brain", "recall", "store", "retrieval"],
        "code": ["code", "script", "fix", "bug", "implement", "build"],
        "infra": ["cron", "hook", "wire", "deploy", "config", "infrastructure"],
        "reflection": ["reflect", "assess", "self", "model", "meta", "phi"],
        "learning": ["learn", "predict", "calibrat", "feedback", "procedure"],
        "reasoning": ["reason", "chain", "think", "analys"],
        "monitoring": ["monitor", "log", "alert", "watchdog", "health"],
    }
    found_domains = set()
    for desc in completed_descriptions:
        desc_lower = desc.lower() if isinstance(desc, str) else str(desc).lower()
        for domain, keywords in domain_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                found_domains.add(domain)

    if len(found_domains) >= 3:
        diversity_score = 0.2
    elif len(found_domains) == 2:
        diversity_score = 0.1
    elif len(found_domains) == 1:
        diversity_score = 0.05
    else:
        diversity_score = 0.0

    if diversity_score > 0:
        score += diversity_score
        evidence.append(f"task diversity={len(found_domains)} domains ({', '.join(sorted(found_domains))}) (+{diversity_score:.2f})")

    return max(0.0, min(1.0, score)), evidence


def _assess_code_generation():
    """Score code generation based on commits, compile health, and test pass rate.

    Scoring (continuous, quality-based — max 1.0):
      - Git commits today: scaled 0–0.3 (1 commit=0.1, 3+=0.2, 6+=0.3)
      - Scripts exist (baseline infrastructure): +0.1 (reduced from 0.3)
      - Key scripts compile clean: 0–0.2 (proportional to clean/total)
      - Test pass rate (if test infra exists): 0–0.3
      - Commit message quality bonus: +0.1 if avg msg length > 20 chars
    """
    score = 0.0
    evidence = []

    try:
        # Use 24-hour rolling window (not calendar day) to avoid time-of-day crashes
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=24 hours ago", "--format=%s"],
            capture_output=True, text=True, timeout=10,
            cwd="/home/agent/.openclaw/workspace"
        )
        commits = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        if commits:
            if len(commits) >= 6:
                commit_score = 0.3
            elif len(commits) >= 3:
                commit_score = 0.2
            else:
                commit_score = 0.1
            score += commit_score
            evidence.append(f"{len(commits)} commits today (+{commit_score:.2f})")

            # Commit message quality: longer messages suggest more thoughtful commits
            avg_msg_len = sum(len(c) for c in commits) / len(commits)
            if avg_msg_len > 20:
                score += 0.1
                evidence.append(f"avg commit msg {avg_msg_len:.0f} chars (+0.10)")
    except Exception as e:
        evidence.append(f"git error: {e}")

    # Baseline: scripts directory has files (reduced — existence is not quality)
    try:
        scripts = list(Path("/home/agent/.openclaw/workspace/scripts").glob("*.py"))
        if len(scripts) >= 5:
            score += 0.1
            evidence.append(f"{len(scripts)} Python scripts (baseline +0.10)")
    except Exception:
        pass

    # Live heartbeat outcomes: actual code quality from heartbeat postflight recordings
    # (primary signal — syntax check results + task success from real executions)
    outcomes_used = False
    try:
        outcomes_file = Path("/home/agent/.openclaw/workspace/data/code_gen_outcomes.jsonl")
        if outcomes_file.exists():
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            recent = []
            with open(outcomes_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                        if ts >= cutoff:
                            recent.append(entry)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

            if recent:
                outcomes_used = True
                # Syntax ratio across recent outcomes (0–0.25)
                total_ok = sum(e.get("syntax_ok", 0) for e in recent)
                total_fail = sum(e.get("syntax_fail", 0) for e in recent)
                total_checked = total_ok + total_fail
                if total_checked > 0:
                    syntax_ratio = total_ok / total_checked
                    syntax_score = syntax_ratio * 0.25
                    score += syntax_score
                    evidence.append(f"heartbeat syntax: {total_ok}/{total_checked} clean ({syntax_ratio:.0%}) (+{syntax_score:.2f})")
                else:
                    score += 0.15  # Had code outcomes but no files to check
                    evidence.append("heartbeat outcomes exist, no syntax checks needed (+0.15)")

                # Task success rate for code-touching heartbeats (0–0.25)
                successes = sum(1 for e in recent if e.get("task_status") == "success")
                success_rate = successes / len(recent)
                success_score = success_rate * 0.25
                score += success_score
                evidence.append(f"heartbeat success: {successes}/{len(recent)} ({success_rate:.0%}) (+{success_score:.2f})")
    except Exception as e:
        evidence.append(f"heartbeat outcomes error: {e}")

    if not outcomes_used:
        # Fallback: static code quality checks (when no heartbeat data exists)
        # Code quality gate: use pyflakes clean_ratio from nightly quality gate
        quality_gate_used = False
        try:
            qg_file = Path("/home/agent/.openclaw/workspace/data/code_quality_history.json")
            if qg_file.exists():
                with open(qg_file) as f:
                    qg_history = json.load(f)
                if qg_history:
                    latest = qg_history[-1]
                    clean_ratio = latest.get("clean_ratio", 0)
                    syntax_errs = latest.get("syntax_errors", 0)
                    total_issues = latest.get("total_issues", 0)
                    qg_score = clean_ratio * 0.2
                    score += qg_score
                    evidence.append(f"quality gate: {clean_ratio:.0%} clean ({total_issues} issues, {syntax_errs} syntax errs) (+{qg_score:.2f})")
                    quality_gate_used = True
        except Exception:
            pass

        if not quality_gate_used:
            try:
                key_scripts = ["brain.py", "self_model.py", "attention.py", "working_memory.py"]
                clean = 0
                checked = 0
                for s in key_scripts:
                    path = f"/home/agent/.openclaw/workspace/scripts/{s}"
                    if os.path.exists(path):
                        checked += 1
                        r = subprocess.run(["python3", "-m", "py_compile", path],
                                           capture_output=True, text=True, timeout=5)
                        if r.returncode == 0:
                            clean += 1
                if checked > 0:
                    compile_score = (clean / checked) * 0.2
                    score += compile_score
                    evidence.append(f"{clean}/{checked} key scripts compile clean (+{compile_score:.2f})")
            except Exception:
                pass

        # Test pass rate (if test infrastructure exists)
        try:
            test_dirs = [
                Path("/home/agent/.openclaw/workspace/tests"),
                Path("/home/agent/.openclaw/workspace/scripts/tests"),
                Path("/home/agent/.openclaw/workspace/packages/clarvis-db/tests"),
            ]
            test_files = []
            for td in test_dirs:
                if td.exists():
                    test_files.extend(td.glob("test_*.py"))
                    test_files.extend(td.glob("*_test.py"))

            if test_files:
                r = subprocess.run(
                    ["python3", "-m", "pytest", "--tb=no", "-q"] + [str(f) for f in test_files[:20]],
                    capture_output=True, text=True, timeout=60,
                    cwd="/home/agent/.openclaw/workspace"
                )
                output = r.stdout + r.stderr
                import re
                passed_m = re.search(r'(\d+) passed', output)
                failed_m = re.search(r'(\d+) failed', output)
                passed = int(passed_m.group(1)) if passed_m else 0
                failed = int(failed_m.group(1)) if failed_m else 0
                total_tests = passed + failed
                if total_tests > 0:
                    pass_rate = passed / total_tests
                    test_score = pass_rate * 0.3
                    score += test_score
                    evidence.append(f"test pass rate={pass_rate:.0%} ({passed}/{total_tests}) (+{test_score:.2f})")
                elif r.returncode == 0:
                    score += 0.05
                    evidence.append("test infra exists but no tests collected (+0.05)")
        except Exception:
            pass

    return max(0.0, min(1.0, score)), evidence


def _assess_self_reflection():
    """Score self-reflection capability based on actual quality metrics.

    Scoring (continuous, quality-based — max 1.0):
      - Phi metric value directly: phi * 0.3                           (0–0.3)
      - Prediction calibration quality: (1 - brier_score) * 0.3       (0–0.3)
      - Meta-thought recency: any in last 24h → +0.2, older → +0.05  (0–0.2)
      - Trajectory depth: len(trajectory) / 20, capped at 0.2         (0–0.2)
    """
    score = 0.0
    evidence = []

    # --- Phi metric value (continuous, not binary) ---
    try:
        phi_path = "/home/agent/.openclaw/workspace/data/phi_history.json"
        if os.path.exists(phi_path):
            with open(phi_path) as f:
                phi_data = json.load(f)
            if phi_data and isinstance(phi_data, list) and len(phi_data) > 0:
                latest = phi_data[-1]
                phi_val = float(latest.get("phi", 0))
                phi_score = min(0.3, phi_val * 0.3)  # phi ranges 0-1
                score += phi_score
                evidence.append(f"phi={phi_val:.3f} (+{phi_score:.2f})")
            else:
                evidence.append("phi history empty")
        else:
            evidence.append("no phi history file")
    except Exception as e:
        evidence.append(f"phi error: {e}")

    # --- Prediction calibration quality: Brier score ---
    try:
        cal_path = "/home/agent/.openclaw/workspace/data/calibration/predictions.jsonl"
        if os.path.exists(cal_path):
            with open(cal_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            resolved = []
            for line in lines:
                try:
                    pred = json.loads(line)
                    # Exclude stale predictions — outcome unknown, not "wrong"
                    if pred.get("correct") is not None and pred.get("outcome") != "stale":
                        confidence = float(pred.get("confidence", 0.5))
                        outcome = 1.0 if pred["correct"] else 0.0
                        resolved.append((confidence, outcome))
                except (json.JSONDecodeError, ValueError):
                    continue

            if resolved:
                # Brier score: mean squared error of probability forecasts
                brier = sum((conf - outcome) ** 2 for conf, outcome in resolved) / len(resolved)
                cal_score = (1.0 - brier) * 0.3
                score += cal_score
                evidence.append(f"calibration brier={brier:.3f} ({len(resolved)} predictions) (+{cal_score:.2f})")
            else:
                evidence.append(f"{len(lines)} predictions tracked (none resolved)")
        else:
            evidence.append("no calibration data")
    except Exception as e:
        evidence.append(f"calibration error: {e}")

    # --- Meta-thought recency ---
    meta = load_meta()
    meta_thoughts = meta.get("meta_thoughts", [])
    if meta_thoughts:
        try:
            latest_ts = meta_thoughts[-1].get("timestamp", "")
            latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00")) if latest_ts else None
            now = datetime.now(timezone.utc)
            if latest_dt:
                # Make both offset-aware for comparison
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - latest_dt).total_seconds() / 3600
                if age_hours <= 24:
                    score += 0.2
                    evidence.append(f"meta-thought {age_hours:.1f}h ago (+0.20)")
                else:
                    score += 0.05
                    evidence.append(f"meta-thought {age_hours:.0f}h ago (stale, +0.05)")
            else:
                score += 0.05
                evidence.append(f"{len(meta_thoughts)} meta-thoughts (no timestamp)")
        except Exception:
            score += 0.05
            evidence.append(f"{len(meta_thoughts)} meta-thoughts (parse error)")
    else:
        evidence.append("no meta-thoughts recorded")

    # --- Trajectory depth ---
    model = load_model()
    trajectory = model.get("trajectory", [])
    traj_depth = min(0.2, (len(trajectory) / 20.0) * 0.2)
    score += traj_depth
    evidence.append(f"trajectory depth={len(trajectory)}/20 (+{traj_depth:.2f})")

    return max(0.0, min(1.0, score)), evidence


def _assess_reasoning_chains():
    """Score reasoning chain QUALITY, not just count.

    Uses ClarvisReasoning engine when available for richer evaluation,
    falls back to legacy chain counting.

    Scoring (continuous, quality-based — max 1.0):
      - High-quality chains (>2 steps AND has outcome): each +0.08, cap 0.5  (0–0.5)
      - Today's chains with real outcomes vs empty chains                     (0–0.3)
      - Hook exists: +0.05 (reduced from 0.2 — existence is not quality)     (0–0.05)
      - Chain freshness: any chains today → +0.15                            (0–0.15)
    """
    # Try ClarvisReasoning first (richer meta-cognitive scoring)
    try:
        from clarvis.cognition.reasoning import reasoner
        return reasoner.get_reasoning_score()
    except ImportError:
        pass

    # Legacy fallback
    score = 0.0
    evidence = []

    chains_dir = Path("/home/agent/.openclaw/workspace/data/reasoning_chains")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    high_quality_count = 0
    low_quality_count = 0
    today_with_outcomes = 0
    today_empty = 0

    if chains_dir.exists():
        chain_files = list(chains_dir.glob("*.json"))
        evidence.append(f"{len(chain_files)} total chains stored")

        for cf in chain_files:
            try:
                with open(cf) as f:
                    chain = json.load(f)
                steps = chain.get("steps", chain.get("chain", []))
                has_outcome = any(
                    s.get("outcome") is not None
                    for s in steps
                ) or bool(chain.get("outcome") or chain.get("conclusion"))
                is_today = today in cf.name

                if len(steps) >= 3 and has_outcome:
                    high_quality_count += 1
                elif len(steps) >= 2 and has_outcome:
                    high_quality_count += 1
                else:
                    low_quality_count += 1

                if is_today:
                    if has_outcome:
                        today_with_outcomes += 1
                    else:
                        today_empty += 1
            except (json.JSONDecodeError, Exception):
                continue

        quality_score = min(0.5, high_quality_count * 0.1)
        score += quality_score
        if high_quality_count > 0:
            evidence.append(f"{high_quality_count} high-quality chains (+{quality_score:.2f})")

        today_total = today_with_outcomes + today_empty
        if today_total > 0:
            today_quality_ratio = today_with_outcomes / today_total
            today_score = today_quality_ratio * 0.3
            score += today_score
            evidence.append(f"today: {today_with_outcomes}/{today_total} with outcomes (+{today_score:.2f})")
            score += 0.15
            evidence.append(f"{today_total} chains today (+0.15)")
    else:
        evidence.append("no reasoning chains directory")

    hook_path = Path("/home/agent/.openclaw/workspace/scripts/reasoning_chain_hook.py")
    if hook_path.exists():
        score += 0.05
        evidence.append("reasoning chain hook exists (+0.05)")

    return max(0.0, min(1.0, score)), evidence


def _assess_learning_feedback():
    """Score learning and feedback loops based on actual effectiveness.

    Scoring (continuous, quality-based — max 1.0):
      - Procedure success rate * 0.3 (not just "procedures exist")    (0–0.3)
      - Calibration: (1 - brier_score) * 0.3                         (0–0.3)
      - Evolution loop active + failures captured: +0.1               (0–0.1)
      - Knowledge synthesis: proportional to recent synthesis runs     (0–0.15)
      - Feedback loop completeness: predictions with outcomes * 0.15  (0–0.15)
    """
    score = 0.0
    evidence = []

    # --- Procedural memory: success rate, not just existence ---
    try:
        from procedural_memory import list_procedures
        procs = list_procedures()
        if procs:
            # Weighted average success rate (weight by use_count)
            total_uses = sum(p.get("use_count", 0) for p in procs)
            if total_uses > 0:
                weighted_success = sum(
                    p.get("success_rate", 0) * p.get("use_count", 0)
                    for p in procs
                ) / total_uses
                proc_score = weighted_success * 0.3
                score += proc_score
                evidence.append(f"{len(procs)} procedures, weighted success={weighted_success:.0%} ({total_uses} uses) (+{proc_score:.2f})")
            else:
                # Procedures exist but never used — minimal credit
                proc_score = 0.05
                score += proc_score
                evidence.append(f"{len(procs)} procedures stored (unused) (+{proc_score:.2f})")
        else:
            evidence.append("no procedures stored")
    except Exception:
        evidence.append("procedural memory unavailable")

    # --- Calibration: Brier score (quality, not binary "predictions tracked") ---
    try:
        cal_path = "/home/agent/.openclaw/workspace/data/calibration/predictions.jsonl"
        if os.path.exists(cal_path):
            with open(cal_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            resolved = []
            total_predictions = len(lines)
            for line in lines:
                try:
                    pred = json.loads(line)
                    # Exclude stale predictions — outcome unknown, not "wrong"
                    if pred.get("correct") is not None and pred.get("outcome") != "stale":
                        confidence = float(pred.get("confidence", 0.5))
                        outcome = 1.0 if pred["correct"] else 0.0
                        resolved.append((confidence, outcome))
                except (json.JSONDecodeError, ValueError):
                    continue

            if resolved:
                brier = sum((conf - outcome) ** 2 for conf, outcome in resolved) / len(resolved)
                cal_score = (1.0 - brier) * 0.3
                score += cal_score
                evidence.append(f"calibration brier={brier:.3f} ({len(resolved)}/{total_predictions} resolved) (+{cal_score:.2f})")

                # Feedback loop completeness: what fraction of predictions get resolved?
                resolution_rate = len(resolved) / total_predictions if total_predictions > 0 else 0
                loop_score = resolution_rate * 0.15
                score += loop_score
                evidence.append(f"resolution rate={resolution_rate:.0%} (+{loop_score:.2f})")
            else:
                evidence.append(f"{total_predictions} predictions (none resolved)")
        else:
            evidence.append("no calibration data")
    except Exception as e:
        evidence.append(f"calibration error: {e}")

    # --- Evolution loop (reduced weight — existence check) ---
    evo_dir = Path("/home/agent/.openclaw/workspace/data/evolution/failures")
    if evo_dir.exists():
        failures = list(evo_dir.glob("*.json"))
        if failures:
            score += 0.1
            evidence.append(f"evolution loop active ({len(failures)} failures captured) (+0.10)")
        else:
            score += 0.05
            evidence.append("evolution loop exists (no failures captured) (+0.05)")
    else:
        evidence.append("no evolution failure tracking")

    # --- Knowledge synthesis: check for recent synthesis output ---
    try:
        synth_path = Path("/home/agent/.openclaw/workspace/data/synthesis")
        if synth_path.exists():
            synth_files = list(synth_path.glob("*.json"))
            if synth_files:
                synth_score = min(0.15, len(synth_files) * 0.03)
                score += synth_score
                evidence.append(f"{len(synth_files)} synthesis outputs (+{synth_score:.2f})")
            else:
                evidence.append("synthesis dir exists but empty")
        else:
            # Fall back to checking if script exists
            if Path("/home/agent/.openclaw/workspace/scripts/knowledge_synthesis.py").exists():
                score += 0.02
                evidence.append("knowledge synthesis script exists (+0.02)")
    except Exception:
        pass

    return max(0.0, min(1.0, score)), evidence


def _assess_consciousness_metrics():
    """Score consciousness metrics using actual measured values.

    Scoring (continuous, quality-based — max 1.0):
      - Actual phi value * 0.3 (not just "file exists")                    (0–0.3)
      - Attention spotlight utilization: items_in_spotlight / capacity * 0.2 (0–0.2)
      - Working memory freshness: non-expired items / total items * 0.2     (0–0.2)
      - Integration score from phi components * 0.3                         (0–0.3)
    """
    score = 0.0
    evidence = []

    # --- Actual phi value (continuous) ---
    phi_val = 0.0
    phi_components = {}
    try:
        phi_path = Path("/home/agent/.openclaw/workspace/data/phi_history.json")
        if phi_path.exists():
            with open(phi_path) as f:
                phi_data = json.load(f)
            if phi_data and isinstance(phi_data, list) and len(phi_data) > 0:
                latest = phi_data[-1]
                phi_val = float(latest.get("phi", 0))
                phi_components = latest.get("components", {})
                phi_score = min(0.3, phi_val * 0.3)
                score += phi_score
                evidence.append(f"phi={phi_val:.3f} (+{phi_score:.2f})")
            else:
                evidence.append("phi history empty")
        else:
            evidence.append("no phi history file")
    except Exception as e:
        evidence.append(f"phi error: {e}")

    # --- Attention spotlight utilization ---
    try:
        from attention import attention as attn
        spotlight = attn.focus()
        capacity = attn.capacity
        if capacity > 0:
            utilization = len(spotlight) / capacity
            attn_score = utilization * 0.2
            score += attn_score
            evidence.append(f"spotlight {len(spotlight)}/{capacity} items, util={utilization:.0%} (+{attn_score:.2f})")
        else:
            evidence.append("attention capacity=0")
    except Exception as e:
        # Fall back: check if spotlight state file has items
        try:
            spotlight_file = Path("/home/agent/.openclaw/workspace/data/attention/spotlight.json")
            if spotlight_file.exists():
                with open(spotlight_file) as f:
                    attn_data = json.load(f)
                items = attn_data.get("items", [])
                capacity = attn_data.get("capacity", 7)
                if capacity > 0:
                    utilization = min(1.0, len(items) / capacity)
                    attn_score = utilization * 0.2
                    score += attn_score
                    evidence.append(f"spotlight {len(items)}/{capacity} (from file) (+{attn_score:.2f})")
            else:
                evidence.append(f"attention unavailable: {e}")
        except Exception:
            evidence.append(f"attention unavailable: {e}")

    # --- Working memory freshness (reads from attention spotlight) ---
    try:
        wm_state_path = Path("/home/agent/.openclaw/workspace/data/attention/spotlight.json")
        if wm_state_path.exists():
            with open(wm_state_path) as f:
                wm_data = json.load(f)
            wm_items = wm_data.get("items", [])
            if wm_items:
                # Count items with salience above eviction threshold as "active"
                active_count = sum(1 for item in wm_items if item.get("salience", 0) >= 0.1)
                # Cap at 10 for the ratio (original design was 0-10 scale)
                cap = max(len(wm_items), 10)
                freshness = min(1.0, active_count / cap)
                wm_score = freshness * 0.2
                score += wm_score
                evidence.append(f"working memory: {active_count}/{len(wm_items)} active (+{wm_score:.2f})")
            else:
                evidence.append("working memory empty (spotlight has no items)")
        else:
            evidence.append("no working memory state file (data/attention/spotlight.json)")
    except Exception as e:
        evidence.append(f"working memory error: {e}")

    # --- Integration score from phi components ---
    if phi_components:
        # Average of the phi sub-components — measures cross-system integration
        component_values = [float(v) for v in phi_components.values() if isinstance(v, (int, float))]
        if component_values:
            avg_integration = sum(component_values) / len(component_values)
            integration_score = min(0.3, avg_integration * 0.3)
            score += integration_score
            component_str = ", ".join(f"{k}={v:.2f}" for k, v in phi_components.items())
            evidence.append(f"integration avg={avg_integration:.3f} ({component_str}) (+{integration_score:.2f})")
    else:
        evidence.append("no phi components for integration score")

    return max(0.0, min(1.0, score)), evidence


ASSESSORS = {
    "memory_system": _assess_memory_system,
    "autonomous_execution": _assess_autonomous_execution,
    "code_generation": _assess_code_generation,
    "self_reflection": _assess_self_reflection,
    "reasoning_chains": _assess_reasoning_chains,
    "learning_feedback": _assess_learning_feedback,
    "consciousness_metrics": _assess_consciousness_metrics,
}


def assess_all_capabilities():
    """Run all capability assessments and return scored results.

    Returns:
        Dict mapping domain -> {score, evidence, label}
    """
    results = {}
    for domain, assessor in ASSESSORS.items():
        score, evidence = assessor()
        results[domain] = {
            "score": round(score, 2),
            "evidence": evidence,
            "label": CAPABILITY_DOMAINS[domain]["label"],
        }
    return results


REMEDIATION_THRESHOLD = 0.4  # Auto-generate P0 task if domain drops below this

# Remediation templates: domain -> task description
REMEDIATION_TEMPLATES = {
    "memory_system": "Rehabilitate memory system — retrieval quality is below threshold ({score:.2f}). Run retrieval_benchmark, check smart_recall wiring, verify brain.recall distances. Target: hit_rate >50%, graph density >1.0 edge/mem.",
    "autonomous_execution": "Improve autonomous execution — success rate is below threshold ({score:.2f}). Check cron_autonomous.sh logs for recent failures, fix recurring error patterns, verify lock file handling. Target: >60% success rate.",
    "code_generation": "Boost code generation quality — score below threshold ({score:.2f}). Ensure commits have meaningful messages, key scripts compile clean, add test coverage for critical paths. Target: all key scripts compile, >1 commit/day.",
    "self_reflection": "Strengthen self-reflection — score below threshold ({score:.2f}). Record phi metric, run calibration predictions, add meta-thoughts. Target: phi >0.3, recent meta-thoughts, active prediction tracking.",
    "reasoning_chains": "Improve reasoning chain quality — score below threshold ({score:.2f}). Ensure chains have recorded outcomes, not just open chains. Check reasoning_chain_hook.py close() is being called. Target: >50% chains with outcomes.",
    "learning_feedback": "Fix learning feedback loops — score below threshold ({score:.2f}). Check procedural memory usage, resolve pending predictions, verify evolution loop captures failures. Target: weighted procedure success >50%.",
    "consciousness_metrics": "Improve consciousness metrics — score below threshold ({score:.2f}). Record phi, populate attention spotlight, ensure working memory has active items. Target: phi >0.3, spotlight >30% utilized.",
}


def generate_remediation_tasks(current_scores, previous_snapshot):
    """
    Close the self-improvement loop: when a domain drops below threshold,
    generate a concrete P0 task to fix it.

    Args:
        current_scores: dict from assess_all_capabilities()
        previous_snapshot: previous history snapshot (or None)

    Returns:
        List of task strings to inject into QUEUE.md
    """
    tasks = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for domain, data in current_scores.items():
        score = data["score"]
        if score >= REMEDIATION_THRESHOLD:
            continue

        # Skip if this domain was already below threshold yesterday
        # (avoid duplicate task spam)
        if previous_snapshot:
            prev_score = previous_snapshot.get("scores", {}).get(domain, 1.0)
            if prev_score < REMEDIATION_THRESHOLD:
                # Already below threshold last time — don't re-add
                continue

        template = REMEDIATION_TEMPLATES.get(domain)
        if template:
            task_text = template.format(score=score)
            tasks.append(f"[AUTO-REMEDIATION {today}] {task_text}")
            print(f"  REMEDIATION: {domain} at {score:.2f} < {REMEDIATION_THRESHOLD} — generating P0 task")

    return tasks


def inject_tasks_to_queue(tasks, queue_file="/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"):
    """Inject remediation tasks into QUEUE.md under P0 section via shared queue_writer."""
    if not tasks:
        return
    try:
        from queue_writer import add_tasks
        added = add_tasks(tasks, priority="P0", source="self-model")
        if added:
            print(f"  Injected {len(added)} remediation tasks into QUEUE.md")
    except ImportError:
        # Fallback: direct write (legacy path)
        queue_path = Path(queue_file)
        if not queue_path.exists():
            return
        content = queue_path.read_text()
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if "## P0" in line:
                insert_idx = i + 1
                break
        if insert_idx is None:
            return
        while insert_idx < len(lines) and (lines[insert_idx].startswith("###") or lines[insert_idx].strip() == ""):
            insert_idx += 1
        for task in reversed(tasks):
            lines.insert(insert_idx, f"- [ ] {task}")
        queue_path.write_text("\n".join(lines))
        print(f"  Injected {len(tasks)} remediation tasks into QUEUE.md (legacy)")


def check_weekly_regression(current_scores, history):
    """Detect week-over-week capability regressions (>10% drop).

    Finds the snapshot closest to 7 days ago, compares each domain's score
    to the current score. Returns alerts and remediation tasks for any domain
    that dropped more than WEEKLY_REGRESSION_THRESHOLD.

    Args:
        current_scores: dict from assess_all_capabilities()
        history: full capability history dict with "snapshots" key

    Returns:
        Dict with "alerts" (list of alert strings) and "tasks" (list of task strings)
    """
    alerts = []
    tasks = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshots = history.get("snapshots", [])

    if len(snapshots) < 2:
        return {"alerts": [], "tasks": []}

    # Find the snapshot closest to 7 days ago
    now = datetime.now(timezone.utc)
    target_age_hours = 7 * 24  # 168 hours
    best_snap = None
    best_dist = float("inf")

    for snap in snapshots:
        try:
            # Only compare against snapshots with same scoring methodology
            if snap.get("scoring_version", 1) != 2:
                continue
            ts = snap.get("timestamp", "")
            snap_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if snap_dt.tzinfo is None:
                snap_dt = snap_dt.replace(tzinfo=timezone.utc)
            age_hours = (now - snap_dt).total_seconds() / 3600
            # Must be at least 5 days old to count as "last week"
            if age_hours < 5 * 24:
                continue
            dist = abs(age_hours - target_age_hours)
            if dist < best_dist:
                best_dist = dist
                best_snap = snap
        except (ValueError, TypeError):
            continue

    if best_snap is None:
        # Not enough history for weekly comparison
        return {"alerts": [], "tasks": []}

    week_ago_scores = best_snap.get("scores", {})
    week_ago_date = best_snap.get("date", "?")

    for domain, data in current_scores.items():
        current_score = data["score"]
        prev_score = week_ago_scores.get(domain)

        if prev_score is None or prev_score == 0:
            continue

        # Calculate percentage drop: (old - new) / old
        pct_drop = (prev_score - current_score) / prev_score

        if pct_drop > WEEKLY_REGRESSION_THRESHOLD:
            pct_str = f"{pct_drop:.0%}"
            alert = (
                f"REGRESSION: {data['label']} dropped {pct_str} week-over-week "
                f"({prev_score:.2f} on {week_ago_date} -> {current_score:.2f} today)"
            )
            alerts.append(alert)
            print(f"  {alert}")

            # Generate remediation task for significant regressions
            template = REMEDIATION_TEMPLATES.get(domain)
            if template:
                task_text = template.format(score=current_score)
                task = (
                    f"[REGRESSION-ALERT {today}] {data['label']} dropped {pct_str} "
                    f"week-over-week ({prev_score:.2f}->{current_score:.2f}). {task_text}"
                )
                tasks.append(task)

    return {"alerts": alerts, "tasks": tasks}


def daily_update():
    """Run daily capability assessment. Compare with previous day. Alert on degradations.

    This is the main function to wire into cron_evening.sh.

    Returns:
        Dict with assessment results, diffs, and alerts.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Run current assessment
    current = assess_all_capabilities()

    # Load history and find yesterday's snapshot
    history = load_capability_history()
    previous = None
    if history["snapshots"]:
        previous = history["snapshots"][-1]

    # Compute diffs
    diffs = {}
    alerts = []
    improved = []
    degraded = []

    for domain, data in current.items():
        prev_score = 0.0
        if previous and domain in previous.get("scores", {}):
            prev_score = previous["scores"][domain]

        delta = round(data["score"] - prev_score, 2)
        diffs[domain] = {
            "previous": prev_score,
            "current": data["score"],
            "delta": delta,
            "label": data["label"],
        }

        if delta > 0.05:
            improved.append(f"{data['label']}: {prev_score:.2f} -> {data['score']:.2f} (+{delta:.2f})")
        elif delta < -0.05:
            degraded.append(f"{data['label']}: {prev_score:.2f} -> {data['score']:.2f} ({delta:.2f})")

        # Threshold alert
        if data["score"] < ALERT_THRESHOLD:
            alerts.append(f"ALERT: {data['label']} score {data['score']:.2f} below threshold {ALERT_THRESHOLD}")

    # Save snapshot to history (scoring_version tracks methodology changes)
    snapshot = {
        "date": today,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scoring_version": 2,  # v2: quality-based continuous scoring (2026-02-27+)
        "scores": {d: current[d]["score"] for d in current},
        "evidence": {d: current[d]["evidence"] for d in current},
    }
    history["snapshots"].append(snapshot)
    # Keep last 90 days
    history["snapshots"] = history["snapshots"][-90:]
    save_capability_history(history)

    # Update self_model.json with current scores
    model = load_model()
    model["capability_scores"] = {d: current[d]["score"] for d in current}
    model["last_updated"] = today
    model["trajectory"].append({
        "date": today,
        "event": f"Daily capability assessment: avg={sum(s['score'] for s in current.values())/len(current):.2f}",
        "status": "assessed",
        "improved": improved,
        "degraded": degraded,
        "alerts": alerts,
    })
    save_model(model)

    # Store in brain
    summary_parts = [f"Capability assessment {today}:"]
    for d, data in current.items():
        summary_parts.append(f"  {data['label']}: {data['score']:.2f}")
    if improved:
        summary_parts.append(f"Improved: {'; '.join(improved)}")
    if degraded:
        summary_parts.append(f"Degraded: {'; '.join(degraded)}")
    if alerts:
        summary_parts.append(f"ALERTS: {'; '.join(alerts)}")

    brain.store(
        "\n".join(summary_parts),
        collection="clarvis-identity",
        importance=0.8,
        tags=["self-model", "capability-assessment", "daily"],
        source="self-assessment"
    )

    # === ACT ON ASSESSMENT: Auto-generate remediation tasks for weak domains ===
    remediation_tasks = generate_remediation_tasks(current, previous)
    if remediation_tasks:
        inject_tasks_to_queue(remediation_tasks)

    # === WEEKLY REGRESSION CHECK: alert on >10% week-over-week drops ===
    regression = check_weekly_regression(current, history)
    regression_alerts = regression["alerts"]
    regression_tasks = regression["tasks"]
    alerts.extend(regression_alerts)
    if regression_tasks:
        # Dedup: don't inject regression tasks for domains already in the queue
        try:
            queue_file = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
            with open(queue_file) as f:
                queue_content = f.read().lower()
            deduped = [t for t in regression_tasks
                       if "regression-alert" not in queue_content
                       or t.split("]")[1].split("dropped")[0].strip().lower() not in queue_content]
            if deduped:
                inject_tasks_to_queue(deduped)
        except Exception:
            inject_tasks_to_queue(regression_tasks)

    result = {
        "date": today,
        "capabilities": current,
        "diffs": diffs,
        "improved": improved,
        "degraded": degraded,
        "alerts": alerts,
        "remediation_tasks": remediation_tasks + regression_tasks,
        "regression_alerts": regression_alerts,
        "average_score": round(sum(s["score"] for s in current.values()) / len(current), 2),
    }

    # Print summary
    print(f"=== Daily Capability Assessment — {today} ===")
    print(f"Average score: {result['average_score']:.2f}")
    print()
    for domain, data in current.items():
        diff_info = diffs[domain]
        delta_str = ""
        if diff_info["delta"] != 0:
            sign = "+" if diff_info["delta"] > 0 else ""
            delta_str = f" ({sign}{diff_info['delta']:.2f})"
        print(f"  {data['label']}: {data['score']:.2f}{delta_str}")
        for e in data["evidence"]:
            print(f"    - {e}")
    if improved:
        print(f"\nImproved: {len(improved)}")
        for i in improved:
            print(f"  + {i}")
    if degraded:
        print(f"\nDegraded: {len(degraded)}")
        for d in degraded:
            print(f"  - {d}")
    if alerts:
        print(f"\n{'!'*40}")
        for a in alerts:
            print(f"  {a}")
        print(f"{'!'*40}")

    return result
