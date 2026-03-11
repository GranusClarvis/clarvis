"""Retrieval Gate — Heuristic 3-tier routing for brain recall.

Classifies tasks into retrieval tiers to avoid unnecessary brain.recall() calls:
  NO_RETRIEVAL   — maintenance/cron/infra tasks → skip recall, save ~7.5s
  LIGHT_RETRIEVAL — scoped implementation → 2-3 collections, top-3
  DEEP_RETRIEVAL  — research/design/multi-hop → all collections, top-10, graph expansion

Part of the Adaptive RAG pipeline (GATE → EVAL → RETRY → FEEDBACK).

Usage:
    from clarvis.brain.retrieval_gate import classify_retrieval

    tier = classify_retrieval("Fix cron_watchdog.sh timeout")
    # → RetrievalTier(tier='NO_RETRIEVAL', reason='maintenance keyword: cron',
    #                  collections=[], n_results=0, graph_expand=False)
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RetrievalTier:
    """Result of retrieval gate classification."""
    tier: str  # NO_RETRIEVAL | LIGHT_RETRIEVAL | DEEP_RETRIEVAL
    reason: str
    collections: List[str] = field(default_factory=list)
    n_results: int = 0
    graph_expand: bool = False

    def to_dict(self):
        return {
            "tier": self.tier,
            "reason": self.reason,
            "collections": self.collections,
            "n_results": self.n_results,
            "graph_expand": self.graph_expand,
        }


# --- Keyword patterns ---

# Tasks that never need brain recall (pure maintenance, cron health, cleanup)
_NO_RETRIEVAL_PATTERNS = [
    re.compile(r'\b(backup|cleanup|vacuum|compaction|checkpoint|garbage.collect|log.rot|watchdog|health.check|health_monitor)\b', re.I),
    re.compile(r'\b(graph.checkpoint|graph.compaction|graph.vacuum|graph_checkpoint|graph_compaction)\b', re.I),
    re.compile(r'\b(cron_cleanup|cron_watchdog|backup_daily|backup_verify)\b', re.I),
    re.compile(r'\b(shellcheck|lint|format|dead.script|deprecated)\b', re.I),
    re.compile(r'\b(dream_engine|counterfactual)\b', re.I),
]

# Tags that indicate maintenance tasks (from QUEUE.md [TAG] format)
_NO_RETRIEVAL_TAGS = {
    "CRON_SHELLCHECK_AUDIT", "CLI_DEAD_SCRIPT_SWEEP", "CRON_CLEANUP",
    "GRAPH_CHECKPOINT", "GRAPH_COMPACTION", "GRAPH_VACUUM",
    "BACKUP", "CLEANUP", "WATCHDOG", "HEALTH",
}

# Tasks that need deep retrieval (research, design, multi-hop reasoning)
_DEEP_RETRIEVAL_PATTERNS = [
    re.compile(r'\b(research|arXiv|paper|survey|literature|state.of.the.art)\b', re.I),
    re.compile(r'\b(design|architect|plan|strategy|roadmap|audit)\b', re.I),
    re.compile(r'\b(investigate|analyze|diagnose|root.cause|regression|why)\b', re.I),
    re.compile(r'\b(multi.hop|cross.collection|semantic.bridge|overlap|density)\b', re.I),
    re.compile(r'\b(consciousness|phi|AGI|self.model|identity|soul)\b', re.I),
    re.compile(r'\b(RESEARCH_DISCOVERY|STRATEGIC_AUDIT|EVOLUTION_ANALYSIS)\b'),
]

# Tags that indicate deep retrieval tasks
_DEEP_RETRIEVAL_TAGS = {
    "RESEARCH_DISCOVERY", "STRATEGIC_AUDIT", "EVOLUTION_ANALYSIS",
    "AUTONOMY_SCORE_INVESTIGATION", "RECALL_GRAPH_CONTEXT",
    "SEMANTIC_BRIDGE", "INTRA_DENSITY_BOOST",
}

# Collections for each tier
_LIGHT_COLLECTIONS = ["clarvis-learnings", "clarvis-procedures", "clarvis-episodes"]
_DEEP_COLLECTIONS = [
    "clarvis-identity", "clarvis-preferences", "clarvis-learnings",
    "clarvis-infrastructure", "clarvis-goals", "clarvis-context",
    "clarvis-memories", "clarvis-procedures", "autonomous-learning",
    "clarvis-episodes",
]


def _extract_tag(task_text: str) -> Optional[str]:
    """Extract [TAG] from task text."""
    m = re.match(r'\[([A-Z0-9_]+)\]', task_text.strip())
    return m.group(1) if m else None


def classify_retrieval(task_text: str) -> RetrievalTier:
    """Classify a task into a retrieval tier.

    Args:
        task_text: The task description (from QUEUE.md or selected task).

    Returns:
        RetrievalTier with tier, reason, collections, n_results, graph_expand.
    """
    if not task_text or not task_text.strip():
        return RetrievalTier(
            tier="NO_RETRIEVAL",
            reason="empty task",
        )

    tag = _extract_tag(task_text)

    # 1. Check NO_RETRIEVAL first (maintenance/cron tasks)
    if tag and tag in _NO_RETRIEVAL_TAGS:
        return RetrievalTier(
            tier="NO_RETRIEVAL",
            reason=f"maintenance tag: {tag}",
        )

    for pat in _NO_RETRIEVAL_PATTERNS:
        m = pat.search(task_text)
        if m:
            return RetrievalTier(
                tier="NO_RETRIEVAL",
                reason=f"maintenance keyword: {m.group(0)}",
            )

    # 2. Check DEEP_RETRIEVAL (research/design/investigation)
    if tag and tag in _DEEP_RETRIEVAL_TAGS:
        return RetrievalTier(
            tier="DEEP_RETRIEVAL",
            reason=f"research/design tag: {tag}",
            collections=_DEEP_COLLECTIONS,
            n_results=10,
            graph_expand=True,
        )

    deep_matches = 0
    deep_reason = ""
    for pat in _DEEP_RETRIEVAL_PATTERNS:
        m = pat.search(task_text)
        if m:
            deep_matches += 1
            if not deep_reason:
                deep_reason = m.group(0)

    if deep_matches >= 2:
        return RetrievalTier(
            tier="DEEP_RETRIEVAL",
            reason=f"multi-signal deep: {deep_reason} (+{deep_matches - 1} more)",
            collections=_DEEP_COLLECTIONS,
            n_results=10,
            graph_expand=True,
        )

    if deep_matches == 1:
        # Single deep signal — still deep but lighter
        return RetrievalTier(
            tier="DEEP_RETRIEVAL",
            reason=f"deep keyword: {deep_reason}",
            collections=_DEEP_COLLECTIONS,
            n_results=7,
            graph_expand=False,
        )

    # 3. Default: LIGHT_RETRIEVAL (scoped implementation, wiring, fixes)
    return RetrievalTier(
        tier="LIGHT_RETRIEVAL",
        reason="default: scoped implementation",
        collections=_LIGHT_COLLECTIONS,
        n_results=3,
        graph_expand=False,
    )


def dry_run(tasks: list) -> list:
    """Classify a list of tasks and return results for validation.

    Args:
        tasks: List of task description strings.

    Returns:
        List of dicts with task (truncated) and classification result.
    """
    results = []
    for task in tasks:
        tier = classify_retrieval(task)
        results.append({
            "task": task[:80],
            "tier": tier.tier,
            "reason": tier.reason,
            "n_results": tier.n_results,
            "collections": len(tier.collections),
            "graph_expand": tier.graph_expand,
        })
    return results


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "dry-run":
        # Dry-run on sample tasks
        sample_tasks = [
            "[CRON_SHELLCHECK_AUDIT] Run ShellCheck on the 8 cron orchestrator bash scripts",
            "[RETRIEVAL_GATE] Build retrieval-needed classifier in clarvis/brain/retrieval_gate.py",
            "[RESEARCH_DISCOVERY] Research: MemOS — Memory Operating System for AI Agents",
            "[PARALLEL_BRAIN_RECALL] Implement parallel collection queries in brain.py recall()",
            "[BACKUP] Run backup_daily.sh and verify",
        ]
        results = dry_run(sample_tasks)
        print(json.dumps(results, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "classify":
        task = " ".join(sys.argv[2:])
        tier = classify_retrieval(task)
        print(json.dumps(tier.to_dict(), indent=2))
    else:
        print("Usage:")
        print("  python3 -m clarvis.brain.retrieval_gate dry-run")
        print("  python3 -m clarvis.brain.retrieval_gate classify <task text>")
        sys.exit(0)
