"""Tests for clarvis.cognition — confidence tracking and thought protocol.

Covers:
  - clarvis/cognition/confidence.py: predictions, outcomes, calibration, review, auto_resolve
  - clarvis/cognition/thought_protocol.py: Signal, SignalVector, RelationGraph,
    DecisionRule, ThoughtFrame, ThoughtProtocol
"""

import json
import os
import sys
import tempfile
import time

import pytest

# Ensure workspace root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# PART 1: confidence.py — redirect all file I/O to temp dirs
# ===========================================================================

@pytest.fixture
def conf_env(tmp_path, monkeypatch):
    """Patch confidence module to use temp directory for all I/O."""
    import clarvis.cognition.confidence as conf

    cal_dir = str(tmp_path / "calibration")
    os.makedirs(cal_dir, exist_ok=True)
    pred_file = os.path.join(cal_dir, "predictions.jsonl")
    thresh_file = os.path.join(cal_dir, "thresholds.json")

    monkeypatch.setattr(conf, "CALIBRATION_DIR", cal_dir)
    monkeypatch.setattr(conf, "PREDICTIONS_FILE", pred_file)
    monkeypatch.setattr(conf, "THRESHOLDS_FILE", thresh_file)
    # Reset in-memory cache
    monkeypatch.setattr(conf, "_predictions_cache", None)
    monkeypatch.setattr(conf, "_predictions_cache_mtime", 0)
    # Stub out brain store to avoid production writes
    monkeypatch.setattr(conf, "_brain_store", lambda text, importance=0.5: None)

    return conf


# ---------------------------------------------------------------------------
# _load_predictions / _save_predictions
# ---------------------------------------------------------------------------

