#!/usr/bin/env python3
"""
Theory of Mind — User modeling and intent prediction.

Predicts what the user wants before they ask by:
  1. Tracking behavioral patterns across sessions (temporal rhythms)
  2. Mining episodic memory for recurring request types
  3. Building a preference model from stated + observed preferences
  4. Predicting next likely intent from context + history
  5. Generating proactive suggestions at session open

Core data structures:
  - user_model.json: persistent user model (preferences, rhythms, intent history)
  - Integrates with: brain (semantic recall), episodic_memory (patterns),
    meta_cognition.json (user_model field), attention (proactive items)

Usage:
    python3 theory_of_mind.py observe <event_json>   # Record a user-observable event
    python3 theory_of_mind.py predict                 # Predict next likely intent
    python3 theory_of_mind.py suggest                 # Generate proactive suggestions
    python3 theory_of_mind.py profile                 # Show current user model
    python3 theory_of_mind.py update                  # Run full model update cycle
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain, AUTONOMOUS_LEARNING

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/theory_of_mind")
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FILE = DATA_DIR / "user_model.json"
EVENTS_FILE = DATA_DIR / "events.jsonl"
PREDICTIONS_LOG = DATA_DIR / "prediction_log.jsonl"

# External data sources
EPISODES_FILE = Path("/home/agent/.openclaw/workspace/data/episodes.json")
META_COGNITION_FILE = Path("/home/agent/.openclaw/workspace/data/meta_cognition.json")
QUEUE_FILE = Path("/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md")
AUTONOMOUS_LOG = Path("/home/agent/.openclaw/workspace/memory/cron/autonomous.log")


class TheoryOfMind:
    """Models user intent, preferences, and temporal patterns to predict needs."""

    def __init__(self):
        self.model = self._load_model()

    # ==================================================================
    # PERSISTENCE
    # ==================================================================

    def _load_model(self):
        if MODEL_FILE.exists():
            try:
                with open(MODEL_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_model()

    def _default_model(self):
        return {
            "version": 1,
            "last_updated": None,
            # Preference weights: topic -> {interest: 0-1, frequency: count, last_seen: ISO}
            "preferences": {},
            # Temporal rhythms: hour_of_day -> {typical_actions: [...], frequency: int}
            "temporal_rhythms": {},
            # Intent history: recent intents with context for sequence prediction
            "intent_history": [],
            # Request patterns: action_verb -> {count, avg_complexity, contexts}
            "request_patterns": {},
            # Satisfaction signals: what leads to positive/negative outcomes
            "satisfaction_model": {
                "positive_signals": [],
                "negative_signals": [],
            },
            # Active predictions: what we think user will want next
            "active_predictions": [],
            # Stats
            "total_observations": 0,
            "prediction_accuracy": {"correct": 0, "total": 0},
        }

    def _save_model(self):
        self.model["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(MODEL_FILE, "w") as f:
            json.dump(self.model, f, indent=2)

    # ==================================================================
    # 1. OBSERVE — Record user-observable events
    # ==================================================================

    def observe(self, event_type, content, context=None):
        """Record an observable event for user modeling.

        event_type: "request", "feedback", "preference", "goal_set", "task_complete"
        content: the actual content (task text, preference statement, etc.)
        context: optional dict with extra context (time_of_day, session_key, etc.)
        """
        now = datetime.now(timezone.utc)
        event = {
            "timestamp": now.isoformat(),
            "type": event_type,
            "content": content[:300],
            "context": context or {},
            "hour": now.hour,
            "weekday": now.strftime("%A"),
        }

        # Append to events log
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")

        self.model["total_observations"] += 1

        # Update preference weights
        self._update_preferences(event)

        # Update temporal rhythms
        self._update_temporal_rhythms(event)

        # Update request patterns
        if event_type == "request":
            self._update_request_patterns(event)

        # Update intent history
        self._update_intent_history(event)

        self._save_model()
        return event

    def _update_preferences(self, event):
        """Extract preference signals from events and update preference weights."""
        content_lower = event["content"].lower()
        prefs = self.model["preferences"]

        # Domain detection
        TOPIC_KEYWORDS = {
            "memory_system": ["memory", "brain", "recall", "store", "retrieval"],
            "consciousness": ["consciousness", "phi", "awareness", "gwt", "attention"],
            "code_quality": ["test", "lint", "quality", "clean", "refactor"],
            "automation": ["cron", "autonomous", "heartbeat", "schedule"],
            "reasoning": ["reason", "chain", "think", "analyze", "logic"],
            "learning": ["learn", "meta", "predict", "calibrate", "feedback"],
            "infrastructure": ["wire", "hook", "integrate", "deploy", "config"],
            "goals": ["goal", "progress", "milestone", "target", "roadmap"],
        }

        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                if topic not in prefs:
                    prefs[topic] = {"interest": 0.5, "frequency": 0, "last_seen": None}
                prefs[topic]["frequency"] += 1
                prefs[topic]["last_seen"] = event["timestamp"]
                # Interest decays toward 0.5 baseline but spikes on activity
                prefs[topic]["interest"] = min(1.0,
                    prefs[topic]["interest"] * 0.9 + 0.15)

        # Decay topics not seen in this event
        for topic in prefs:
            if topic not in [t for t, kws in TOPIC_KEYWORDS.items()
                             if any(kw in content_lower for kw in kws)]:
                prefs[topic]["interest"] = max(0.1,
                    prefs[topic]["interest"] * 0.995)

    def _update_temporal_rhythms(self, event):
        """Track what types of events happen at what times."""
        hour_key = str(event["hour"])
        rhythms = self.model["temporal_rhythms"]

        if hour_key not in rhythms:
            rhythms[hour_key] = {"actions": defaultdict(int), "frequency": 0}
        elif not isinstance(rhythms[hour_key].get("actions"), dict):
            rhythms[hour_key]["actions"] = {}

        rhythms[hour_key]["frequency"] = rhythms[hour_key].get("frequency", 0) + 1

        # Track action type distribution at this hour
        actions = rhythms[hour_key]["actions"]
        event_type = event["type"]
        actions[event_type] = actions.get(event_type, 0) + 1

    def _update_request_patterns(self, event):
        """Track request verb patterns for intent prediction."""
        content = event["content"]
        words = content.lower().split()
        if not words:
            return

        # Extract the action verb (first word, stripped of common prefixes)
        verb = words[0].strip("[]()-")
        patterns = self.model["request_patterns"]

        if verb not in patterns:
            patterns[verb] = {"count": 0, "contexts": [], "avg_word_count": 0}

        pat = patterns[verb]
        pat["count"] += 1

        # Track context words (nouns after the verb)
        context_words = [w for w in words[1:6] if len(w) > 3]
        pat["contexts"].extend(context_words)
        pat["contexts"] = pat["contexts"][-50:]  # cap

        # Track complexity via word count
        n = pat["count"]
        pat["avg_word_count"] = ((pat["avg_word_count"] * (n - 1) + len(words)) / n)

    def _update_intent_history(self, event):
        """Maintain a sliding window of recent intents for sequence prediction."""
        intent = {
            "timestamp": event["timestamp"],
            "type": event["type"],
            "summary": event["content"][:100],
            "hour": event["hour"],
        }
        self.model["intent_history"].append(intent)
        self.model["intent_history"] = self.model["intent_history"][-100:]

    # ==================================================================
    # 2. PREDICT — Predict next likely user intent
    # ==================================================================

    def predict_intent(self):
        """Predict what the user likely wants next.

        Combines:
          - Temporal patterns (what usually happens at this hour/day)
          - Preference momentum (which topics are trending)
          - Request sequence patterns (what typically follows what)
          - Episodic context (what tasks are pending/in-progress)
          - Active queue items (what's on the roadmap)

        Returns:
          List of predictions, each with {intent, confidence, reasoning}
        """
        now = datetime.now(timezone.utc)
        predictions = []

        # === Signal 1: Temporal patterns ===
        temporal_preds = self._predict_from_temporal(now)
        predictions.extend(temporal_preds)

        # === Signal 2: Preference momentum ===
        pref_preds = self._predict_from_preferences()
        predictions.extend(pref_preds)

        # === Signal 3: Pending work from queue ===
        queue_preds = self._predict_from_queue()
        predictions.extend(queue_preds)

        # === Signal 4: Episodic failure recovery ===
        recovery_preds = self._predict_from_failures()
        predictions.extend(recovery_preds)

        # === Signal 5: Sequence prediction (what follows last intent) ===
        seq_preds = self._predict_from_sequence()
        predictions.extend(seq_preds)

        # Merge duplicate intents by boosting confidence
        merged = self._merge_predictions(predictions)

        # Sort by confidence
        merged.sort(key=lambda p: p["confidence"], reverse=True)

        # Save top predictions
        self.model["active_predictions"] = merged[:5]
        self._save_model()

        # Log predictions for accuracy tracking
        for pred in merged[:3]:
            log_entry = {
                "timestamp": now.isoformat(),
                "intent": pred["intent"],
                "confidence": pred["confidence"],
                "reasoning": pred["reasoning"],
                "resolved": None,  # filled in later by observe()
            }
            with open(PREDICTIONS_LOG, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

        return merged[:5]

    def _predict_from_temporal(self, now):
        """Predict based on what usually happens at this time."""
        preds = []
        hour_key = str(now.hour)
        rhythms = self.model.get("temporal_rhythms", {})
        hour_data = rhythms.get(hour_key)

        if not hour_data or hour_data.get("frequency", 0) < 2:
            return preds

        actions = hour_data.get("actions", {})
        total = sum(actions.values()) if isinstance(actions, dict) else 0
        if total < 2:
            return preds

        # Find dominant action type at this hour
        for action_type, count in sorted(actions.items(), key=lambda x: x[1], reverse=True)[:2]:
            ratio = count / total
            if ratio > 0.3:
                preds.append({
                    "intent": f"User typically does '{action_type}' at hour {now.hour}",
                    "confidence": min(0.7, ratio * 0.8),
                    "reasoning": f"temporal_rhythm: {count}/{total} events at hour {now.hour} are '{action_type}'",
                    "source": "temporal",
                })

        return preds

    def _predict_from_preferences(self):
        """Predict based on trending preference topics."""
        preds = []
        prefs = self.model.get("preferences", {})

        if not prefs:
            return preds

        # Sort by interest * recency
        now = datetime.now(timezone.utc)
        scored_topics = []
        for topic, data in prefs.items():
            interest = data.get("interest", 0.5)
            last_seen = data.get("last_seen")
            frequency = data.get("frequency", 0)

            # Recency boost: more recent = higher score
            recency = 0.5
            if last_seen:
                try:
                    last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    hours_ago = (now - last_dt).total_seconds() / 3600
                    recency = max(0.1, 1.0 - (hours_ago / 168))  # decay over a week
                except (ValueError, TypeError):
                    pass

            score = interest * 0.5 + recency * 0.3 + min(1.0, frequency / 20) * 0.2
            scored_topics.append((topic, score, interest, frequency))

        scored_topics.sort(key=lambda x: x[1], reverse=True)

        for topic, score, interest, freq in scored_topics[:2]:
            if score > 0.4:
                preds.append({
                    "intent": f"Continue work on {topic.replace('_', ' ')}",
                    "confidence": min(0.6, score * 0.7),
                    "reasoning": f"preference_momentum: interest={interest:.2f}, freq={freq}, score={score:.2f}",
                    "source": "preference",
                })

        return preds

    def _predict_from_queue(self):
        """Predict based on pending items in evolution QUEUE.md."""
        preds = []

        if not QUEUE_FILE.exists():
            return preds

        try:
            content = QUEUE_FILE.read_text()
            # Find unchecked items
            pending = []
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- [ ]"):
                    task_text = stripped[5:].strip()
                    pending.append(task_text)

            if pending:
                # Top pending task is likely next focus
                preds.append({
                    "intent": f"Work on: {pending[0][:100]}",
                    "confidence": 0.5,
                    "reasoning": f"queue: top pending item from QUEUE.md ({len(pending)} pending total)",
                    "source": "queue",
                })

                # If multiple pending, predict the user cares about throughput
                if len(pending) >= 3:
                    preds.append({
                        "intent": "User wants to clear backlog (multiple pending tasks)",
                        "confidence": 0.3,
                        "reasoning": f"queue: {len(pending)} pending tasks suggest backlog pressure",
                        "source": "queue",
                    })
        except OSError:
            pass

        return preds

    def _predict_from_failures(self):
        """Predict user wants to address recent failures."""
        preds = []

        if not EPISODES_FILE.exists():
            return preds

        try:
            with open(EPISODES_FILE) as f:
                episodes = json.load(f)
        except (json.JSONDecodeError, OSError):
            return preds

        # Recent failures (last 24h)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        recent_failures = []

        for ep in reversed(episodes):
            try:
                ts = datetime.fromisoformat(ep["timestamp"].replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    break
                if ep.get("outcome") in ("failure", "soft_failure"):
                    recent_failures.append(ep)
            except (ValueError, TypeError, KeyError):
                continue

        if recent_failures:
            # Group by error type
            error_tasks = [f["task"][:80] for f in recent_failures[:3]]
            preds.append({
                "intent": f"Address recent failure: {error_tasks[0]}",
                "confidence": min(0.6, 0.3 + len(recent_failures) * 0.1),
                "reasoning": f"failure_recovery: {len(recent_failures)} failures in last 24h",
                "source": "failure_recovery",
            })

        return preds

    def _predict_from_sequence(self):
        """Predict based on what typically follows the last observed intent."""
        preds = []
        history = self.model.get("intent_history", [])

        if len(history) < 3:
            return preds

        # Build bigram transition probabilities
        transitions = defaultdict(lambda: defaultdict(int))
        for i in range(len(history) - 1):
            curr_type = history[i]["type"]
            next_type = history[i + 1]["type"]
            transitions[curr_type][next_type] += 1

        # Predict from last intent
        last_type = history[-1]["type"]
        if last_type in transitions:
            next_counts = transitions[last_type]
            total = sum(next_counts.values())
            for next_type, count in sorted(next_counts.items(),
                                            key=lambda x: x[1], reverse=True)[:1]:
                prob = count / total
                if prob > 0.3:
                    preds.append({
                        "intent": f"After '{last_type}', user typically does '{next_type}'",
                        "confidence": min(0.5, prob * 0.6),
                        "reasoning": f"sequence: P('{next_type}'|'{last_type}') = {prob:.0%} ({count}/{total})",
                        "source": "sequence",
                    })

        return preds

    def _merge_predictions(self, predictions):
        """Merge predictions with overlapping intents by boosting confidence."""
        if not predictions:
            return []

        # Group by source for dedup within source
        seen_sources = set()
        merged = []
        for pred in predictions:
            key = (pred["source"], pred["intent"][:50])
            if key in seen_sources:
                continue
            seen_sources.add(key)
            merged.append(pred)

        return merged

    # ==================================================================
    # 3. SUGGEST — Generate proactive suggestions
    # ==================================================================

    def generate_suggestions(self):
        """Generate proactive suggestions to present at session open.

        Combines predictions with context-aware heuristics.

        Returns:
            List of suggestion dicts {suggestion, priority, context}
        """
        suggestions = []
        now = datetime.now(timezone.utc)

        # Get fresh predictions
        predictions = self.predict_intent()

        # Convert high-confidence predictions to suggestions
        for pred in predictions:
            if pred["confidence"] >= 0.4:
                suggestions.append({
                    "suggestion": pred["intent"],
                    "priority": "high" if pred["confidence"] >= 0.6 else "medium",
                    "context": pred["reasoning"],
                    "source": pred["source"],
                })

        # Add time-based suggestions
        hour = now.hour

        # Morning: suggest review and planning
        if 6 <= hour <= 9:
            suggestions.append({
                "suggestion": "Review yesterday's progress and plan today's priorities",
                "priority": "medium",
                "context": "morning_routine: typical planning window",
                "source": "temporal_heuristic",
            })

        # Evening: suggest reflection
        if 20 <= hour <= 23:
            suggestions.append({
                "suggestion": "Run daily reflection and capability assessment",
                "priority": "medium",
                "context": "evening_routine: consolidation window",
                "source": "temporal_heuristic",
            })

        # Add preference-based suggestions for high-interest topics not recently worked on
        prefs = self.model.get("preferences", {})
        for topic, data in prefs.items():
            if data.get("interest", 0) > 0.7 and data.get("frequency", 0) >= 3:
                last_seen = data.get("last_seen")
                if last_seen:
                    try:
                        last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        hours_since = (now - last_dt).total_seconds() / 3600
                        if hours_since > 48:
                            suggestions.append({
                                "suggestion": f"Revisit {topic.replace('_', ' ')} (high interest, {hours_since:.0f}h since last activity)",
                                "priority": "low",
                                "context": f"preference_nudge: interest={data['interest']:.2f}, dormant {hours_since:.0f}h",
                                "source": "preference_nudge",
                            })
                    except (ValueError, TypeError):
                        pass

        # Deduplicate
        seen = set()
        deduped = []
        for s in suggestions:
            key = s["suggestion"][:60]
            if key not in seen:
                seen.add(key)
                deduped.append(s)

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        deduped.sort(key=lambda s: priority_order.get(s["priority"], 3))

        return deduped[:7]

    # ==================================================================
    # 4. FULL UPDATE — Mine all data sources for model update
    # ==================================================================

    def full_update(self):
        """Run a comprehensive model update from all data sources.

        Mines episodes, autonomous logs, and brain memories to enrich the
        user model with observed patterns. Call this during daily reflection.

        Returns:
            Summary dict with update statistics.
        """
        stats = {"events_mined": 0, "preferences_updated": 0, "patterns_found": 0}

        # --- Mine episodes for behavioral patterns ---
        if EPISODES_FILE.exists():
            try:
                with open(EPISODES_FILE) as f:
                    episodes = json.load(f)

                for ep in episodes:
                    task = ep.get("task", "")
                    outcome = ep.get("outcome", "")

                    # Each episode is an implicit observation
                    self.observe(
                        event_type="task_complete" if outcome == "success" else "feedback",
                        content=task,
                        context={"outcome": outcome, "source": "episodic_mine"}
                    )
                    stats["events_mined"] += 1

                    # Track satisfaction signals
                    if outcome == "success":
                        self.model["satisfaction_model"]["positive_signals"].append(
                            task[:100])
                        self.model["satisfaction_model"]["positive_signals"] = \
                            self.model["satisfaction_model"]["positive_signals"][-50:]
                    elif outcome in ("failure", "soft_failure"):
                        self.model["satisfaction_model"]["negative_signals"].append(
                            task[:100])
                        self.model["satisfaction_model"]["negative_signals"] = \
                            self.model["satisfaction_model"]["negative_signals"][-50:]

            except (json.JSONDecodeError, OSError):
                pass

        # --- Mine autonomous log for execution patterns ---
        if AUTONOMOUS_LOG.exists():
            try:
                with open(AUTONOMOUS_LOG) as f:
                    lines = f.readlines()
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                today_lines = [l for l in lines if today in l]

                for line in today_lines:
                    if "COMPLETED" in line or "FAILED" in line:
                        self.observe(
                            event_type="task_complete",
                            content=line.strip()[:200],
                            context={"source": "autonomous_log"}
                        )
                        stats["events_mined"] += 1
            except OSError:
                pass

        # --- Mine brain preferences collection ---
        try:
            pref_memories = brain.recall(
                "user preferences goals priorities",
                n=10,
                collections=["clarvis-preferences"]
            )
            for mem in pref_memories:
                doc = mem.get("document", "")
                if doc:
                    self.observe(
                        event_type="preference",
                        content=doc[:200],
                        context={"source": "brain_preferences"}
                    )
                    stats["preferences_updated"] += 1
        except Exception:
            pass

        # --- Compute pattern statistics ---
        stats["patterns_found"] = len(self.model.get("request_patterns", {}))
        stats["total_observations"] = self.model["total_observations"]
        stats["preference_topics"] = len(self.model.get("preferences", {}))
        stats["temporal_hours_tracked"] = len(self.model.get("temporal_rhythms", {}))

        # --- Update meta-cognition user_model field ---
        try:
            if META_COGNITION_FILE.exists():
                with open(META_COGNITION_FILE) as f:
                    meta = json.load(f)

                # Generate a concise user state summary
                top_prefs = sorted(
                    self.model.get("preferences", {}).items(),
                    key=lambda x: x[1].get("interest", 0),
                    reverse=True
                )[:3]
                pref_summary = ", ".join(f"{t}" for t, _ in top_prefs) if top_prefs else "unknown"

                predictions = self.model.get("active_predictions", [])
                top_intent = predictions[0]["intent"][:100] if predictions else "no prediction"

                meta["user_model"] = {
                    "inferred_state": f"focused on: {pref_summary}",
                    "intent": top_intent,
                    "preference_topics": len(self.model.get("preferences", {})),
                    "model_confidence": min(1.0, self.model["total_observations"] / 100),
                    "last_update": datetime.now(timezone.utc).isoformat(),
                }

                with open(META_COGNITION_FILE, "w") as f:
                    json.dump(meta, f, indent=2)
        except Exception:
            pass

        # --- Store summary in brain ---
        try:
            brain.store(
                f"Theory of mind update: {stats['events_mined']} events mined, "
                f"{stats['preference_topics']} preference topics, "
                f"{stats['patterns_found']} request patterns. "
                f"Top interests: {', '.join(t for t, _ in sorted(self.model.get('preferences', {}).items(), key=lambda x: x[1].get('interest', 0), reverse=True)[:3])}",
                collection=AUTONOMOUS_LEARNING,
                importance=0.6,
                tags=["theory-of-mind", "user-model", "update"],
                source="theory_of_mind",
            )
        except Exception:
            pass

        self._save_model()
        return stats

    # ==================================================================
    # 5. PROFILE — Show current user model
    # ==================================================================

    def show_profile(self):
        """Print a human-readable summary of the current user model."""
        m = self.model
        print("=" * 60)
        print("THEORY OF MIND — User Model")
        print("=" * 60)
        print(f"Last updated: {m.get('last_updated', 'never')}")
        print(f"Total observations: {m.get('total_observations', 0)}")
        acc = m.get("prediction_accuracy", {})
        if acc.get("total", 0) > 0:
            print(f"Prediction accuracy: {acc['correct']}/{acc['total']} "
                  f"({acc['correct']/acc['total']:.0%})")

        # Preferences
        prefs = m.get("preferences", {})
        if prefs:
            print(f"\n--- Preference Model ({len(prefs)} topics) ---")
            sorted_prefs = sorted(prefs.items(),
                                   key=lambda x: x[1].get("interest", 0), reverse=True)
            for topic, data in sorted_prefs[:10]:
                bar = "#" * int(data.get("interest", 0) * 10) + "." * (10 - int(data.get("interest", 0) * 10))
                print(f"  {topic:25s}  [{bar}] {data.get('interest', 0):.2f}  "
                      f"(freq={data.get('frequency', 0)})")

        # Temporal rhythms
        rhythms = m.get("temporal_rhythms", {})
        if rhythms:
            print(f"\n--- Temporal Rhythms ({len(rhythms)} hours tracked) ---")
            for hour in sorted(rhythms.keys(), key=lambda x: int(x)):
                data = rhythms[hour]
                freq = data.get("frequency", 0)
                actions = data.get("actions", {})
                top_action = max(actions.items(), key=lambda x: x[1])[0] if actions else "?"
                print(f"  Hour {hour:>2s}: {freq:3d} events  (dominant: {top_action})")

        # Request patterns
        patterns = m.get("request_patterns", {})
        if patterns:
            print(f"\n--- Request Patterns ({len(patterns)} verbs) ---")
            sorted_pats = sorted(patterns.items(),
                                  key=lambda x: x[1].get("count", 0), reverse=True)
            for verb, data in sorted_pats[:10]:
                ctx = data.get("contexts", [])
                top_ctx = ", ".join(set(ctx[-5:])) if ctx else ""
                print(f"  {verb:15s}  {data.get('count', 0):3d}x  "
                      f"avg_words={data.get('avg_word_count', 0):.1f}  ctx: {top_ctx[:40]}")

        # Active predictions
        preds = m.get("active_predictions", [])
        if preds:
            print(f"\n--- Active Predictions ({len(preds)}) ---")
            for p in preds:
                conf_bar = "#" * int(p["confidence"] * 10)
                print(f"  [{conf_bar:10s}] {p['confidence']:.0%}  {p['intent'][:60]}")
                print(f"    reason: {p['reasoning'][:60]}")

        # Satisfaction model
        sat = m.get("satisfaction_model", {})
        pos = sat.get("positive_signals", [])
        neg = sat.get("negative_signals", [])
        if pos or neg:
            print("\n--- Satisfaction Signals ---")
            print(f"  Positive: {len(pos)} signals")
            print(f"  Negative: {len(neg)} signals")

    # ==================================================================
    # 6. PROACTIVE ATTENTION — Push suggestions to spotlight
    # ==================================================================

    def push_to_spotlight(self, suggestions=None):
        """Push top suggestions to the attention spotlight.

        Call this at session_open to prime Clarvis with proactive context.
        Returns number of items pushed.
        """
        if suggestions is None:
            suggestions = self.generate_suggestions()

        pushed = 0
        try:
            from attention import attention
            for s in suggestions[:3]:  # Push top 3
                if s["priority"] in ("high", "medium"):
                    attention.submit(
                        f"[ToM] {s['suggestion'][:120]}",
                        source="theory_of_mind",
                        importance=0.7 if s["priority"] == "high" else 0.5,
                        relevance=0.6,
                        boost=0.1,
                    )
                    pushed += 1
        except Exception:
            pass  # Attention unavailable — degrade gracefully

        return pushed

    # ==================================================================
    # 7. SCORING — For integration with self_model capability assessor
    # ==================================================================

    def get_model_score(self):
        """Score the user model's maturity for capability assessment.

        Scoring (continuous 0-1):
          - Observation volume: min(0.2, total_observations / 200)
          - Preference coverage: min(0.2, topics / 8)
          - Temporal coverage: min(0.2, hours_tracked / 12)
          - Prediction accuracy: accuracy * 0.2 (if any predictions resolved)
          - Active predictions exist: +0.1 if any, +0.2 if confidence > 0.5

        Returns:
          (score, evidence_list)
        """
        score = 0.0
        evidence = []

        obs = self.model.get("total_observations", 0)
        obs_score = min(0.2, obs / 200 * 0.2)
        score += obs_score
        evidence.append(f"observations={obs} (+{obs_score:.2f})")

        topics = len(self.model.get("preferences", {}))
        topic_score = min(0.2, topics / 8 * 0.2)
        score += topic_score
        evidence.append(f"preference_topics={topics} (+{topic_score:.2f})")

        hours = len(self.model.get("temporal_rhythms", {}))
        time_score = min(0.2, hours / 12 * 0.2)
        score += time_score
        evidence.append(f"temporal_hours={hours} (+{time_score:.2f})")

        acc = self.model.get("prediction_accuracy", {})
        if acc.get("total", 0) > 0:
            accuracy = acc["correct"] / acc["total"]
            acc_score = accuracy * 0.2
            score += acc_score
            evidence.append(f"prediction_accuracy={accuracy:.0%} (+{acc_score:.2f})")

        preds = self.model.get("active_predictions", [])
        if preds:
            max_conf = max(p.get("confidence", 0) for p in preds)
            if max_conf > 0.5:
                score += 0.2
                evidence.append(f"active predictions with confidence {max_conf:.2f} (+0.20)")
            else:
                score += 0.1
                evidence.append(f"active predictions (low confidence {max_conf:.2f}) (+0.10)")

        return round(min(1.0, score), 2), evidence


# Singleton (lazy — no I/O until first access)
_tom = None

def get_tom():
    global _tom
    if _tom is None:
        _tom = TheoryOfMind()
    return _tom

class _LazyToM:
    def __getattr__(self, name):
        real = get_tom()
        global tom
        tom = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazyToM (not yet initialized)>"

tom = _LazyToM()


# ==================================================================
# CLI
# ==================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: theory_of_mind.py <observe|predict|suggest|profile|update|score>")
        print()
        print("Commands:")
        print("  observe <type> <content>  Record a user event (type: request|feedback|preference)")
        print("  predict                   Predict next likely user intent")
        print("  suggest                   Generate proactive suggestions")
        print("  profile                   Show current user model")
        print("  update                    Full model update from all data sources")
        print("  score                     Show model maturity score")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "observe":
        if len(sys.argv) < 4:
            print("Usage: observe <event_type> <content>")
            sys.exit(1)
        event_type = sys.argv[2]
        content = " ".join(sys.argv[3:])
        event = tom.observe(event_type, content)
        print(f"Observed: {event['type']} -> {event['content'][:80]}")

    elif cmd == "predict":
        predictions = tom.predict_intent()
        if not predictions:
            print("No predictions (insufficient data).")
        else:
            print(f"Intent Predictions ({len(predictions)}):")
            for p in predictions:
                print(f"  [{p['confidence']:.0%}] {p['intent'][:70]}")
                print(f"       {p['reasoning'][:70]}")

    elif cmd == "suggest":
        suggestions = tom.generate_suggestions()
        if not suggestions:
            print("No suggestions available.")
        else:
            print(f"Proactive Suggestions ({len(suggestions)}):")
            for s in suggestions:
                icon = {"high": "!!!", "medium": " ! ", "low": "   "}.get(s["priority"], "   ")
                print(f"  [{icon}] {s['suggestion'][:70]}")
                print(f"       context: {s['context'][:60]}")

    elif cmd == "profile":
        tom.show_profile()

    elif cmd == "update":
        print("Running full theory of mind update...")
        stats = tom.full_update()
        print("\n--- Update Complete ---")
        print(f"  Events mined: {stats['events_mined']}")
        print(f"  Preferences updated: {stats['preferences_updated']}")
        print(f"  Request patterns: {stats['patterns_found']}")
        print(f"  Total observations: {stats['total_observations']}")
        print(f"  Preference topics: {stats['preference_topics']}")
        print(f"  Temporal hours tracked: {stats['temporal_hours_tracked']}")

    elif cmd == "score":
        score, evidence = tom.get_model_score()
        print(f"Theory of Mind Model Score: {score:.2f}")
        for e in evidence:
            print(f"  - {e}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
