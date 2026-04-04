#!/usr/bin/env python3
"""
Directive Engine — Smart, scoped instruction enforcement for Clarvis.

Companion to obligation_tracker.py. Adds the intelligence layer:
- Classification: standing / window / one_shot / session
- Emotional dampening: detects hyperbolic/angry wording, lowers literalness
- Expiry & sunset: auto-retires directives that outlive their scope
- Discretion: graduated enforcement (enforce / soften / note / skip)
- Interference budgets: limits how much enforcement can disrupt work

Design constraints (from operator):
1. Temporary/window-bound instructions must not become permanent
2. Enforcement must not dominate judgment or degrade quality
3. Emotional/strict wording must not crystalize unsafe rigid rules
4. Integration must be seamless, not bureaucratic
5. Prevents speech-without-state-transition without heavy friction

Architecture:
    directive_engine.py (classification, scoping, discretion)
         └── obligation_tracker.py (durable enforcement backend)

Usage:
    from directive_engine import DirectiveEngine
    engine = DirectiveEngine()

    # Classify and record a new directive
    directive = engine.ingest("Always commit work before ending a session",
                              source="user", raw_context="calm direct instruction")

    # Check what to enforce for current task
    active = engine.active_directives(task_context="working on brain optimization")

    # Should a specific directive be enforced right now?
    decision = engine.should_enforce(directive_id, task_context="...")
    # Returns: {action: "enforce"|"soften"|"note"|"skip", reason: "..."}

CLI:
    python3 directive_engine.py ingest "instruction text" [--source user|system]
    python3 directive_engine.py list [--active|--all|--expired]
    python3 directive_engine.py check [--task "context"]
    python3 directive_engine.py expire                    # Run sunset/expiry sweep
    python3 directive_engine.py status                    # Human-readable summary
    python3 directive_engine.py verify                    # Self-test
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DIRECTIVES_FILE = os.path.join(WORKSPACE, "data", "directives.json")
DIRECTIVES_LOG = os.path.join(WORKSPACE, "data", "directives_log.jsonl")

# ── CONSTANTS ──────────────────────────────────────────────────────────

# Scope types
SCOPE_STANDING = "standing"       # Permanent until explicitly retired
SCOPE_WINDOW = "window"           # Active within a time window, then expires
SCOPE_ONE_SHOT = "one_shot"       # Fulfilled once, then auto-retires
SCOPE_SESSION = "session"         # Current conversation only, not persisted to obligations

# Enforcement actions (graduated)
ENFORCE = "enforce"     # Full enforcement: include in context, check compliance
SOFTEN = "soften"       # Soft enforcement: note but don't block or escalate
NOTE = "note"           # Record only: log that it was considered, no action
SKIP = "skip"           # Skip entirely: expired, irrelevant, or budget exceeded

# Default sunset periods (days without reference before auto-expiry)
SUNSET_DAYS = {
    SCOPE_STANDING: 90,
    SCOPE_WINDOW: 30,
    SCOPE_ONE_SHOT: 14,
    SCOPE_SESSION: 0,  # Never persisted
}

# ── CLASSIFIER PATTERNS ───────────────────────────────────────────────

# Temporal scope detection
_STANDING_MARKERS = [
    r"\b(always|never|every\s+time|going\s+forward|from\s+now\s+on|permanently)\b",
    r"\b(standing\s+instruction|ongoing|continuous|indefinite)\b",
]
_WINDOW_MARKERS = [
    r"\b(this\s+week|until\s+\w+day|for\s+the\s+next|temporarily|for\s+now)\b",
    r"\b(until\s+i\s+say|until\s+further\s+notice|during\s+the?\s+\w+)\b",
    r"\b(this\s+sprint|this\s+month|this\s+quarter|before\s+the\s+deadline)\b",
    r"\b(for\s+\d+\s+(day|week|hour|minute)s?)\b",
]
_ONE_SHOT_MARKERS = [
    r"\b(next\s+time|once|just\s+this\s+(once|time)|one-time|the\s+next)\b",
    r"\b(when\s+you\s+get\s+to\s+it|first\s+chance|at\s+some\s+point)\b",
]

# Emotional temperature detection
# Each tuple: (pattern, weight, case_sensitive)
# case_sensitive=True means do NOT use re.IGNORECASE
_EMOTIONAL_SIGNALS = [
    (r"[!]{2,}", 0.3, False),               # Multiple exclamation marks
    (r"\b[A-Z]{4,}\b", 0.2, True),           # SHOUTING (4+ consecutive caps, case-sensitive)
    (r"\b(stupid|ridiculous|insane|terrible|awful|horrible|wtf|damn|hell)\b", 0.25, False),
    (r"\b(NEVER\s+EVER|absolutely\s+never|under\s+no\s+circumstances)\b", 0.2, False),
    (r"\b(I\s+told\s+you|how\s+many\s+times|stop\s+doing|quit\s+it)\b", 0.15, False),
    (r"\b(waste|wasting|wasted|useless|pointless)\b", 0.1, False),
]

# Calm/specific signals (increase literalness)
_CALM_SIGNALS = [
    (r"\b(please|specifically|the\s+rule\s+is|policy:|convention:)\b", 0.1),
    (r"\b(because|reason|rationale|since|given\s+that)\b", 0.1),
    (r"\b(should|prefer|when\s+possible|by\s+default)\b", 0.05),
]

# Duration extraction patterns
_DURATION_PATTERNS = [
    (r"(?:for|for\s+the\s+next)\s+(\d+)\s+day", "days"),
    (r"(?:for|for\s+the\s+next)\s+(\d+)\s+week", "weeks"),
    (r"(?:for|for\s+the\s+next)\s+(\d+)\s+hour", "hours"),
    (r"(?:for|for\s+the\s+next)\s+(\d+)\s+month", "months"),
    (r"until\s+(\w+day)", "weekday"),  # "until Thursday"
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


# ── CLASSIFIER ─────────────────────────────────────────────────────────

class DirectiveClassifier:
    """Rule-based classifier for incoming instructions.

    No LLM needed — deterministic, fast, auditable.
    Outputs: scope, confidence, literalness, emotional_origin, suggested_expiry.
    """

    @staticmethod
    def classify(text: str, source: str = "user",
                 raw_context: str = "") -> dict:
        """Classify an instruction text into directive metadata.

        Args:
            text: The instruction/directive text
            source: Who issued it ("user", "system", "inferred")
            raw_context: Optional surrounding context (conversation tone)

        Returns:
            {scope, confidence, literalness, emotional_origin,
             emotional_score, suggested_expiry_days, duration_detected,
             classification_reasons}
        """
        combined = f"{text} {raw_context}".strip()
        combined_lower = combined.lower()
        text_lower = text.lower()
        reasons = []

        # ── Scope detection ──
        scope = SCOPE_STANDING  # default
        scope_scores = {
            SCOPE_STANDING: 0.0,
            SCOPE_WINDOW: 0.0,
            SCOPE_ONE_SHOT: 0.0,
        }

        for pattern in _STANDING_MARKERS:
            if re.search(pattern, combined_lower):
                scope_scores[SCOPE_STANDING] += 1.0
                reasons.append(f"standing_marker: {pattern}")

        for pattern in _WINDOW_MARKERS:
            if re.search(pattern, combined_lower):
                scope_scores[SCOPE_WINDOW] += 1.5  # Boost: explicit window overrides default
                reasons.append(f"window_marker: {pattern}")

        for pattern in _ONE_SHOT_MARKERS:
            if re.search(pattern, combined_lower):
                scope_scores[SCOPE_ONE_SHOT] += 1.5
                reasons.append(f"one_shot_marker: {pattern}")

        # Pick highest-scoring scope
        best_scope = max(scope_scores, key=scope_scores.get)
        if scope_scores[best_scope] > 0:
            scope = best_scope
        # If no markers found, default to standing with moderate confidence

        # ── Emotional temperature ──
        emotional_score = 0.0
        for pattern, weight, case_sensitive in _EMOTIONAL_SIGNALS:
            flags = 0 if case_sensitive else re.IGNORECASE
            matches = re.findall(pattern, combined, flags)
            if matches:
                emotional_score += weight * len(matches)
                reasons.append(f"emotional_signal: {pattern} ({len(matches)}x)")

        emotional_score = min(1.0, emotional_score)
        emotional_origin = emotional_score > 0.4

        # ── Literalness ──
        # Start at 0.7 (reasonable default)
        literalness = 0.7

        # Calm signals increase literalness
        for pattern, boost in _CALM_SIGNALS:
            if re.search(pattern, combined_lower):
                literalness = min(1.0, literalness + boost)

        # Emotional signals decrease literalness
        literalness = max(0.2, literalness - emotional_score * 0.5)

        # Source affects literalness
        if source == "user":
            literalness = min(1.0, literalness + 0.1)
        elif source == "inferred":
            literalness = max(0.3, literalness - 0.2)

        # ── Confidence ──
        confidence = 0.7  # default

        if source == "user" and not emotional_origin:
            confidence = 0.9
        elif source == "user" and emotional_origin:
            confidence = 0.6  # Emotional user directives: record but with lower confidence
        elif source == "system":
            confidence = 0.8
        elif source == "inferred":
            confidence = 0.4

        # Higher scope_score = more confident classification
        if scope_scores[scope] > 1.0:
            confidence = min(1.0, confidence + 0.1)

        # ── Duration / expiry detection ──
        duration_detected = None
        suggested_expiry_days = SUNSET_DAYS.get(scope, 90)

        for pattern, unit in _DURATION_PATTERNS:
            match = re.search(pattern, combined_lower)
            if match:
                val = match.group(1)
                if unit == "days":
                    suggested_expiry_days = int(val)
                    duration_detected = f"{val} days"
                elif unit == "weeks":
                    suggested_expiry_days = int(val) * 7
                    duration_detected = f"{val} weeks"
                elif unit == "hours":
                    suggested_expiry_days = max(1, int(val) // 24)
                    duration_detected = f"{val} hours"
                elif unit == "months":
                    suggested_expiry_days = int(val) * 30
                    duration_detected = f"{val} months"
                elif unit == "weekday":
                    # Rough: assume within 7 days
                    suggested_expiry_days = 7
                    duration_detected = f"until {val}"
                scope = SCOPE_WINDOW  # Override to window if duration found
                reasons.append(f"duration_detected: {duration_detected}")
                break

        result = {
            "scope": scope,
            "confidence": round(confidence, 2),
            "literalness": round(literalness, 2),
            "emotional_origin": emotional_origin,
            "emotional_score": round(emotional_score, 2),
            "suggested_expiry_days": suggested_expiry_days,
            "duration_detected": duration_detected,
            "classification_reasons": reasons[:10],  # Cap for storage
        }

        # LLM fallback for ambiguous classifications (confidence < 0.5)
        if result["confidence"] < 0.5 and os.environ.get("DIRECTIVE_LLM_CLASSIFY") == "true":
            llm_result = _llm_classify_fallback(text, result)
            if llm_result:
                result.update(llm_result)
                result["classification_reasons"].append("llm_fallback_applied")

        return result


def _llm_classify_fallback(text, rule_result):
    """Use cheapest LLM via OpenRouter to refine ambiguous directive classification.

    Only called when rule-based confidence < 0.5 and DIRECTIVE_LLM_CLASSIFY=true.
    Returns dict with updated fields, or None on failure.
    """
    try:
        import requests

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            auth_file = os.path.join(os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw")), "agents/main/agent/auth-profiles.json")
            try:
                with open(auth_file) as f:
                    auth = json.load(f)
                api_key = auth.get("profiles", {}).get("openrouter:default", {}).get("key")
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                return None
        if not api_key:
            return None

        prompt = (
            "Classify this instruction/directive. Respond with ONLY valid JSON, no markdown.\n"
            f"Instruction: \"{text}\"\n\n"
            f"Rule-based result: scope={rule_result['scope']}, confidence={rule_result['confidence']}\n\n"
            "Classify into:\n"
            "- scope: \"standing\" (permanent rule), \"window\" (temporary/time-bound), or \"one_shot\" (do once)\n"
            "- confidence: 0.0-1.0 (how certain is this classification)\n"
            "- literalness: 0.0-1.0 (how literally should this be followed vs interpreted)\n"
            "- emotional_origin: true/false (is this driven by emotion/frustration)\n\n"
            "JSON output:"
        )

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "minimax/minimax-m2.5",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.0,
            },
            timeout=10,
        )
        resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
        parsed = json.loads(content)

        updates = {}
        if "scope" in parsed and parsed["scope"] in ("standing", "window", "one_shot"):
            updates["scope"] = parsed["scope"]
        if "confidence" in parsed and isinstance(parsed["confidence"], (int, float)):
            updates["confidence"] = round(max(0.0, min(1.0, float(parsed["confidence"]))), 2)
        if "literalness" in parsed and isinstance(parsed["literalness"], (int, float)):
            updates["literalness"] = round(max(0.0, min(1.0, float(parsed["literalness"]))), 2)
        if "emotional_origin" in parsed and isinstance(parsed["emotional_origin"], bool):
            updates["emotional_origin"] = parsed["emotional_origin"]

        return updates if updates else None

    except Exception:
        return None


# ── DIRECTIVE ENGINE ───────────────────────────────────────────────────

class DirectiveEngine:
    """Smart instruction management with classification, expiry, and discretion."""

    def __init__(self, filepath: str = DIRECTIVES_FILE):
        self.filepath = filepath
        self.classifier = DirectiveClassifier()
        self.data = self._load()
        self._obligation_tracker = None

    def _load(self) -> dict:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"directives": [], "version": 2, "schema": "directive_engine_v2"}

    def _save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        tmp = self.filepath + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.filepath)

    def _log(self, directive_id: str, event: str, detail: str = ""):
        entry = {
            "ts": _now(),
            "directive_id": directive_id,
            "event": event,
            "detail": detail[:500],
        }
        os.makedirs(os.path.dirname(DIRECTIVES_LOG), exist_ok=True)
        with open(DIRECTIVES_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    @property
    def obligation_tracker(self):
        """Lazy-load obligation tracker to avoid circular imports.

        Set _obligation_tracker = False to permanently disable (for testing).
        """
        if self._obligation_tracker is None:
            try:
                sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
                import _paths  # noqa: F401 — registers all script subdirs on sys.path
                from obligation_tracker import ObligationTracker
                self._obligation_tracker = ObligationTracker()
            except ImportError:
                self._obligation_tracker = False
        return self._obligation_tracker if self._obligation_tracker else None

    # ── INGEST ─────────────────────────────────────────────────────────

    def ingest(self, text: str, source: str = "user",
               raw_context: str = "",
               priority: str = "P2",
               check_command: Optional[str] = None,
               tags: Optional[list] = None,
               force_scope: Optional[str] = None,
               force_expiry_days: Optional[int] = None) -> dict:
        """Classify and record a new directive.

        This is the main entry point. It:
        1. Classifies the instruction (scope, confidence, literalness, emotional detection)
        2. Creates the directive record with full metadata
        3. Optionally links to obligation_tracker for enforceable directives
        4. Applies safety bounds

        Args:
            text: The instruction text
            source: "user", "system", or "inferred"
            raw_context: Surrounding conversation context (helps emotional detection)
            priority: "P0" through "P3"
            check_command: Optional shell command for verification (exit 0 = satisfied)
            tags: Optional tags for categorization
            force_scope: Override classifier scope detection
            force_expiry_days: Override expiry calculation

        Returns:
            The complete directive dict
        """
        # Classify
        classification = self.classifier.classify(text, source, raw_context)

        # Allow overrides
        scope = force_scope or classification["scope"]
        expiry_days = force_expiry_days or classification["suggested_expiry_days"]

        now = _now_dt()
        dir_id = f"dir_{now.strftime('%Y%m%d_%H%M%S')}_{len(self.data['directives'])}"

        # Calculate expiry
        expires_at = None
        if scope != SCOPE_STANDING or expiry_days < 90:
            expires_at = (now + timedelta(days=expiry_days)).isoformat()

        directive = {
            "id": dir_id,
            "text": text,
            "normalized": self._normalize(text),
            "source": source,
            "raw_context": raw_context[:500] if raw_context else "",
            "created_at": _now(),

            # Classification
            "scope": scope,
            "confidence": classification["confidence"],
            "literalness": classification["literalness"],
            "emotional_origin": classification["emotional_origin"],
            "emotional_score": classification["emotional_score"],
            "classification_reasons": classification["classification_reasons"],

            # Temporal
            "expires_at": expires_at,
            "sunset_days": SUNSET_DAYS.get(scope, 90),
            "last_referenced": _now(),

            # Priority & budget
            "priority": priority,
            "interference_budget": {
                "max_context_tokens": self._default_context_budget(priority),
                "max_checks_per_day": 12 if scope == SCOPE_STANDING else 4,
                "can_block_task": priority in ("P0", "P1") and not classification["emotional_origin"],
            },

            # Safety
            "safety": {
                "overrides_identity": False,  # ALWAYS false — SOUL.md is inviolable
                "requires_verification": check_command is not None,
                "can_be_softened": classification["literalness"] < 0.9,
                "emotional_dampening_applied": classification["emotional_origin"],
            },

            # Enforcement link
            "obligation_id": None,
            "verification_method": "check_command" if check_command else "contextual",
            "check_command": check_command,
            "tags": tags or [],

            # State
            "status": "active",
            "times_enforced": 0,
            "times_softened": 0,
            "times_skipped": 0,
            "decline_reason": None,
        }

        # Conflict detection — check for contradicting active directives
        conflicts = self._detect_conflicts(directive)
        directive["conflicts"] = conflicts
        if conflicts:
            for c in conflicts:
                if c["action"] == "supersede":
                    self.supersede(c["conflicting_id"], dir_id, c["reason"])

        # Session-bound directives don't persist to obligation_tracker
        if scope == SCOPE_SESSION:
            directive["status"] = "session_only"
            self._log(dir_id, "ingested_session", f"scope=session, not persisted")
        else:
            # Link to obligation tracker for durable enforcement
            self._link_obligation(directive)

        self.data["directives"].append(directive)
        self._save()
        self._log(dir_id, "ingested", (
            f"scope={scope}, conf={classification['confidence']}, "
            f"lit={classification['literalness']}, "
            f"emotional={classification['emotional_origin']}"
            + (f", conflicts={len(conflicts)}" if conflicts else "")
        ))

        return directive

    def _normalize(self, text: str) -> str:
        """Extract intent from instruction text, stripping emotional noise."""
        # Remove excessive punctuation
        normalized = re.sub(r'[!]{2,}', '!', text)
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        # Lowercase the first word if it's ALL CAPS (common in emotional text)
        words = normalized.split()
        if words and words[0] == words[0].upper() and len(words[0]) > 2:
            words[0] = words[0].lower()
            normalized = ' '.join(words)
        return normalized

    def _default_context_budget(self, priority: str) -> int:
        """Max tokens this directive can consume in prompt context injection."""
        return {"P0": 200, "P1": 150, "P2": 80, "P3": 40}.get(priority, 80)

    def _link_obligation(self, directive: dict):
        """Create a linked obligation in obligation_tracker for durable enforcement."""
        tracker = self.obligation_tracker
        if not tracker:
            return

        # Map scope to obligation frequency
        freq_map = {
            SCOPE_STANDING: "daily",
            SCOPE_WINDOW: "daily",
            SCOPE_ONE_SHOT: "every_heartbeat",
        }
        frequency = freq_map.get(directive["scope"], "daily")

        ob = tracker.record_obligation(
            label=directive["normalized"][:120],
            description=directive["text"],
            ob_type=directive["scope"],
            frequency=frequency,
            check_command=directive.get("check_command"),
            source=f"directive_engine:{directive['source']}",
            tags=directive.get("tags", []) + [f"dir:{directive['id']}"],
        )
        directive["obligation_id"] = ob["id"]
        self._log(directive["id"], "linked_obligation", ob["id"])

    # ── CONFLICT DETECTION ─────────────────────────────────────────────

    # Negation patterns that flip directive intent
    _NEGATION_PAIRS = [
        (r'\balways\b', r'\bnever\b'),
        (r'\bdo\b', r"\bdon'?t\b"),
        (r'\bshould\b', r"\bshouldn'?t\b"),
        (r'\bmust\b', r"\bmustn'?t\b"),
        (r'\benable\b', r'\bdisable\b'),
        (r'\bstart\b', r'\bstop\b'),
        (r'\bauto[- ]?commit\b', r"\bdon'?t.*commit\b"),
    ]

    def _detect_conflicts(self, new_directive: dict) -> list:
        """Check if a new directive contradicts any active directive.

        Returns list of conflict dicts: {conflicting_id, reason, action, similarity}.
        Action is 'supersede' (auto-replace) or 'flag' (needs user resolution).
        """
        active = [d for d in self.data["directives"]
                  if d["status"] in ("active", "session_only")]
        if not active:
            return []

        new_norm = new_directive["normalized"].lower()
        new_words = set(re.findall(r'\b\w{3,}\b', new_norm))
        conflicts = []

        for existing in active:
            ex_norm = existing["normalized"].lower()
            ex_words = set(re.findall(r'\b\w{3,}\b', ex_norm))

            # Word overlap (Jaccard) — only consider if topic overlaps significantly
            if not new_words or not ex_words:
                continue
            overlap = len(new_words & ex_words) / len(new_words | ex_words)
            if overlap < 0.25:
                continue

            # Check negation patterns
            negated = False
            for pos, neg in self._NEGATION_PAIRS:
                new_has_pos = bool(re.search(pos, new_norm))
                new_has_neg = bool(re.search(neg, new_norm))
                ex_has_pos = bool(re.search(pos, ex_norm))
                ex_has_neg = bool(re.search(neg, ex_norm))

                if (new_has_pos and ex_has_neg) or (new_has_neg and ex_has_pos):
                    negated = True
                    break

            if not negated:
                # Also check if one has "not"/"don't" and other doesn't, on same topic
                new_has_negation = bool(re.search(r"\b(not|no|don'?t|never|stop|disable)\b", new_norm))
                ex_has_negation = bool(re.search(r"\b(not|no|don'?t|never|stop|disable)\b", ex_norm))
                if overlap >= 0.5 and new_has_negation != ex_has_negation:
                    negated = True

            if negated:
                # Decide action: same source + newer = supersede; different source = flag
                if new_directive["source"] == existing["source"]:
                    action = "supersede"
                    reason = f"newer directive from same source contradicts: '{existing['normalized'][:60]}'"
                else:
                    action = "flag"
                    reason = f"contradicts directive from {existing['source']}: '{existing['normalized'][:60]}'"

                conflicts.append({
                    "conflicting_id": existing["id"],
                    "reason": reason,
                    "action": action,
                    "similarity": round(overlap, 2),
                })

        return conflicts

    # ── QUERY ──────────────────────────────────────────────────────────

    def get(self, directive_id: str) -> Optional[dict]:
        for d in self.data["directives"]:
            if d["id"] == directive_id:
                return d
        return None

    def list_active(self) -> list:
        """Return directives that are currently active (not expired/declined/retired)."""
        self._sweep_expiry()  # Housekeeping on read
        return [d for d in self.data["directives"]
                if d["status"] in ("active", "session_only")]

    def list_all(self) -> list:
        return self.data["directives"]

    def active_directives(self, task_context: str = "") -> list:
        """Get active directives relevant to the current task, with enforcement decisions.

        This is the main query interface for the heartbeat pipeline.
        Returns directives sorted by priority, each annotated with an enforcement decision.
        """
        active = self.list_active()
        results = []

        for d in active:
            decision = self.should_enforce(d["id"], task_context)
            if decision["action"] != SKIP:
                results.append({
                    "directive": d,
                    "decision": decision,
                })

        # Sort: enforce first, then soften, then note
        action_order = {ENFORCE: 0, SOFTEN: 1, NOTE: 2, SKIP: 3}
        results.sort(key=lambda x: (
            action_order.get(x["decision"]["action"], 3),
            {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(x["directive"]["priority"], 2),
        ))

        return results

    # ── DISCRETION LAYER ───────────────────────────────────────────────

    def should_enforce(self, directive_id: str,
                       task_context: str = "") -> dict:
        """Determine how to handle a directive right now.

        Returns graduated enforcement decision:
        - enforce: Full enforcement, include in context, check compliance
        - soften: Note it but don't block or escalate
        - note: Record that it was considered, no action
        - skip: Don't enforce (expired, irrelevant, budget exceeded)

        The reasoning layer retains discretion — this is a recommendation, not a jail.
        """
        d = self.get(directive_id)
        if not d:
            return {"action": SKIP, "reason": "directive not found"}

        # 1. Status checks
        if d["status"] not in ("active", "session_only"):
            return {"action": SKIP, "reason": f"status={d['status']}"}

        # 2. Expiry check
        if d.get("expires_at"):
            try:
                if _now_dt() > _parse_iso(d["expires_at"]):
                    self._expire(d, "past expiry date")
                    return {"action": SKIP, "reason": "expired"}
            except (ValueError, TypeError):
                pass

        # 3. Sunset check (no reference in sunset_days)
        if d.get("last_referenced") and d.get("sunset_days", 0) > 0:
            try:
                last_ref = _parse_iso(d["last_referenced"])
                days_since = (_now_dt() - last_ref).days
                if days_since > d["sunset_days"]:
                    self._expire(d, f"sunset: {days_since}d without reference (limit: {d['sunset_days']}d)")
                    return {"action": SKIP, "reason": f"sunset after {days_since}d"}
            except (ValueError, TypeError):
                pass

        # 4. Emotional dampening
        if d.get("emotional_origin") and d.get("literalness", 0.7) < 0.5:
            d["times_softened"] = d.get("times_softened", 0) + 1
            self._save()
            return {
                "action": SOFTEN,
                "reason": f"emotional_origin (score={d.get('emotional_score', 0):.2f}), literalness={d['literalness']:.2f}",
            }

        # 5. One-shot already fulfilled
        if d["scope"] == SCOPE_ONE_SHOT and d.get("times_enforced", 0) > 0:
            self._retire(d, "one_shot fulfilled")
            return {"action": SKIP, "reason": "one_shot already fulfilled"}

        # 6. Interference budget check
        budget = d.get("interference_budget", {})
        max_checks = budget.get("max_checks_per_day", 12)
        today_checks = self._today_check_count(d["id"])
        if today_checks >= max_checks:
            return {"action": NOTE, "reason": f"daily check budget exhausted ({today_checks}/{max_checks})"}

        # 7. Task relevance (simple keyword overlap)
        if task_context and not self._is_relevant(d, task_context):
            return {"action": NOTE, "reason": "low relevance to current task"}

        # 8. Default: enforce based on confidence and literalness
        confidence = d.get("confidence", 0.7)
        literalness = d.get("literalness", 0.7)

        if confidence >= 0.7 and literalness >= 0.6:
            action = ENFORCE
        elif confidence >= 0.5:
            action = SOFTEN
        else:
            action = NOTE

        # Update reference time
        d["last_referenced"] = _now()
        self._save()

        return {
            "action": action,
            "reason": f"conf={confidence:.2f}, lit={literalness:.2f}",
        }

    def _is_relevant(self, directive: dict, task_context: str) -> bool:
        """Simple keyword relevance check between directive and task."""
        d_words = set(re.findall(r'[a-z]{3,}', directive.get("normalized", "").lower()))
        t_words = set(re.findall(r'[a-z]{3,}', task_context.lower()))
        if not d_words:
            return True  # Can't determine relevance, assume relevant
        overlap = len(d_words & t_words)
        # Also check tags
        for tag in directive.get("tags", []):
            if tag.lower() in task_context.lower():
                return True
        return overlap >= 1 or len(d_words) <= 3  # Short directives always relevant

    def _today_check_count(self, directive_id: str) -> int:
        """Count how many times this directive was checked today (from log)."""
        today = _now_dt().strftime("%Y-%m-%d")
        count = 0
        try:
            with open(DIRECTIVES_LOG) as f:
                for line in f:
                    if directive_id in line and today in line:
                        count += 1
        except (FileNotFoundError, IOError):
            pass
        return count

    # ── EXPIRY & LIFECYCLE ─────────────────────────────────────────────

    def _sweep_expiry(self):
        """Check all directives for expiry/sunset. Called on list_active()."""
        now = _now_dt()
        changed = False
        for d in self.data["directives"]:
            if d["status"] not in ("active",):
                continue

            # Check explicit expiry
            if d.get("expires_at"):
                try:
                    if now > _parse_iso(d["expires_at"]):
                        self._expire(d, "past expiry date")
                        changed = True
                        continue
                except (ValueError, TypeError):
                    pass

            # Check sunset
            if d.get("last_referenced") and d.get("sunset_days", 0) > 0:
                try:
                    last_ref = _parse_iso(d["last_referenced"])
                    if (now - last_ref).days > d["sunset_days"]:
                        self._expire(d, f"sunset: {(now - last_ref).days}d unreferenced")
                        changed = True
                except (ValueError, TypeError):
                    pass

        if changed:
            self._save()

    def _expire(self, directive: dict, reason: str):
        """Mark a directive as expired and retire its linked obligation."""
        directive["status"] = "expired"
        directive["expired_at"] = _now()
        directive["expiry_reason"] = reason
        self._log(directive["id"], "expired", reason)

        # Also retire linked obligation
        if directive.get("obligation_id") and self.obligation_tracker:
            self.obligation_tracker.retire(directive["obligation_id"],
                                           f"directive expired: {reason}")
        self._save()

    def _retire(self, directive: dict, reason: str):
        """Manually retire a directive."""
        directive["status"] = "retired"
        directive["retired_at"] = _now()
        directive["retire_reason"] = reason
        self._log(directive["id"], "retired", reason)

        if directive.get("obligation_id") and self.obligation_tracker:
            self.obligation_tracker.retire(directive["obligation_id"],
                                           f"directive retired: {reason}")
        self._save()

    def retire(self, directive_id: str, reason: str = "manual"):
        """Public retirement interface."""
        d = self.get(directive_id)
        if d:
            self._retire(d, reason)

    def decline(self, directive_id: str, reason: str):
        """Decline a directive — records why enforcement was rejected.

        This is how the reasoning layer exercises discretion.
        A declined directive is logged but not enforced.
        """
        d = self.get(directive_id)
        if not d:
            return
        d["status"] = "declined"
        d["decline_reason"] = reason
        d["declined_at"] = _now()
        self._log(directive_id, "declined", reason)

        if d.get("obligation_id") and self.obligation_tracker:
            self.obligation_tracker.retire(d["obligation_id"],
                                           f"directive declined: {reason}")
        self._save()

    def supersede(self, old_id: str, new_id: str, reason: str = ""):
        """Mark an old directive as superseded by a new one."""
        old = self.get(old_id)
        if old:
            old["status"] = "superseded"
            old["superseded_by"] = new_id
            old["superseded_at"] = _now()
            self._log(old_id, "superseded", f"by {new_id}: {reason}")
            if old.get("obligation_id") and self.obligation_tracker:
                self.obligation_tracker.retire(old["obligation_id"],
                                               f"superseded by {new_id}")
            self._save()

    # ── CONTEXT ASSEMBLY ───────────────────────────────────────────────

    def build_context(self, task_context: str = "",
                      max_tokens: int = 500) -> str:
        """Build a context string for prompt injection during heartbeat.

        Respects per-directive token budgets and overall max_tokens limit.
        Returns a compact, prioritized summary of active directives.
        """
        active = self.active_directives(task_context)
        if not active:
            return ""

        lines = ["ACTIVE DIRECTIVES:"]
        tokens_used = 20  # Header overhead

        for item in active:
            d = item["directive"]
            decision = item["decision"]
            budget = d.get("interference_budget", {}).get("max_context_tokens", 80)

            # Estimate tokens (rough: 4 chars per token)
            entry_text = self._format_context_entry(d, decision)
            est_tokens = len(entry_text) // 4

            if tokens_used + est_tokens > max_tokens:
                lines.append(f"  ... ({len(active) - len(lines) + 1} more directives omitted)")
                break
            if est_tokens > budget:
                # Truncate to budget
                entry_text = entry_text[:budget * 4]

            lines.append(entry_text)
            tokens_used += est_tokens

        return "\n".join(lines)

    def _format_context_entry(self, d: dict, decision: dict) -> str:
        """Format a single directive for context injection."""
        scope_icon = {
            SCOPE_STANDING: "⟳",
            SCOPE_WINDOW: "⧖",
            SCOPE_ONE_SHOT: "①",
            SCOPE_SESSION: "💬",
        }.get(d["scope"], "•")

        action_prefix = {
            ENFORCE: "▸",
            SOFTEN: "~",
            NOTE: "○",
        }.get(decision["action"], "•")

        expiry_note = ""
        if d.get("expires_at"):
            try:
                days_left = (_parse_iso(d["expires_at"]) - _now_dt()).days
                if days_left <= 7:
                    expiry_note = f" [expires in {days_left}d]"
            except (ValueError, TypeError):
                pass

        emotional_note = ""
        if d.get("emotional_dampening_applied") or d.get("emotional_origin"):
            emotional_note = " [emotional origin — apply with judgment]"

        return (
            f"  {action_prefix} [{d['priority']}] {scope_icon} "
            f"{d['normalized'][:100]}{expiry_note}{emotional_note}"
        )

    # ── MIGRATION ──────────────────────────────────────────────────────

    def migrate_existing_obligations(self):
        """One-time migration: wrap existing obligations as directives.

        Adds directive metadata around existing obligation_tracker entries
        so they benefit from classification, expiry, and discretion.
        """
        tracker = self.obligation_tracker
        if not tracker:
            return 0

        existing_ob_ids = {d.get("obligation_id") for d in self.data["directives"]}
        migrated = 0

        for ob in tracker.list_all():
            if ob["id"] in existing_ob_ids:
                continue  # Already linked

            # Classify based on existing obligation metadata
            classification = self.classifier.classify(
                ob.get("description", ob.get("label", "")),
                source=ob.get("source", "system"),
            )

            scope = ob.get("type", SCOPE_STANDING)
            if scope not in (SCOPE_STANDING, SCOPE_WINDOW, SCOPE_ONE_SHOT, SCOPE_SESSION):
                scope = SCOPE_STANDING  # Normalize legacy types

            dir_id = f"dir_migrated_{ob['id']}"
            directive = {
                "id": dir_id,
                "text": ob.get("description", ob.get("label", "")),
                "normalized": ob.get("label", ""),
                "source": ob.get("source", "system"),
                "raw_context": "migrated from obligation_tracker",
                "created_at": ob.get("created_at", _now()),
                "scope": scope,
                "confidence": classification["confidence"],
                "literalness": classification["literalness"],
                "emotional_origin": classification["emotional_origin"],
                "emotional_score": classification["emotional_score"],
                "classification_reasons": ["migrated_from_obligation_tracker"],
                "expires_at": None,
                "sunset_days": SUNSET_DAYS.get(scope, 90),
                "last_referenced": _now(),
                "priority": "P2",
                "interference_budget": {
                    "max_context_tokens": 80,
                    "max_checks_per_day": 12,
                    "can_block_task": False,
                },
                "safety": {
                    "overrides_identity": False,
                    "requires_verification": ob.get("check_command") is not None,
                    "can_be_softened": True,
                    "emotional_dampening_applied": False,
                },
                "obligation_id": ob["id"],
                "verification_method": "check_command" if ob.get("check_command") else "contextual",
                "check_command": ob.get("check_command"),
                "tags": ob.get("tags", []),
                "status": "active" if ob["state"]["status"] == "active" else ob["state"]["status"],
                "times_enforced": ob["state"].get("satisfied_count", 0),
                "times_softened": 0,
                "times_skipped": 0,
                "decline_reason": None,
            }
            self.data["directives"].append(directive)
            migrated += 1
            self._log(dir_id, "migrated", f"from obligation {ob['id']}")

        if migrated:
            self._save()
        return migrated

    # ── STATUS ─────────────────────────────────────────────────────────

    def status_summary(self) -> str:
        """Human-readable status summary."""
        all_dirs = self.data["directives"]
        active = [d for d in all_dirs if d["status"] in ("active", "session_only")]
        expired = [d for d in all_dirs if d["status"] == "expired"]
        declined = [d for d in all_dirs if d["status"] == "declined"]

        lines = ["=== Directive Engine Status ==="]
        lines.append(f"Total directives: {len(all_dirs)}")
        lines.append(f"  Active: {len(active)}")
        lines.append(f"  Expired/sunset: {len(expired)}")
        lines.append(f"  Declined: {len(declined)}")
        lines.append("")

        scope_counts = {}
        for d in active:
            scope_counts[d["scope"]] = scope_counts.get(d["scope"], 0) + 1
        if scope_counts:
            lines.append("Active by scope:")
            for scope, count in sorted(scope_counts.items()):
                lines.append(f"  {scope}: {count}")
            lines.append("")

        emotional_count = sum(1 for d in active if d.get("emotional_origin"))
        if emotional_count:
            lines.append(f"Emotional origin (dampened): {emotional_count}")
            lines.append("")

        lines.append("Active directives:")
        for d in active:
            scope_icon = {"standing": "⟳", "window": "⧖", "one_shot": "①", "session": "💬"}.get(d["scope"], "•")
            exp = ""
            if d.get("expires_at"):
                try:
                    days = (_parse_iso(d["expires_at"]) - _now_dt()).days
                    exp = f" [expires {days}d]"
                except (ValueError, TypeError):
                    pass
            emo = " [emotional]" if d.get("emotional_origin") else ""
            lines.append(
                f"  {scope_icon} [{d['priority']}] {d['normalized'][:80]}"
                f" (conf={d['confidence']}, lit={d['literalness']}){exp}{emo}"
            )

        return "\n".join(lines)


# ── VERIFICATION ───────────────────────────────────────────────────────

def run_verification() -> bool:
    """Comprehensive self-test of the directive engine."""
    import tempfile
    print("=== Directive Engine Verification ===")
    errors = []

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        test_file = tf.name

    try:
        engine = DirectiveEngine(filepath=test_file)
        # Disconnect from real obligation tracker for testing
        # Use False sentinel (not None) to prevent lazy-loading
        engine._obligation_tracker = False

        # 1. Classification: standing instruction
        c = DirectiveClassifier.classify(
            "Always commit work before ending a session",
            source="user",
        )
        assert c["scope"] == SCOPE_STANDING, f"Expected standing, got {c['scope']}"
        assert c["confidence"] >= 0.7, f"Low confidence: {c['confidence']}"
        assert c["literalness"] >= 0.6, f"Low literalness: {c['literalness']}"
        assert not c["emotional_origin"], "Should not be emotional"
        print(f"  [PASS] Classify standing: scope={c['scope']}, conf={c['confidence']}, lit={c['literalness']}")

        # 2. Classification: window instruction
        c = DirectiveClassifier.classify(
            "Focus only on the harness repo this week",
            source="user",
        )
        assert c["scope"] == SCOPE_WINDOW, f"Expected window, got {c['scope']}"
        print(f"  [PASS] Classify window: scope={c['scope']}, expiry={c['suggested_expiry_days']}d")

        # 3. Classification: one-shot
        c = DirectiveClassifier.classify(
            "Next time you do a brain search, try parallel queries",
            source="user",
        )
        assert c["scope"] == SCOPE_ONE_SHOT, f"Expected one_shot, got {c['scope']}"
        print(f"  [PASS] Classify one_shot: scope={c['scope']}")

        # 4. Classification: emotional dampening
        c = DirectiveClassifier.classify(
            "STOP WASTING TOKENS ON USELESS RESEARCH!!! This is INSANE!!!",
            source="user",
        )
        assert c["emotional_origin"], "Should detect emotional origin"
        assert c["literalness"] < 0.6, f"Literalness should be dampened: {c['literalness']}"
        assert c["emotional_score"] > 0.4, f"Emotional score too low: {c['emotional_score']}"
        print(f"  [PASS] Emotional dampening: emotional={c['emotional_origin']}, score={c['emotional_score']:.2f}, lit={c['literalness']:.2f}")

        # 5. Classification: calm + specific
        c = DirectiveClassifier.classify(
            "Please use snake_case for all new Python functions, because it's the project convention",
            source="user",
        )
        assert c["literalness"] >= 0.7, f"Calm+specific should have high literalness: {c['literalness']}"
        assert not c["emotional_origin"]
        print(f"  [PASS] Calm+specific: lit={c['literalness']}, conf={c['confidence']}")

        # 6. Classification: duration detection
        c = DirectiveClassifier.classify(
            "For the next 3 days, prioritize only bug fixes",
            source="user",
        )
        assert c["scope"] == SCOPE_WINDOW
        assert c["suggested_expiry_days"] == 3
        assert c["duration_detected"] == "3 days"
        print(f"  [PASS] Duration detection: {c['duration_detected']}, expiry={c['suggested_expiry_days']}d")

        # 7. Ingest and query
        d1 = engine.ingest("Always run tests before committing", source="user", priority="P1")
        assert d1["id"]
        assert d1["scope"] == SCOPE_STANDING
        assert d1["status"] == "active"
        print(f"  [PASS] Ingest standing directive: {d1['id']}")

        d2 = engine.ingest("This week, focus on brain optimization only",
                          source="user", priority="P1")
        assert d2["scope"] == SCOPE_WINDOW
        print(f"  [PASS] Ingest window directive: {d2['id']}")

        d3 = engine.ingest("STOP DOING THAT STUPID THING!!! NEVER AGAIN!!!",
                          source="user")
        assert d3["emotional_origin"]
        assert d3["literalness"] < 0.5
        print(f"  [PASS] Ingest emotional directive: emotional={d3['emotional_origin']}, lit={d3['literalness']}")

        # 8. should_enforce decisions
        decision = engine.should_enforce(d1["id"], "running tests on brain module")
        assert decision["action"] in (ENFORCE, SOFTEN), f"Expected enforce/soften, got {decision['action']}"
        print(f"  [PASS] Enforce standing: action={decision['action']}")

        decision = engine.should_enforce(d3["id"], "doing research")
        assert decision["action"] == SOFTEN, f"Expected soften for emotional, got {decision['action']}"
        print(f"  [PASS] Soften emotional: action={decision['action']}, reason={decision['reason']}")

        # 9. active_directives
        active = engine.active_directives("testing brain module")
        assert len(active) >= 2, f"Expected ≥2 active directives, got {len(active)}"
        print(f"  [PASS] Active directives: {len(active)} returned")

        # 10. Context assembly
        context = engine.build_context("working on tests")
        assert "ACTIVE DIRECTIVES:" in context
        assert len(context) > 20
        print(f"  [PASS] Context assembly: {len(context)} chars")

        # 11. Expiry
        d_exp = engine.ingest("Do X for the next 0 days", source="user",
                             force_scope=SCOPE_WINDOW, force_expiry_days=0)
        # Manually set expiry to past
        d_exp["expires_at"] = (_now_dt() - timedelta(days=1)).isoformat()
        engine._save()
        decision = engine.should_enforce(d_exp["id"])
        assert decision["action"] == SKIP, f"Expected skip for expired, got {decision['action']}"
        assert "expired" in decision["reason"]
        print(f"  [PASS] Expiry enforcement: action={decision['action']}")

        # 12. Decline
        engine.decline(d3["id"], "emotional overreaction, user calmed down")
        d3_after = engine.get(d3["id"])
        assert d3_after["status"] == "declined"
        print(f"  [PASS] Decline: status={d3_after['status']}")

        # 13. One-shot fulfillment
        d_os = engine.ingest("Next time, try parallel queries", source="user",
                            force_scope=SCOPE_ONE_SHOT)
        d_os["times_enforced"] = 1  # Simulate fulfillment
        engine._save()
        decision = engine.should_enforce(d_os["id"])
        assert decision["action"] == SKIP
        print(f"  [PASS] One-shot auto-retire: action={decision['action']}")

        # 14. Supersede
        d_new = engine.ingest("Use pytest instead of unittest", source="user")
        engine.supersede(d1["id"], d_new["id"], "updated testing preference")
        d1_after = engine.get(d1["id"])
        assert d1_after["status"] == "superseded"
        print(f"  [PASS] Supersede: {d1['id']} → {d_new['id']}")

        # 15. Status summary
        status = engine.status_summary()
        assert "Directive Engine Status" in status
        print(f"  [PASS] Status summary: {len(status)} chars")

        # 16. Normalization
        normalized = engine._normalize("STOP DOING THIS!!! It's RIDICULOUS!!!")
        assert normalized.count("!") <= 3, f"Normalization should reduce punctuation: {normalized}"
        print(f"  [PASS] Normalization: '{normalized}'")

        # 17. Conflict detection
        d_commit = engine.ingest("Always auto-commit code changes after tasks", source="user")
        d_nocommit = engine.ingest("Never auto-commit code changes after tasks", source="user")
        assert len(d_nocommit.get("conflicts", [])) > 0, "Expected conflict detection"
        assert d_nocommit["conflicts"][0]["action"] == "supersede"
        old_d = engine.get(d_commit["id"])
        assert old_d["status"] == "superseded", f"Expected superseded, got {old_d['status']}"
        print(f"  [PASS] Conflict detection: {len(d_nocommit['conflicts'])} conflict(s), auto-superseded")

        print("\n=== ALL 17 CHECKS PASSED ===")
        return True

    except AssertionError as e:
        print(f"\n  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n  [FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            os.unlink(test_file)
        except OSError:
            pass


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: directive_engine.py <ingest|list|check|expire|status|verify|migrate>")
        sys.exit(1)

    cmd = sys.argv[1]
    engine = DirectiveEngine()

    if cmd == "ingest":
        if len(sys.argv) < 3:
            print("Usage: directive_engine.py ingest 'instruction text' [--source user|system|inferred]")
            sys.exit(1)
        text = sys.argv[2]
        source = "user"
        raw_context = ""
        priority = "P2"
        if "--source" in sys.argv:
            idx = sys.argv.index("--source")
            if idx + 1 < len(sys.argv):
                source = sys.argv[idx + 1]
        if "--context" in sys.argv:
            idx = sys.argv.index("--context")
            if idx + 1 < len(sys.argv):
                raw_context = sys.argv[idx + 1]
        if "--priority" in sys.argv:
            idx = sys.argv.index("--priority")
            if idx + 1 < len(sys.argv):
                priority = sys.argv[idx + 1]
        d = engine.ingest(text, source=source, raw_context=raw_context, priority=priority)
        print(f"Ingested: {d['id']}")
        print(f"  Scope: {d['scope']}, Confidence: {d['confidence']}, Literalness: {d['literalness']}")
        print(f"  Emotional: {d['emotional_origin']} (score={d['emotional_score']:.2f})")
        if d.get("expires_at"):
            print(f"  Expires: {d['expires_at'][:10]}")
        if d.get("obligation_id"):
            print(f"  Linked obligation: {d['obligation_id']}")
        if d.get("conflicts"):
            for c in d["conflicts"]:
                print(f"  Conflict [{c['action'].upper()}]: {c['reason']} (sim={c['similarity']})")

    elif cmd == "list":
        show_all = "--all" in sys.argv
        show_expired = "--expired" in sys.argv
        directives = engine.list_all() if show_all else engine.list_active()
        if show_expired:
            directives = [d for d in engine.list_all() if d["status"] == "expired"]
        for d in directives:
            scope_icon = {"standing": "⟳", "window": "⧖", "one_shot": "①", "session": "💬"}.get(d["scope"], "•")
            status = d["status"]
            if d.get("emotional_origin"):
                status += " [emotional]"
            print(f"  {scope_icon} {d['id']}: {d['normalized'][:60]} [{status}]")

    elif cmd == "check":
        task = ""
        if "--task" in sys.argv:
            idx = sys.argv.index("--task")
            if idx + 1 < len(sys.argv):
                task = sys.argv[idx + 1]
        active = engine.active_directives(task)
        print(f"Active directives for task context: '{task[:50]}'" if task else "Active directives:")
        for item in active:
            d = item["directive"]
            dec = item["decision"]
            print(f"  [{dec['action'].upper():7s}] {d['normalized'][:60]} ({dec['reason']})")
        if not active:
            print("  No active directives.")

    elif cmd == "context":
        task = ""
        if "--task" in sys.argv:
            idx = sys.argv.index("--task")
            if idx + 1 < len(sys.argv):
                task = sys.argv[idx + 1]
        context = engine.build_context(task)
        print(context if context else "(no active directives)")

    elif cmd == "expire":
        engine._sweep_expiry()
        expired = [d for d in engine.list_all() if d["status"] == "expired"]
        print(f"Expiry sweep complete. {len(expired)} expired directives total.")

    elif cmd == "status":
        print(engine.status_summary())

    elif cmd == "verify":
        success = run_verification()
        sys.exit(0 if success else 1)

    elif cmd == "migrate":
        count = engine.migrate_existing_obligations()
        print(f"Migrated {count} existing obligations to directives.")

    elif cmd == "decline":
        if len(sys.argv) < 4:
            print("Usage: directive_engine.py decline <directive_id> 'reason'")
            sys.exit(1)
        engine.decline(sys.argv[2], sys.argv[3])
        print(f"Declined: {sys.argv[2]}")

    elif cmd == "retire":
        if len(sys.argv) < 3:
            print("Usage: directive_engine.py retire <directive_id> ['reason']")
            sys.exit(1)
        reason = sys.argv[3] if len(sys.argv) > 3 else "manual"
        engine.retire(sys.argv[2], reason)
        print(f"Retired: {sys.argv[2]}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