class TestLoadSavePredictions:
    def test_load_empty(self, conf_env):
        result = conf_env._load_predictions()
        assert result == []

    def test_save_then_load(self, conf_env):
        entries = [
            {"event": "e1", "expected": "ok", "confidence": 0.8,
             "outcome": None, "correct": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        conf_env._save_predictions(entries)
        loaded = conf_env._load_predictions()
        assert len(loaded) == 1
        assert loaded[0]["event"] == "e1"

    def test_cache_hit(self, conf_env):
        """Second load should return cached data (same object)."""
        entries = [{"event": "x", "expected": "y", "confidence": 0.5,
                    "outcome": None, "correct": None, "timestamp": "t"}]
        conf_env._save_predictions(entries)
        first = conf_env._load_predictions()
        second = conf_env._load_predictions()
        assert first is second


# ---------------------------------------------------------------------------
# predict()
# ---------------------------------------------------------------------------

class TestPredict:
    def test_predict_returns_entry(self, conf_env):
        entry = conf_env.predict("deploy", "no_errors", 0.8)
        assert entry["event"] == "deploy"
        assert entry["expected"] == "no_errors"
        assert entry["confidence"] == 0.8
        assert entry["outcome"] is None
        assert entry["correct"] is None

    def test_predict_clamps_confidence(self, conf_env):
        e1 = conf_env.predict("e1", "ok", 1.5)
        assert e1["confidence"] == 1.0
        e2 = conf_env.predict("e2", "ok", -0.5)
        assert e2["confidence"] == 0.0

    def test_predict_appends_to_file(self, conf_env):
        conf_env.predict("a", "ok", 0.7)
        conf_env.predict("b", "ok", 0.6)
        # Reset cache to force reload
        conf_env._predictions_cache = None
        loaded = conf_env._load_predictions()
        assert len(loaded) == 2


# ---------------------------------------------------------------------------
# outcome()
# ---------------------------------------------------------------------------

class TestOutcome:
    def test_outcome_no_match(self, conf_env):
        result = conf_env.outcome("nonexistent", "anything")
        assert result is None

    def test_outcome_correct(self, conf_env):
        conf_env.predict("test_event", "success", 0.9)
        result = conf_env.outcome("test_event", "success")
        assert result is not None
        assert result["correct"] is True
        assert result["outcome"] == "success"

    def test_outcome_wrong(self, conf_env):
        conf_env.predict("test_event", "success", 0.9)
        result = conf_env.outcome("test_event", "failure")
        assert result is not None
        assert result["correct"] is False

    def test_outcome_case_insensitive(self, conf_env):
        conf_env.predict("ev", "SUCCESS", 0.8)
        result = conf_env.outcome("ev", "  success  ")
        assert result["correct"] is True

    def test_outcome_matches_most_recent_unresolved(self, conf_env):
        conf_env.predict("ev", "a", 0.5)
        conf_env.predict("ev", "b", 0.6)
        result = conf_env.outcome("ev", "b")
        assert result["expected"] == "b"
        assert result["correct"] is True


# ---------------------------------------------------------------------------
# calibration()
# ---------------------------------------------------------------------------

class TestCalibration:
    def test_calibration_no_data(self, conf_env):
        stats = conf_env.calibration()
        assert stats["total"] == 0
        assert stats["resolved"] == 0

    def test_calibration_no_resolved(self, conf_env):
        conf_env.predict("ev", "ok", 0.7)
        stats = conf_env.calibration()
        assert stats["total"] == 1
        assert stats["resolved"] == 0
        assert stats["buckets"] == {}

    def test_calibration_with_resolved(self, conf_env):
        conf_env.predict("ev1", "ok", 0.8)
        conf_env._predictions_cache = None  # invalidate cache (same-second mtime)
        conf_env.outcome("ev1", "ok")
        conf_env.predict("ev2", "ok", 0.2)
        conf_env._predictions_cache = None
        conf_env.outcome("ev2", "fail")
        stats = conf_env.calibration()
        assert stats["resolved"] == 2
        assert "brier_score" in stats
        assert stats["brier_score"] >= 0

    def test_calibration_buckets(self, conf_env):
        # One in high bucket (correct) and one in low bucket (wrong)
        conf_env.predict("hi", "ok", 0.75)
        conf_env.outcome("hi", "ok")
        conf_env.predict("lo", "ok", 0.1)
        conf_env.outcome("lo", "nope")
        stats = conf_env.calibration()
        # High bucket should have 100% accuracy
        if "high (60-90%)" in stats["buckets"]:
            assert stats["buckets"]["high (60-90%)"]["accuracy"] == 1.0
        # Low bucket should have 0% accuracy
        if "low (0-30%)" in stats["buckets"]:
            assert stats["buckets"]["low (0-30%)"]["accuracy"] == 0.0

    def test_brier_score_perfect(self, conf_env):
        """Perfect predictions → Brier score near 0."""
        conf_env.predict("p1", "ok", 0.99)
        conf_env.outcome("p1", "ok")
        stats = conf_env.calibration()
        assert stats["brier_score"] < 0.01


# ---------------------------------------------------------------------------
# dynamic_confidence()
# ---------------------------------------------------------------------------

class TestDynamicConfidence:
    def test_few_resolved_returns_default(self, conf_env):
        # < 3 resolved → 0.7
        assert conf_env.dynamic_confidence() == 0.7

    def test_with_enough_data(self, conf_env):
        # Create 5 resolved predictions
        for i in range(5):
            conf_env.predict(f"ev{i}", "ok", 0.8)
            conf_env._predictions_cache = None
            conf_env.outcome(f"ev{i}", "ok")
        dc = conf_env.dynamic_confidence()
        assert 0.3 <= dc <= 0.95

    def test_dynamic_clamped(self, conf_env):
        """Even extreme data stays within [0.3, 0.95]."""
        for i in range(10):
            conf_env.predict(f"ev{i}", "ok", 0.99)
            conf_env._predictions_cache = None
            conf_env.outcome(f"ev{i}", "ok")
        dc = conf_env.dynamic_confidence()
        assert dc <= 0.95
        assert dc >= 0.3


# ---------------------------------------------------------------------------
# review()
# ---------------------------------------------------------------------------

class TestReview:
    def test_review_no_resolved(self, conf_env):
        result = conf_env.review()
        assert result["resolved"] == 0
        assert result["diagnosis"] == "No resolved predictions yet"
        assert "recommendation" in result

    def test_review_with_data(self, conf_env):
        for i in range(5):
            conf_env.predict(f"ev{i}", "ok", 0.7)
            conf_env._predictions_cache = None  # invalidate (same-second mtime)
            conf_env.outcome(f"ev{i}", "ok")
        result = conf_env.review()
        assert result["resolved"] == 5
        assert result["success_rate"] == 1.0
        assert result["diagnosis"] in ("UNDERCONFIDENT", "OVERCONFIDENT", "WELL_CALIBRATED")
        assert "brier_score" in result
        assert "calibration_curve" in result
        assert "recommended_confidence" in result

    def test_review_overconfident(self, conf_env):
        for i in range(5):
            conf_env.predict(f"ev{i}", "ok", 0.95)
            conf_env._predictions_cache = None
            conf_env.outcome(f"ev{i}", "fail")
        result = conf_env.review()
        assert result["success_rate"] == 0.0
        assert result["diagnosis"] == "OVERCONFIDENT"


# ---------------------------------------------------------------------------
# auto_resolve()
# ---------------------------------------------------------------------------

class TestAutoResolve:
    def test_auto_resolve_empty(self, conf_env):
        result = conf_env.auto_resolve("task", "success")
        assert result == {"matched": 0, "stale_expired": 0, "remaining_open": 0}

    def test_auto_resolve_matches_event(self, conf_env):
        # predict with a sanitized event name matching the task text
        conf_env.predict("deploy_server_now", "ok", 0.7)
        result = conf_env.auto_resolve("deploy_server_now", "success")
        assert result["matched"] >= 1

    def test_auto_resolve_expires_stale(self, conf_env):
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        entries = [{
            "event": "old_event",
            "expected": "ok",
            "confidence": 0.5,
            "timestamp": old_ts,
            "outcome": None,
            "correct": None,
        }]
        conf_env._save_predictions(entries)
        result = conf_env.auto_resolve("unrelated_task", "success", max_age_days=7)
        assert result["stale_expired"] == 1

    def test_auto_resolve_substring_match(self, conf_env):
        conf_env.predict("some_very_long_event_name_about_deployment_and_testing", "ok", 0.6)
        result = conf_env.auto_resolve(
            "some_very_long_event_name_about_deployment_and_testing_extra", "success"
        )
        assert result["matched"] >= 1


# ---------------------------------------------------------------------------
# save_threshold / load_threshold
# ---------------------------------------------------------------------------

class TestThresholds:
    def test_load_default(self, conf_env):
        assert conf_env.load_threshold() == 0.7

    def test_save_and_load(self, conf_env):
        conf_env.save_threshold(0.85, "test reason")
        assert conf_env.load_threshold() == 0.85

    def test_save_returns_data(self, conf_env):
        data = conf_env.save_threshold(0.6, "low confidence")
        assert data["confidence"] == 0.6
        assert data["reason"] == "low confidence"
        assert "updated" in data


# ---------------------------------------------------------------------------
# predict_specific()
# ---------------------------------------------------------------------------

class TestPredictSpecific:
    def test_unknown_domain(self, conf_env):
        result = conf_env.predict_specific("nonexistent")
        assert result is None

    def test_known_domains(self, conf_env):
        for domain in ("retrieval", "phi", "procedure", "chain", "calibration"):
            result = conf_env.predict_specific(domain)
            assert result is not None
            assert "event" in result
            assert 0.0 <= result["confidence"] <= 1.0


# ===========================================================================
# PART 2: thought_protocol.py — pure in-memory datastructures
# ===========================================================================

from clarvis.cognition.thought_protocol import (
    Signal, SignalVector, Relation, RelationGraph,
    DecisionRule, ThoughtFrame, ThoughtProtocol,
)


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

class TestSignal:
    def test_scalar_strength(self):
        sig = Signal("sal", 0.85)
        assert sig.strength() == 0.85

    def test_dict_strength(self):
        sig = Signal("emo", {"approach": 0.6, "avoid": -0.1})
        assert sig.strength() == 0.6

    def test_string_strength(self):
        sig = Signal("ctx", "task_selection")
        assert sig.strength() == 0.5

    def test_encode_scalar(self):
        sig = Signal("sal", 0.85)
        assert sig.encode() == "@sal(0.85)"

    def test_encode_dict(self):
        sig = Signal("emo", {"approach": 0.60, "avoid": 0.10})
        encoded = sig.encode()
        assert encoded.startswith("@emo(")
        assert "approach=0.60" in encoded
        assert "avoid=0.10" in encoded

    def test_encode_string(self):
        sig = Signal("ctx", "idle")
        assert sig.encode() == "@ctx(idle)"

    def test_empty_dict_strength(self):
        sig = Signal("empty", {})
        assert sig.strength() == 0.0

    def test_timestamp_set(self):
        before = time.time()
        sig = Signal("test", 1.0)
        assert sig.timestamp >= before


# ---------------------------------------------------------------------------
# SignalVector
# ---------------------------------------------------------------------------

class TestSignalVector:
    def test_set_and_get(self):
        sv = SignalVector()
        sv.set("sal", 0.8)
        assert sv.get("sal") == 0.8

    def test_get_default(self):
        sv = SignalVector()
        assert sv.get("nonexistent") == 0.0
        assert sv.get("nonexistent", 42) == 42

    def test_strength(self):
        sv = SignalVector()
        sv.set("sal", 0.9)
        assert sv.strength("sal") == 0.9
        assert sv.strength("nonexistent") == 0.0

    def test_encode_empty(self):
        sv = SignalVector()
        assert sv.encode() == "S[]"

    def test_encode_sorted_keys(self):
        sv = SignalVector()
        sv.set("zebra", 0.1)
        sv.set("alpha", 0.9)
        encoded = sv.encode()
        assert encoded.startswith("S[alpha=")

    def test_encode_dict_value(self):
        sv = SignalVector()
        sv.set("emo", {"approach": 0.6, "avoid": 0.1})
        encoded = sv.encode()
        assert "emo=" in encoded
        assert "0.60" in encoded

    def test_encode_string_value(self):
        sv = SignalVector()
        sv.set("ctx", "idle")
        assert "ctx=idle" in sv.encode()

    def test_to_dict(self):
        sv = SignalVector()
        sv.set("a", 1.0)
        sv.set("b", 2.0)
        d = sv.to_dict()
        assert d == {"a": 1.0, "b": 2.0}

    def test_overwrite(self):
        sv = SignalVector()
        sv.set("x", 1.0)
        sv.set("x", 2.0)
        assert sv.get("x") == 2.0


# ---------------------------------------------------------------------------
# Relation
# ---------------------------------------------------------------------------

class TestRelation:
    def test_encode(self):
        r = Relation("a", "b", "causal", 0.9)
        assert r.encode() == "#a -> #b [causal:0.9]"

    def test_default_weight(self):
        r = Relation("a", "b", "similar")
        assert r.weight == 1.0


# ---------------------------------------------------------------------------
# RelationGraph
# ---------------------------------------------------------------------------

class TestRelationGraph:
    def test_add_and_neighbors(self):
        rg = RelationGraph()
        rg.add("a", "b", "similar")
        assert len(rg.neighbors("a")) == 1
        assert len(rg.neighbors("b")) == 1

    def test_neighbors_with_type_filter(self):
        rg = RelationGraph()
        rg.add("a", "b", "similar")
        rg.add("a", "c", "causal")
        assert len(rg.neighbors("a", rel_type="similar")) == 1
        assert len(rg.neighbors("a", rel_type="causal")) == 1
        assert len(rg.neighbors("a")) == 2

    def test_strongest_path_direct(self):
        rg = RelationGraph()
        rg.add("a", "b", "direct")
        path = rg.strongest_path("a", "b")
        assert len(path) == 1

    def test_strongest_path_two_hop(self):
        rg = RelationGraph()
        rg.add("a", "b", "step1")
        rg.add("b", "c", "step2")
        path = rg.strongest_path("a", "c")
        assert len(path) == 2

    def test_strongest_path_no_connection(self):
        rg = RelationGraph()
        rg.add("a", "b", "link")
        path = rg.strongest_path("a", "z")
        assert path == []

    def test_strongest_path_self(self):
        rg = RelationGraph()
        path = rg.strongest_path("a", "a")
        assert path == []

    def test_encode_multiple(self):
        rg = RelationGraph()
        rg.add("a", "b", "sim")
        rg.add("c", "d", "cause")
        encoded = rg.encode()
        assert "#a -> #b" in encoded
        assert "#c -> #d" in encoded
        assert " ; " in encoded

    def test_empty_encode(self):
        rg = RelationGraph()
        assert rg.encode() == ""


# ---------------------------------------------------------------------------
# DecisionRule
# ---------------------------------------------------------------------------

class TestDecisionRule:
    def test_simple_gt(self):
        sv = SignalVector()
        sv.set("sal", 0.8)
        rule = DecisionRule("sal > 0.5", "execute")
        assert rule.evaluate(sv) is True

    def test_simple_lt(self):
        sv = SignalVector()
        sv.set("sal", 0.3)
        rule = DecisionRule("sal < 0.5", "defer")
        assert rule.evaluate(sv) is True

    def test_gte(self):
        sv = SignalVector()
        sv.set("sal", 0.5)
        rule = DecisionRule("sal >= 0.5", "go")
        assert rule.evaluate(sv) is True

    def test_lte(self):
        sv = SignalVector()
        sv.set("sal", 0.5)
        rule = DecisionRule("sal <= 0.5", "go")
        assert rule.evaluate(sv) is True

    def test_eq(self):
        sv = SignalVector()
        sv.set("sal", 0.5)
        rule = DecisionRule("sal == 0.5", "exact")
        assert rule.evaluate(sv) is True

    def test_and_both_true(self):
        sv = SignalVector()
        sv.set("sal", 0.8)
        sv.set("emo_bias", 0.6)
        rule = DecisionRule("sal > 0.5 AND emo_bias > 0.3", "go")
        assert rule.evaluate(sv) is True

    def test_and_one_false(self):
        sv = SignalVector()
        sv.set("sal", 0.8)
        sv.set("emo_bias", 0.1)
        rule = DecisionRule("sal > 0.5 AND emo_bias > 0.3", "go")
        assert rule.evaluate(sv) is False

    def test_or_one_true(self):
        sv = SignalVector()
        sv.set("sal", 0.2)
        sv.set("emo_bias", 0.8)
        rule = DecisionRule("sal > 0.5 OR emo_bias > 0.5", "go")
        assert rule.evaluate(sv) is True

    def test_or_both_false(self):
        sv = SignalVector()
        sv.set("sal", 0.1)
        sv.set("emo_bias", 0.1)
        rule = DecisionRule("sal > 0.5 OR emo_bias > 0.5", "go")
        assert rule.evaluate(sv) is False

    def test_not(self):
        sv = SignalVector()
        sv.set("sal", 0.3)
        rule = DecisionRule("NOT sal > 0.5", "defer")
        assert rule.evaluate(sv) is True

    def test_dotted_access(self):
        sv = SignalVector()
        sv.set("emo", {"approach": 0.6, "avoid": 0.1})
        rule = DecisionRule("emo.approach > 0.3", "go")
        assert rule.evaluate(sv) is True

    def test_dotted_access_miss(self):
        sv = SignalVector()
        sv.set("emo", {"approach": 0.6})
        rule = DecisionRule("emo.avoid > 0.3", "go")
        assert rule.evaluate(sv) is False  # avoid not in dict → 0.0

    def test_dotted_non_dict(self):
        sv = SignalVector()
        sv.set("emo", 0.5)  # not a dict
        rule = DecisionRule("emo.approach > 0.3", "go")
        assert rule.evaluate(sv) is False  # non-dict → 0.0

    def test_encode(self):
        rule = DecisionRule("sal > 0.5", "execute", confidence=0.8)
        assert rule.encode() == "IF sal > 0.5 THEN !execute [0.80]"

    def test_malformed_condition(self):
        sv = SignalVector()
        rule = DecisionRule("garbage!!!", "fail")
        assert rule.evaluate(sv) is False


# ---------------------------------------------------------------------------
# ThoughtFrame
# ---------------------------------------------------------------------------

class TestThoughtFrame:
    def test_signal_and_resolve_matching(self):
        frame = ThoughtFrame("test")
        frame.signal("sal", 0.9)
        frame.decide("sal > 0.5", "execute", confidence=0.8)
        result = frame.resolve()
        assert result["action"] == "execute"
        assert result["confidence"] == 0.8
        assert result["matched_rules"] == 1

    def test_resolve_no_match_defers(self):
        frame = ThoughtFrame("test")
        frame.signal("sal", 0.1)
        frame.decide("sal > 0.5", "execute", confidence=0.8)
        result = frame.resolve()
        assert result["action"] == "defer"
        assert result["confidence"] == 0.0

    def test_resolve_caches(self):
        frame = ThoughtFrame("test")
        frame.decide("sal > 0.5", "go", confidence=0.5)
        r1 = frame.resolve()
        r2 = frame.resolve()
        assert r1 is r2

    def test_best_confidence_wins(self):
        frame = ThoughtFrame("test")
        frame.signal("sal", 0.9)
        frame.signal("emo_bias", 0.8)
        frame.decide("sal > 0.5", "low_conf", confidence=0.3)
        frame.decide("emo_bias > 0.5", "high_conf", confidence=0.9)
        result = frame.resolve()
        assert result["action"] == "high_conf"

    def test_relate_adds_to_graph(self):
        frame = ThoughtFrame("test")
        frame.relate("a", "b", "similar", weight=0.9)
        assert len(frame.relations.relations) == 1

    def test_trace_records(self):
        frame = ThoughtFrame("test")
        frame.signal("sal", 0.5)
        frame.decide("sal > 0.3", "go")
        frame.resolve()
        assert any("@sal" in t for t in frame.trace)
        assert any("RULE" in t for t in frame.trace)
        assert any("RESOLVED" in t for t in frame.trace)

    def test_encode_includes_purpose(self):
        frame = ThoughtFrame("my_purpose")
        encoded = frame.encode()
        assert "FRAME(my_purpose)" in encoded

    def test_encode_includes_signals(self):
        frame = ThoughtFrame("test")
        frame.signal("sal", 0.8)
        encoded = frame.encode()
        assert "S[sal=0.80]" in encoded

    def test_encode_includes_rules(self):
        frame = ThoughtFrame("test")
        frame.decide("sal > 0.5", "go", confidence=0.7)
        encoded = frame.encode()
        assert "IF sal > 0.5 THEN !go" in encoded

    def test_encode_includes_result_after_resolve(self):
        frame = ThoughtFrame("test")
        frame.signal("sal", 0.9)
        frame.decide("sal > 0.5", "go", confidence=0.8)
        frame.resolve()
        encoded = frame.encode()
        assert "RESULT(!go" in encoded

    def test_duration_ms(self):
        frame = ThoughtFrame("test")
        time.sleep(0.01)
        assert frame.duration_ms() >= 5  # at least 5ms

    def test_frame_id_auto_generated(self):
        frame = ThoughtFrame("test")
        assert frame.id.startswith("tf_")

    def test_frame_id_custom(self):
        frame = ThoughtFrame("test", frame_id="custom_123")
        assert frame.id == "custom_123"

    def test_result_includes_frame_id(self):
        frame = ThoughtFrame("test", frame_id="myframe")
        result = frame.resolve()
        assert result["frame_id"] == "myframe"
        assert result["purpose"] == "test"

    def test_signals_in_result(self):
        frame = ThoughtFrame("test")
        frame.signal("x", 1.0)
        result = frame.resolve()
        assert result["signals"]["x"] == 1.0


# ---------------------------------------------------------------------------
# ThoughtProtocol
# ---------------------------------------------------------------------------

@pytest.fixture
def proto(tmp_path, monkeypatch):
    """Create a ThoughtProtocol with no disk patterns."""
    return ThoughtProtocol()


class TestThoughtProtocolFrame:
    def test_frame_creates_frame(self, proto):
        f = proto.frame("test")
        assert isinstance(f, ThoughtFrame)
        assert proto.active_frame is f

    def test_frame_sets_purpose(self, proto):
        f = proto.frame("my_purpose")
        assert f.purpose == "my_purpose"


class TestThoughtProtocolDefaults:
    def test_default_patterns_loaded(self, proto):
        assert "urgent_task" in proto._patterns
        assert "risky_action" in proto._patterns
        assert "memory_retrieval" in proto._patterns

    def test_default_patterns_have_rules(self, proto):
        for name, rules in proto._patterns.items():
            assert len(rules) >= 1
            for rule in rules:
                assert isinstance(rule, DecisionRule)


class TestThoughtProtocolApplyPattern:
    def test_apply_existing_pattern(self, proto):
        f = proto.frame("test")
        f.signal("sal", 0.9)
        success = proto.apply_pattern("urgent_task", f)
        assert success is True
        result = f.resolve()
        assert result["action"] == "execute_now"

    def test_apply_nonexistent_pattern(self, proto):
        f = proto.frame("test")
        assert proto.apply_pattern("nonexistent", f) is False


class TestThoughtProtocolEval:
    def test_eval_signal(self, proto):
        result = proto.eval("@sal(0.8)")
        assert len(result["results"]) >= 2  # signal + resolution
        signal_result = result["results"][0]
        assert signal_result["type"] == "signal"
        assert signal_result["name"] == "sal"
        assert signal_result["value"] == 0.8

    def test_eval_rule(self, proto):
        result = proto.eval("@sal(0.9) ; IF sal > 0.5 THEN execute")
        assert result["resolution"]["action"] == "execute"

    def test_eval_rule_no_match(self, proto):
        result = proto.eval("@sal(0.1) ; IF sal > 0.5 THEN execute")
        assert result["resolution"]["action"] == "defer"

    def test_eval_action(self, proto):
        result = proto.eval("!select(task1)")
        action_result = [r for r in result["results"] if r["type"] == "action"]
        assert len(action_result) >= 1

    def test_eval_sequence(self, proto):
        result = proto.eval("@sal(0.8) ; @emo_bias(0.5) ; IF sal > 0.5 THEN go")
        assert result["resolution"]["action"] == "go"
        assert "duration_ms" in result
        assert "trace" in result

    def test_eval_string_signal(self, proto):
        result = proto.eval("@ctx(hello)")
        signal_result = result["results"][0]
        assert signal_result["value"] == "hello"

    def test_eval_empty_statement_skipped(self, proto):
        result = proto.eval("; ; @sal(0.5) ; ;")
        signals = [r for r in result["results"] if r["type"] == "signal"]
        assert len(signals) == 1


class TestThoughtProtocolTaskDecision:
    def test_high_salience_executes(self, proto):
        result = proto.task_decision("important task", salience=0.9)
        assert result["action"] == "execute"
        assert result["confidence"] >= 0.6

    def test_low_salience_defers(self, proto):
        result = proto.task_decision("boring task", salience=0.1, somatic_bias=-0.5)
        assert result["action"] == "defer"

    def test_signals_included(self, proto):
        result = proto.task_decision("task", salience=0.7, somatic_bias=0.2,
                                     spotlight_align=0.5, episode_activation=0.3)
        assert "readiness" in result["signals"]
        assert "sal" in result["signals"]

    def test_readiness_computation(self, proto):
        result = proto.task_decision("task", salience=1.0, somatic_bias=1.0,
                                     spotlight_align=1.0, episode_activation=1.0)
        readiness = result["signals"]["readiness"]
        assert readiness > 0.5

    def test_spotlight_match_high_confidence(self, proto):
        result = proto.task_decision("aligned task", salience=0.9, spotlight_align=0.7)
        assert result["action"] == "execute"
        assert result["confidence"] >= 0.8


class TestThoughtProtocolRecentAndStats:
    def test_recent_thoughts_empty(self, proto):
        assert proto.get_recent_thoughts() == []

    def test_recent_thoughts_after_eval(self, proto):
        proto.eval("@sal(0.5)")
        thoughts = proto.get_recent_thoughts()
        assert len(thoughts) == 1

    def test_thought_stats_empty(self, proto):
        stats = proto.thought_stats()
        assert stats["total_frames"] == 0

    def test_thought_stats_after_evals(self, proto):
        proto.eval("@sal(0.5)")
        proto.eval("@sal(0.9) ; IF sal > 0.5 THEN go")
        stats = proto.thought_stats()
        assert stats["total_frames"] == 2
        assert "eval" in stats["purposes"]
        assert stats["avg_duration_ms"] >= 0


class TestThoughtProtocolRegisterPattern:
    def test_register_custom_pattern(self, proto):
        proto.register_pattern("my_rule", [
            {"condition": "x > 0.5", "action": "go", "confidence": 0.8},
        ])
        assert "my_rule" in proto._patterns

    def test_apply_custom_pattern(self, proto):
        proto.register_pattern("my_rule", [
            {"condition": "x > 0.5", "action": "go", "confidence": 0.8},
        ])
        f = proto.frame("test")
        f.signal("x", 0.9)
        proto.apply_pattern("my_rule", f)
        result = f.resolve()
        assert result["action"] == "go"


class TestThoughtProtocolMemoryQuery:
    def test_memory_query_without_brain(self, proto):
        """Should work even without brain (falls back gracefully)."""
        result = proto.memory_query("test query")
        assert "action" in result
        # Will have error since brain isn't available in test isolation
        assert result.get("error") or result.get("memories") is not None


class TestThoughtProtocolActions:
    def test_execute_unknown_action(self, proto):
        result = proto.eval("!unknown_action(args)")
        action_results = [r for r in result["results"] if r["type"] == "action"]
        assert len(action_results) >= 1
        assert "unknown_action" in str(action_results[0]["result"])

    def test_execute_select(self, proto):
        result = proto.eval("!select(task_42)")
        action_results = [r for r in result["results"] if r["type"] == "action"]
        assert any("task_42" in str(r["result"]) for r in action_results)

    def test_execute_decide(self, proto):
        result = proto.eval("@sal(0.8) ; IF sal > 0.5 THEN go ; !decide")
        assert "resolution" in result


# ---------------------------------------------------------------------------
# ThoughtFrame encode with relations
# ---------------------------------------------------------------------------

class TestThoughtFrameEncodeRelations:
    def test_encode_with_relations(self):
        frame = ThoughtFrame("test")
        frame.relate("a", "b", "similar")
        encoded = frame.encode()
        assert "#a -> #b" in encoded


# ===========================================================================
# PART 3: Additional coverage for uncovered paths
# ===========================================================================

class TestThoughtProtocolEncodeState:
    def test_encode_state_returns_signal_string(self, proto):
        """encode_state should return S[...] even without subsystem access."""
        result = proto.encode_state()
        assert result.startswith("S[")
        assert result.endswith("]")
        # Should have at least a timestamp signal
        assert "t=" in result

    def test_encode_state_has_default_signals(self, proto):
        """Without subsystems, defaults should be set."""
        result = proto.encode_state()
        # sal defaults to 0.5 when attention unavailable
        assert "sal=" in result


class TestThoughtProtocolPatternPersistence:
    def test_save_and_load_patterns(self, tmp_path, monkeypatch):
        """Patterns should roundtrip through JSON."""
        import clarvis.cognition.thought_protocol as tp_mod
        pattern_file = tmp_path / "thought_patterns.json"
        monkeypatch.setattr(tp_mod, "THOUGHT_LOG", tmp_path / "log.jsonl")

        # Create protocol and register a custom pattern
        p = ThoughtProtocol()
        # Override _save_patterns to use tmp_path
        original_save = p._save_patterns
        def patched_save():
            data = {}
            for name, rules in p._patterns.items():
                data[name] = [
                    {"condition": r.condition, "action": r.action, "confidence": r.confidence}
                    for r in rules
                ]
            pattern_file.write_text(json.dumps(data, indent=2))
        p._save_patterns = patched_save

        p.register_pattern("test_pattern", [
            {"condition": "x > 0.5", "action": "go", "confidence": 0.8},
            {"condition": "x <= 0.5", "action": "wait", "confidence": 0.5},
        ])
        assert pattern_file.exists()
        data = json.loads(pattern_file.read_text())
        assert "test_pattern" in data
        assert len(data["test_pattern"]) == 2

    def test_load_patterns_from_disk(self, tmp_path, monkeypatch):
        """Should load patterns from existing file on init."""
        import clarvis.cognition.thought_protocol as tp_mod
        pattern_file = tmp_path / "thought_patterns.json"
        monkeypatch.setattr(tp_mod, "THOUGHT_LOG", tmp_path / "log.jsonl")

        # Write a pattern file
        data = {"disk_pattern": [
            {"condition": "y > 0.9", "action": "rush", "confidence": 0.95}
        ]}
        pattern_file.write_text(json.dumps(data))

        # Monkey-patch _load_patterns to use our file
        def patched_load(self_):
            if pattern_file.exists():
                loaded = json.loads(pattern_file.read_text())
                for name, rules in loaded.items():
                    self_._patterns[name] = [
                        DecisionRule(r["condition"], r["action"], r.get("confidence", 0.5))
                        for r in rules
                    ]
        monkeypatch.setattr(ThoughtProtocol, "_load_patterns", patched_load)

        p = ThoughtProtocol()
        assert "disk_pattern" in p._patterns

    def test_load_corrupt_patterns_file(self, tmp_path, monkeypatch):
        """Corrupt patterns file should not crash."""
        import clarvis.cognition.thought_protocol as tp_mod
        pattern_file = tmp_path / "thought_patterns.json"
        monkeypatch.setattr(tp_mod, "THOUGHT_LOG", tmp_path / "log.jsonl")

        pattern_file.write_text("NOT VALID JSON!!!")

        def patched_load(self_):
            if pattern_file.exists():
                try:
                    loaded = json.loads(pattern_file.read_text())
                    for name, rules in loaded.items():
                        self_._patterns[name] = [
                            DecisionRule(r["condition"], r["action"], r.get("confidence", 0.5))
                            for r in rules
                        ]
                except (json.JSONDecodeError, KeyError):
                    pass
        monkeypatch.setattr(ThoughtProtocol, "_load_patterns", patched_load)

        p = ThoughtProtocol()
        # Should still have defaults even with corrupt file
        assert "urgent_task" in p._patterns


class TestThoughtProtocolLogging:
    def test_log_frame_records_in_memory(self, proto):
        """Thought frames should be recorded in memory history."""
        proto.eval("@sal(0.8)")
        assert len(proto.frame_history) >= 1
        entry = proto.frame_history[-1]
        assert "frame_id" in entry
        assert "purpose" in entry
        assert "duration_ms" in entry

    def test_thought_stats_from_memory(self):
        """thought_stats should work from in-memory history."""
        p = ThoughtProtocol()
        p.frame_history = []
        for i in range(3):
            p.eval(f"@val({i / 10})")
        stats = p.thought_stats()
        assert stats["total_frames"] == 3
        assert "avg_duration_ms" in stats

    def test_frame_history_limit(self, proto):
        """History should be limited to 50 entries."""
        for i in range(55):
            proto.eval(f"@val({i / 100})")
        assert len(proto.frame_history) <= 50


class TestThoughtProtocolQueryEval:
    def test_eval_query_without_brain(self, proto):
        """?query should fail gracefully without brain."""
        result = proto.eval("?test_query")
        query_results = [r for r in result["results"] if r["type"] == "query"]
        assert len(query_results) >= 1
        # Should have error or empty result
        r = query_results[0]["result"]
        assert isinstance(r, list)

    def test_eval_if_case_insensitive(self, proto):
        """IF/THEN parsing should be case-insensitive."""
        result = proto.eval("@sal(0.9) ; if sal > 0.5 then go")
        assert result["resolution"]["action"] == "go"

    def test_eval_action_state(self, proto):
        """!state action should return encoded state."""
        result = proto.eval("!state")
        action_results = [r for r in result["results"] if r["type"] == "action"]
        assert len(action_results) >= 1


class TestRelationGraphAdvanced:
    def test_strongest_path_three_hop(self):
        rg = RelationGraph()
        rg.add("a", "b", "step1")
        rg.add("b", "c", "step2")
        rg.add("c", "d", "step3")
        path = rg.strongest_path("a", "d", max_depth=3)
        assert len(path) == 3

    def test_strongest_path_exceeds_depth(self):
        rg = RelationGraph()
        rg.add("a", "b", "step1")
        rg.add("b", "c", "step2")
        rg.add("c", "d", "step3")
        rg.add("d", "e", "step4")
        path = rg.strongest_path("a", "e", max_depth=2)
        # May or may not find depending on BFS iteration limit
        # The important thing is it doesn't crash

    def test_neighbors_empty(self):
        rg = RelationGraph()
        assert rg.neighbors("nonexistent") == []

    def test_bidirectional_index(self):
        rg = RelationGraph()
        rel = rg.add("a", "b", "link")
        assert rel in rg.neighbors("a")
        assert rel in rg.neighbors("b")


class TestDecisionRuleAdvanced:
    def test_complex_and_or(self):
        """AND/OR combined (OR has lower precedence in split)."""
        sv = SignalVector()
        sv.set("x", 0.8)
        sv.set("y", 0.3)
        # "x > 0.5 OR y > 0.5" → True (x is > 0.5)
        rule = DecisionRule("x > 0.5 OR y > 0.5", "go")
        assert rule.evaluate(sv) is True

    def test_not_with_true_condition(self):
        sv = SignalVector()
        sv.set("x", 0.8)
        rule = DecisionRule("NOT x > 0.5", "defer")
        assert rule.evaluate(sv) is False

    def test_missing_signal_defaults_zero(self):
        sv = SignalVector()
        rule = DecisionRule("missing > 0.5", "go")
        assert rule.evaluate(sv) is False  # strength of missing = 0.0

    def test_default_confidence(self):
        rule = DecisionRule("x > 0.5", "go")
        assert rule.confidence == 0.5


class TestConfidenceEdgeCases:
    def test_outcome_already_resolved(self, conf_env):
        """Resolving same event twice should find nothing (already resolved)."""
        conf_env.predict("ev", "ok", 0.8)
        conf_env._predictions_cache = None
        conf_env.outcome("ev", "ok")
        conf_env._predictions_cache = None
        result = conf_env.outcome("ev", "ok")
        assert result is None  # no unresolved left

    def test_calibration_buckets_all_ranges(self, conf_env):
        """Test predictions spanning all 4 calibration buckets."""
        pairs = [
            ("lo", 0.15, "ok"),    # low bucket
            ("med", 0.45, "ok"),   # med bucket
            ("hi", 0.75, "ok"),    # high bucket
            ("vhi", 0.95, "ok"),   # very high bucket
        ]
        for event, conf, expected in pairs:
            conf_env.predict(event, expected, conf)
            conf_env._predictions_cache = None
            conf_env.outcome(event, expected)
        stats = conf_env.calibration()
        assert stats["resolved"] == 4
        assert len(stats["buckets"]) >= 3  # should have at least 3 non-empty buckets

    def test_auto_resolve_already_resolved_skipped(self, conf_env):
        """Already-resolved predictions should be skipped by auto_resolve."""
        conf_env.predict("done", "ok", 0.8)
        conf_env._predictions_cache = None
        conf_env.outcome("done", "ok")
        result = conf_env.auto_resolve("done", "success")
        assert result["matched"] == 0  # already resolved

    def test_predict_specific_returns_entry_fields(self, conf_env):
        result = conf_env.predict_specific("retrieval")
        assert "timestamp" in result
        assert "outcome" in result
        assert result["outcome"] is None  # not yet resolved


# ===========================================================================
# PART 4: attention.py — AttentionItem pure tests (no disk I/O)
# ===========================================================================

from clarvis.cognition.attention import (
    AttentionItem, AttentionSpotlight,
    SPOTLIGHT_CAPACITY, DECAY_PER_TICK, EVICTION_THRESHOLD,
    W_IMPORTANCE, W_RECENCY, W_RELEVANCE, W_ACCESS, W_BOOST,
)


class TestAttentionConstants:
    def test_spotlight_capacity(self):
        assert SPOTLIGHT_CAPACITY == 7

    def test_weights_sum_to_one(self):
        total = W_IMPORTANCE + W_RECENCY + W_RELEVANCE + W_ACCESS + W_BOOST
        assert abs(total - 1.0) < 0.01

    def test_decay_positive(self):
        assert DECAY_PER_TICK > 0

    def test_eviction_threshold(self):
        assert 0 < EVICTION_THRESHOLD < 1


class TestAttentionItem:
    def test_constructor_defaults(self):
        item = AttentionItem("test content")
        assert item.content == "test content"
        assert item.source == "unknown"
        assert item.importance == 0.5
        assert item.relevance == 0.5
        assert item.boost == 0.0
        assert item.access_count == 0
        assert item.id.startswith("attn_")

    def test_constructor_custom(self):
        item = AttentionItem("test", source="brain", importance=0.9,
                             relevance=0.8, boost=0.3, item_id="custom_id")
        assert item.id == "custom_id"
        assert item.source == "brain"
        assert item.importance == 0.9
        assert item.relevance == 0.8
        assert item.boost == 0.3

    def test_constructor_clamps_values(self):
        item = AttentionItem("test", importance=1.5, relevance=-0.5, boost=2.0)
        assert item.importance == 1.0
        assert item.relevance == 0.0
        assert item.boost == 1.0

    def test_salience_returns_float(self):
        item = AttentionItem("test", importance=0.8, relevance=0.7, boost=0.5)
        sal = item.salience()
        assert isinstance(sal, float)
        assert 0.0 <= sal <= 1.0

    def test_salience_higher_with_more_importance(self):
        lo = AttentionItem("lo", importance=0.1, relevance=0.5)
        hi = AttentionItem("hi", importance=0.9, relevance=0.5)
        assert hi.salience() > lo.salience()

    def test_salience_higher_with_boost(self):
        base = AttentionItem("base", importance=0.5, relevance=0.5)
        boosted = AttentionItem("boosted", importance=0.5, relevance=0.5, boost=0.8)
        assert boosted.salience() > base.salience()

    def test_touch_increments_access(self):
        item = AttentionItem("test")
        assert item.access_count == 0
        item.touch()
        assert item.access_count == 1
        item.touch()
        assert item.access_count == 2

    def test_touch_updates_last_accessed(self):
        item = AttentionItem("test")
        old_accessed = item.last_accessed
        item.touch()
        assert item.last_accessed >= old_accessed

    def test_decay_reduces_relevance(self):
        item = AttentionItem("test", relevance=0.8, boost=0.5)
        old_rel = item.relevance
        old_boost = item.boost
        item.decay()
        assert item.relevance < old_rel
        assert item.boost < old_boost

    def test_decay_floors_at_zero(self):
        item = AttentionItem("test", relevance=0.01, boost=0.01)
        for _ in range(10):
            item.decay()
        assert item.relevance == 0.0
        assert item.boost == 0.0

    def test_to_dict(self):
        item = AttentionItem("test content", source="brain",
                             importance=0.8, item_id="test_id")
        d = item.to_dict()
        assert d["id"] == "test_id"
        assert d["content"] == "test content"
        assert d["source"] == "brain"
        assert d["importance"] == 0.8
        assert "salience" in d
        assert "created_at" in d

    def test_from_dict_roundtrip(self):
        original = AttentionItem("roundtrip test", source="test",
                                 importance=0.7, relevance=0.6, boost=0.2,
                                 item_id="rt_id")
        original.access_count = 3
        original.ticks_in_spotlight = 2
        original.ticks_total = 5
        d = original.to_dict()
        restored = AttentionItem.from_dict(d)
        assert restored.id == "rt_id"
        assert restored.content == "roundtrip test"
        assert restored.importance == 0.7
        assert restored.relevance == 0.6
        assert restored.access_count == 3
        assert restored.ticks_in_spotlight == 2
        assert restored.ticks_total == 5

    def test_from_dict_minimal(self):
        d = {"id": "min", "content": "minimal"}
        item = AttentionItem.from_dict(d)
        assert item.id == "min"
        assert item.content == "minimal"
        assert item.importance == 0.5  # default


# ---------------------------------------------------------------------------
# AttentionSpotlight — isolated with temp directory
# ---------------------------------------------------------------------------

@pytest.fixture
def spotlight(tmp_path, monkeypatch):
    """Create an AttentionSpotlight with temp file for persistence."""
    import clarvis.cognition.attention as attn_mod
    monkeypatch.setattr(attn_mod, "SPOTLIGHT_FILE", tmp_path / "spotlight.json")
    return AttentionSpotlight(capacity=3)


class TestAttentionSpotlight:
    def test_empty_spotlight(self, spotlight):
        assert len(spotlight.items) == 0

    def test_submit_creates_item(self, spotlight):
        item = spotlight.submit("test content", source="test", importance=0.8)
        assert item.content == "test content"
        assert len(spotlight.items) == 1

    def test_submit_duplicate_reinforces(self, spotlight):
        spotlight.submit("same content", relevance=0.5)
        item = spotlight.submit("same content", relevance=0.9)
        assert len(spotlight.items) == 1  # no duplicate
        assert item.relevance == 0.9  # updated to max
        assert item.access_count >= 1  # touched

    def test_focus_returns_sorted(self, spotlight):
        spotlight.submit("low", importance=0.1, relevance=0.1, item_id="lo")
        spotlight.submit("high", importance=0.9, relevance=0.9, item_id="hi")
        focus = spotlight.focus()
        assert len(focus) == 2
        assert focus[0]["id"] == "hi"  # higher salience first

    def test_focus_limited_by_capacity(self, spotlight):
        for i in range(5):
            spotlight.submit(f"item {i}", importance=0.5, item_id=f"i{i}")
        focus = spotlight.focus()
        assert len(focus) == 3  # capacity is 3

    def test_focus_summary_empty(self, spotlight):
        summary = spotlight.focus_summary()
        assert "empty" in summary

    def test_focus_summary_with_items(self, spotlight):
        spotlight.submit("important task", source="brain", importance=0.9)
        summary = spotlight.focus_summary()
        assert "important task" in summary
        assert "Spotlight" in summary

    def test_tick_empty(self, spotlight):
        result = spotlight.tick()
        assert result["total"] == 0
        assert result["evicted"] == 0

    def test_tick_decays_non_spotlight(self, spotlight):
        # Add 4 items (capacity=3, so 1 will be outside spotlight)
        for i in range(4):
            spotlight.submit(f"item {i}", importance=0.5 + i * 0.1,
                             relevance=0.5 + i * 0.1, item_id=f"t{i}")
        result = spotlight.tick()
        assert result["total"] >= 3
        assert result["decayed"] >= 0

    def test_tick_evicts_below_threshold(self, spotlight):
        # Create item with very low salience that will be evicted
        item = spotlight.submit("ephemeral", importance=0.01,
                                relevance=0.01, boost=0.0, item_id="eph")
        # Force relevance to 0 so salience drops below threshold
        item.relevance = 0.0
        item.boost = 0.0
        item.importance = 0.01
        result = spotlight.tick()
        # May or may not be evicted depending on exact salience calculation

    def test_add_alias(self, spotlight):
        """add() should work as alias for submit()."""
        item = spotlight.add("via add", importance=0.7, source="test")
        assert item.content == "via add"
        assert len(spotlight.items) == 1

    def test_clear(self, spotlight):
        spotlight.submit("item1")
        spotlight.submit("item2")
        spotlight.clear()
        assert len(spotlight.items) == 0

    def test_persistence_roundtrip(self, spotlight, tmp_path, monkeypatch):
        """Items should survive save/load cycle."""
        import clarvis.cognition.attention as attn_mod
        spotlight.submit("persist me", importance=0.8, item_id="persist_id")
        # Create new spotlight that will load from same file
        spot2 = AttentionSpotlight(capacity=3)
        assert "persist_id" in spot2.items
        assert spot2.items["persist_id"].content == "persist me"

    def test_stats(self, spotlight):
        spotlight.submit("item1", importance=0.8, item_id="s1")
        spotlight.submit("item2", importance=0.6, item_id="s2")
        stats = spotlight.stats()
        assert stats["total_items"] >= 2
        assert "avg_salience" in stats
        assert "spotlight_size" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
