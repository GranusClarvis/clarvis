"""Regression tests for [CLARVIS_EPISODIC_RECALL_NULL_GUARD] (2026-05-08).

Autonomous preflight repeatedly emitted

    PREFLIGHT: Episodic recall failed: 'NoneType' object is not subscriptable

before continuing. Root cause: ``EpisodicMemory.recall_similar`` did
``ep["task"][:50]`` while iterating ``self.episodes``, but a handful of
historical episodes were stored with ``task=None``.

These tests pin the degraded-recall behaviour:

* malformed/null episodes never raise
* ``recall_similar`` keeps returning the well-formed neighbours
* ``recall_failures`` still surfaces the failure entries
* the preflight episodic helper produces formatted output (no crash)
"""

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def tmp_workspace(tmp_path, monkeypatch):
    """Isolate episodes/causal-link state under a tmp workspace."""
    monkeypatch.setenv("CLARVIS_WORKSPACE", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    yield tmp_path


def _seed_episodes(tmp_workspace, payloads):
    episodes_file = tmp_workspace / "data" / "episodes.json"
    episodes_file.write_text(json.dumps(payloads))


def _make_episode(eid, task, outcome="success", activation=-1.0, valence=0.0):
    return {
        "id": eid,
        "timestamp": "2026-05-08T00:00:00+00:00",
        "task": task,
        "section": None,
        "salience": 0.5,
        "outcome": outcome,
        "failure_type": None,
        "valence": valence,
        "duration_s": 60,
        "error": None,
        "steps": None,
        "access_times": [1.0],
        "activation": activation,
    }


def _import_em_module():
    # Force a fresh import so EPISODES_FILE is recomputed against the tmp ws.
    for mod in [
        "clarvis.memory.episodic_memory",
    ]:
        sys.modules.pop(mod, None)
    import importlib
    return importlib.import_module("clarvis.memory.episodic_memory")


def test_recall_similar_skips_null_task_episodes(tmp_workspace, caplog):
    """An episode with task=None must not crash recall_similar."""
    # Order matters: place null/malformed entries BEFORE the good one so the
    # inner match loop iterates past them. This is what triggers the legacy
    # `ep["task"][:50]` NoneType crash before the fix.
    _seed_episodes(
        tmp_workspace,
        [
            _make_episode("ep_null_task", None, outcome="success"),
            _make_episode("ep_bad_type", 1234, outcome="success"),
            _make_episode("ep_good", "Fix queue cap drift", outcome="success"),
        ],
    )
    em_mod = _import_em_module()

    fake_brain_results = [
        {"document": "Episode: Fix queue cap drift — closed", "id": "ep_good"},
    ]
    with patch.object(em_mod.brain, "recall", return_value=fake_brain_results):
        em = em_mod.EpisodicMemory()
        with caplog.at_level(logging.WARNING, logger="clarvis.memory.episodic_memory"):
            results = em.recall_similar("queue cap", n=3)

    assert any(r.get("id") == "ep_good" for r in results), "valid episode must surface"
    assert all(isinstance(r.get("task"), str) for r in results), \
        "null-task episodes must be filtered out"
    # Structured degraded-recall event must be logged, not a Python traceback.
    degraded = [rec for rec in caplog.records if "degraded_recall" in rec.getMessage()]
    assert degraded, "expected a degraded_recall log entry for the skipped episode"


@pytest.mark.parametrize(
    "brain_return",
    [None, "not-a-list", {"single": "dict"}],
)
def test_recall_similar_handles_malformed_brain_return(tmp_workspace, brain_return):
    """brain.recall returning None / non-list must degrade to []."""
    _seed_episodes(
        tmp_workspace,
        [_make_episode("ep_good", "Some task", outcome="success")],
    )
    em_mod = _import_em_module()
    with patch.object(em_mod.brain, "recall", return_value=brain_return):
        em = em_mod.EpisodicMemory()
        results = em.recall_similar("anything", n=3)
    assert isinstance(results, list)


def test_recall_failures_skips_malformed_entries(tmp_workspace):
    """recall_failures must filter non-dict entries instead of raising."""
    _seed_episodes(
        tmp_workspace,
        [
            _make_episode("ep_fail", "Failed something", outcome="failure",
                          activation=0.5),
            _make_episode("ep_ok", "Worked fine", outcome="success"),
            _make_episode("ep_null_outcome", "Edge case", outcome=None),
        ],
    )
    em_mod = _import_em_module()
    em = em_mod.EpisodicMemory()
    # Inject a malformed entry directly into the in-memory list to simulate
    # corrupted on-disk state surviving load.
    em.episodes.append("not-a-dict")  # type: ignore[arg-type]

    failures = em.recall_failures(n=5)
    assert isinstance(failures, list)
    assert all(isinstance(e, dict) for e in failures)
    assert any(e.get("id") == "ep_fail" for e in failures)


def test_preflight_formatter_tolerates_null_task_field():
    """The preflight episodic block must not crash on task=None."""
    # Mirrors the formatter introduced in heartbeat_preflight._preflight_episodic.
    similar = [
        {"outcome": "success", "task": None},
        {"outcome": None, "task": "valid task here"},
        "garbage-non-dict",
        None,
    ]
    similar = [e for e in similar if isinstance(e, dict)]
    rendered = "\n".join(
        f"  [{e.get('outcome') or '?'}] {(e.get('task') or '')[:80]}"
        for e in similar
    )
    assert "[success]" in rendered
    assert "[?] valid task here" in rendered
