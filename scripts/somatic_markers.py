#!/usr/bin/env python3
"""
Somatic Markers — Emotional valence on memories for decision biasing.

Inspired by Damasio's somatic marker hypothesis: past emotional experiences
create "body signals" (markers) that bias future decisions before conscious
reasoning occurs. When Clarvis encounters a task similar to a past episode,
the somatic marker provides an approach/avoid signal.

Extends the existing valence system in episodic_memory.py:
  - Episodes already have scalar valence (0-1, memorability weight)
  - Somatic markers ADD dimensional emotions: {approach, avoid, caution, excitement}
  - Each marker links an emotion to a context pattern
  - On task selection, markers for similar contexts bias the decision

Integration points:
  - episodic_memory.py: encode() calls tag_episode() to add somatic markers
  - task_selector.py: score_tasks() calls get_bias() for emotional decision biasing
  - cron_autonomous.sh: no changes needed (markers fire via episodic + selector)

Usage:
    from somatic_markers import somatic

    # After a task completes, tag the episode
    somatic.tag_episode(episode)

    # Before choosing a task, get emotional bias
    bias = somatic.get_bias("Build new metric system")
    # -> {"signal": "caution", "strength": 0.6, "reason": "similar tasks timed out"}

    # CLI
    python3 somatic_markers.py tag <episode_json>
    python3 somatic_markers.py bias "task description"
    python3 somatic_markers.py stats
    python3 somatic_markers.py markers
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain import brain

MARKERS_FILE = Path("/home/agent/.openclaw/workspace/data/somatic_markers.json")

# Emotion dimensions for somatic markers
# Each maps to a decision signal: approach (+) or avoid (-)
EMOTIONS = {
    "satisfaction":  {"signal": "approach",   "weight": +0.15},
    "excitement":    {"signal": "approach",   "weight": +0.10},
    "mastery":       {"signal": "approach",   "weight": +0.12},
    "frustration":   {"signal": "avoid",      "weight": -0.12},
    "anxiety":       {"signal": "caution",    "weight": -0.08},
    "pain":          {"signal": "avoid",      "weight": -0.15},
    "surprise":      {"signal": "caution",    "weight": -0.05},
    "boredom":       {"signal": "avoid",      "weight": -0.03},
}


class SomaticMarkerSystem:
    """Manages emotional markers on memories for decision biasing."""

    def __init__(self):
        self.markers = self._load()

    def _load(self):
        if MARKERS_FILE.exists():
            with open(MARKERS_FILE) as f:
                return json.load(f)
        return []

    def _save(self):
        MARKERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MARKERS_FILE, 'w') as f:
            json.dump(self.markers[-1000:], f, indent=2)  # cap at 1000

    def tag_episode(self, episode):
        """Analyze an episode and create somatic markers from it.

        Args:
            episode: dict with keys: task, outcome, valence, duration_s, error, salience

        Returns:
            List of marker dicts created for this episode.
        """
        task = episode.get("task", "")
        outcome = episode.get("outcome", "unknown")
        valence = episode.get("valence", 0.5)
        duration_s = episode.get("duration_s", 0)
        error = episode.get("error", "")
        salience = episode.get("salience", 0.5)
        ep_id = episode.get("id", "")

        # Extract context keywords (the "situation" the marker attaches to)
        context_keywords = self._extract_context(task)

        # Compute emotional profile from episode features
        emotions = self._compute_emotions(outcome, valence, duration_s, error, salience)

        # Create markers — one per significant emotion
        new_markers = []
        now = datetime.now(timezone.utc)

        for emotion, strength in emotions.items():
            if abs(strength) < 0.1:
                continue  # Only tag significant emotions

            marker = {
                "id": f"sm_{ep_id}_{emotion}",
                "episode_id": ep_id,
                "timestamp": now.isoformat(),
                "context_keywords": sorted(context_keywords),
                "task_snippet": task[:120],
                "emotion": emotion,
                "strength": round(strength, 4),
                "signal": EMOTIONS[emotion]["signal"],
                "decay_rate": 0.02,  # 2% per day — emotions fade
                "access_count": 0,
            }
            new_markers.append(marker)

        if new_markers:
            self.markers.extend(new_markers)
            self._save()

        return new_markers

    def get_bias(self, task_text, n_markers=10):
        """Get emotional bias for a proposed task.

        Finds somatic markers with similar context, computes aggregate
        approach/avoid signal. This is called BEFORE conscious task analysis.

        Args:
            task_text: The proposed task description
            n_markers: Max markers to consider

        Returns:
            dict with:
                - bias_score: float (-1.0 avoid ... +1.0 approach)
                - signal: "approach" | "avoid" | "caution" | "neutral"
                - strength: 0.0 - 1.0
                - reason: human-readable explanation
                - markers_matched: number of relevant markers found
        """
        if not self.markers:
            return {
                "bias_score": 0.0,
                "signal": "neutral",
                "strength": 0.0,
                "reason": "no somatic markers yet",
                "markers_matched": 0,
            }

        task_keywords = self._extract_context(task_text)
        if not task_keywords:
            return {
                "bias_score": 0.0,
                "signal": "neutral",
                "strength": 0.0,
                "reason": "no context keywords extracted",
                "markers_matched": 0,
            }

        # Find markers with overlapping context
        scored_markers = []
        for marker in self.markers:
            mk_kws = set(marker.get("context_keywords", []))
            overlap = task_keywords & mk_kws
            if not overlap:
                continue

            # Relevance = Jaccard similarity of context keywords
            union = task_keywords | mk_kws
            relevance = len(overlap) / len(union) if union else 0

            # Apply temporal decay
            age_days = self._age_days(marker.get("timestamp", ""))
            decay = math.exp(-marker.get("decay_rate", 0.02) * age_days)

            effective_strength = marker["strength"] * relevance * decay
            scored_markers.append({
                "marker": marker,
                "relevance": relevance,
                "decay": decay,
                "effective_strength": effective_strength,
                "overlap_keywords": list(overlap),
            })

        if not scored_markers:
            return {
                "bias_score": 0.0,
                "signal": "neutral",
                "strength": 0.0,
                "reason": "no markers match this context",
                "markers_matched": 0,
            }

        # Sort by absolute effective strength (most impactful first)
        scored_markers.sort(key=lambda x: abs(x["effective_strength"]), reverse=True)
        top = scored_markers[:n_markers]

        # Aggregate emotional signal
        # Weighted sum of marker decision weights
        total_bias = 0.0
        emotion_counts = {}
        for sm in top:
            emo = sm["marker"]["emotion"]
            weight = EMOTIONS[emo]["weight"]
            total_bias += weight * sm["effective_strength"] / abs(sm["marker"]["strength"]) if sm["marker"]["strength"] != 0 else 0
            emotion_counts[emo] = emotion_counts.get(emo, 0) + 1

            # Record access (markers strengthen with use, like memories)
            sm["marker"]["access_count"] = sm["marker"].get("access_count", 0) + 1

        self._save()

        # Clamp bias to [-1, 1]
        bias_score = max(-1.0, min(1.0, total_bias))
        strength = min(1.0, abs(bias_score))

        # Determine signal
        if bias_score > 0.05:
            signal = "approach"
        elif bias_score < -0.1:
            signal = "avoid" if bias_score < -0.2 else "caution"
        else:
            signal = "neutral"

        # Build reason from dominant emotions
        dominant = sorted(emotion_counts.items(), key=lambda x: -x[1])[:3]
        dom_str = ", ".join(f"{e}({c})" for e, c in dominant)
        top_kws = set()
        for sm in top[:3]:
            top_kws.update(sm["overlap_keywords"][:3])
        kw_str = ", ".join(list(top_kws)[:5])

        reason = f"markers: {dom_str}; context: {kw_str}"

        return {
            "bias_score": round(bias_score, 4),
            "signal": signal,
            "strength": round(strength, 4),
            "reason": reason,
            "markers_matched": len(top),
        }

    def get_stats(self):
        """Get summary statistics of the somatic marker system."""
        if not self.markers:
            return {"total_markers": 0}

        emotion_dist = {}
        signal_dist = {}
        avg_strength = 0
        for m in self.markers:
            emo = m.get("emotion", "unknown")
            sig = m.get("signal", "unknown")
            emotion_dist[emo] = emotion_dist.get(emo, 0) + 1
            signal_dist[sig] = signal_dist.get(sig, 0) + 1
            avg_strength += abs(m.get("strength", 0))

        avg_strength /= len(self.markers)

        return {
            "total_markers": len(self.markers),
            "emotion_distribution": emotion_dist,
            "signal_distribution": signal_dist,
            "avg_strength": round(avg_strength, 3),
            "oldest": self.markers[0].get("timestamp", "")[:10] if self.markers else None,
            "newest": self.markers[-1].get("timestamp", "")[:10] if self.markers else None,
        }

    def _compute_emotions(self, outcome, valence, duration_s, error, salience):
        """Map episode features to emotion dimensions.

        Returns dict of emotion -> strength (0.0 - 1.0).
        """
        emotions = {}

        if outcome == "success":
            # Success generates satisfaction proportional to difficulty
            difficulty_bonus = min(0.3, duration_s / 600.0 * 0.3) if duration_s > 0 else 0
            emotions["satisfaction"] = 0.4 + difficulty_bonus + float(salience) * 0.2

            # Quick successes on high-salience tasks = mastery
            if duration_s < 120 and float(salience) > 0.6:
                emotions["mastery"] = 0.3 + float(salience) * 0.3

            # Novel or high-salience successes = excitement
            if float(salience) > 0.7:
                emotions["excitement"] = 0.2 + float(salience) * 0.2

        elif outcome == "failure":
            # Failures generate pain and frustration
            emotions["pain"] = 0.4 + valence * 0.3
            emotions["frustration"] = 0.3 + valence * 0.2

            # Import errors specifically cause anxiety (brittle infrastructure)
            if error and ("import" in error.lower() or "module" in error.lower()):
                emotions["anxiety"] = 0.5

        elif outcome == "timeout":
            # Timeouts = frustration + anxiety about complexity
            emotions["frustration"] = 0.5
            emotions["anxiety"] = 0.3

        elif outcome == "soft_failure":
            # Soft failures = mild frustration + caution signal
            emotions["frustration"] = 0.2 + valence * 0.2
            emotions["anxiety"] = 0.15
            emotions["surprise"] = 0.2  # unexpected partial failure

        # Duration-based emotions (independent of outcome)
        if duration_s > 300:
            # Long tasks add frustration regardless of outcome
            emotions["frustration"] = max(emotions.get("frustration", 0), 0.2)
        if duration_s > 0 and duration_s < 30:
            # Very fast tasks that succeed feel like mastery
            if outcome == "success":
                emotions["mastery"] = max(emotions.get("mastery", 0), 0.4)

        # Clamp all to [0, 1]
        return {k: min(1.0, max(0.0, v)) for k, v in emotions.items()}

    def _extract_context(self, text):
        """Extract context keywords from task text for marker matching.

        Returns set of normalized keywords (lowercase, len > 3).
        """
        # Remove common stop words and queue formatting
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "into",
            "have", "been", "will", "should", "would", "could", "about",
            "each", "when", "then", "than", "also", "just", "more", "most",
            "some", "such", "only", "very", "every", "after", "before",
            "create", "build", "make", "ensure", "check", "verify", "update",
            "scripts", "cron", "wire", "already", "existing", "using", "based",
            "goal", "task", "implement", "run", "add",
        }

        words = set()
        for word in text.lower().split():
            # Strip punctuation
            clean = word.strip("[](){}.,;:!?\"'-/\\#*_~`@")
            if len(clean) > 3 and clean not in stop_words and not clean.isdigit():
                words.add(clean)

        return words

    def _age_days(self, timestamp_str):
        """Calculate age in days from an ISO timestamp string."""
        if not timestamp_str:
            return 30  # default to 30 days if unknown
        try:
            ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return max(0, (now - ts).total_seconds() / 86400)
        except (ValueError, TypeError):
            return 30

    def backfill_from_episodes(self, episodes_file=None):
        """Create somatic markers from all existing episodes.

        Run once to bootstrap the marker system from historical episodes.

        Returns count of new markers created.
        """
        if episodes_file is None:
            episodes_file = Path("/home/agent/.openclaw/workspace/data/episodes.json")

        if not episodes_file.exists():
            return 0

        with open(episodes_file) as f:
            episodes = json.load(f)

        existing_ep_ids = {m.get("episode_id") for m in self.markers}
        created = 0

        for ep in episodes:
            if ep.get("id") in existing_ep_ids:
                continue
            new = self.tag_episode(ep)
            created += len(new)

        return created


# Singleton
somatic = SomaticMarkerSystem()

# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: somatic_markers.py <tag|bias|stats|markers|backfill>")
        print("  tag <episode_json>   — create markers from an episode")
        print("  bias <task_text>     — get emotional bias for a task")
        print("  stats                — show marker statistics")
        print("  markers              — list all markers")
        print("  backfill             — create markers from all existing episodes")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "tag":
        if len(sys.argv) < 3:
            print("Usage: tag <episode_json>")
            sys.exit(1)
        ep = json.loads(sys.argv[2])
        new_markers = somatic.tag_episode(ep)
        print(f"Created {len(new_markers)} somatic markers:")
        for m in new_markers:
            print(f"  {m['signal']:8s} {m['emotion']:15s} strength={m['strength']:.2f}  ctx={m['context_keywords'][:5]}")

    elif cmd == "bias":
        if len(sys.argv) < 3:
            print("Usage: bias <task_text>")
            sys.exit(1)
        task = " ".join(sys.argv[2:])
        result = somatic.get_bias(task)
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        stats = somatic.get_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "markers":
        for m in somatic.markers:
            age = somatic._age_days(m.get("timestamp", ""))
            print(f"  [{m['signal']:8s}] {m['emotion']:15s} str={m['strength']:.2f}  "
                  f"age={age:.1f}d  task={m['task_snippet'][:60]}")

    elif cmd == "backfill":
        count = somatic.backfill_from_episodes()
        print(f"Backfilled {count} somatic markers from existing episodes")
        stats = somatic.get_stats()
        print(json.dumps(stats, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
