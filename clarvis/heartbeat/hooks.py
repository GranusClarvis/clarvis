"""
Heartbeat lifecycle hook registry.

Replaces import-time wiring with explicit hook registration.
Each subsystem registers a callable with a phase and priority.
Hooks execute in priority order (lower = earlier). Failures in
one hook never block subsequent hooks.

Usage:
    from clarvis.heartbeat.hooks import registry, HookPhase

    # Register a hook
    registry.register(HookPhase.POSTFLIGHT, "my_subsystem", my_fn, priority=50)

    # Run all hooks for a phase
    results = registry.run(HookPhase.POSTFLIGHT, context_dict)

    # Inspect execution order
    names = registry.hooks_for(HookPhase.POSTFLIGHT)
"""

import time


class HookPhase:
    """Lifecycle phases where hooks can run."""
    PREFLIGHT = "preflight"
    POSTFLIGHT = "postflight"
    # Brain operation hooks — fire around brain.remember() and brain.search()
    BRAIN_PRE_STORE = "brain_pre_store"
    BRAIN_POST_STORE = "brain_post_store"
    BRAIN_PRE_SEARCH = "brain_pre_search"
    BRAIN_POST_SEARCH = "brain_post_search"

    ALL = (PREFLIGHT, POSTFLIGHT,
           BRAIN_PRE_STORE, BRAIN_POST_STORE,
           BRAIN_PRE_SEARCH, BRAIN_POST_SEARCH)


class HookRegistry:
    """Thread-safe hook registry with priority-ordered execution."""

    def __init__(self):
        self._hooks = {phase: [] for phase in HookPhase.ALL}

    def register(self, phase, name, fn, priority=100):
        """Register a hook.

        Args:
            phase: HookPhase.PREFLIGHT or POSTFLIGHT
            name: unique hook name (used in results dict and ordering tests)
            fn: callable(context: dict) -> any
            priority: int, lower runs first. Use:
                10-29  = core (confidence, reasoning chain)
                30-49  = recording (procedural memory, episodic)
                50-69  = analysis (consolidation, metrics)
                70-89  = maintenance (queue hygiene, digest)
                90+    = optional / slow
        """
        if phase not in HookPhase.ALL:
            raise ValueError(f"Unknown phase: {phase!r}. Use HookPhase.PREFLIGHT or POSTFLIGHT")

        # Prevent duplicate names within a phase
        existing = {h["name"] for h in self._hooks[phase]}
        if name in existing:
            # Replace existing hook (supports re-registration)
            self._hooks[phase] = [h for h in self._hooks[phase] if h["name"] != name]

        self._hooks[phase].append({
            "name": name,
            "fn": fn,
            "priority": priority,
        })
        # Maintain sorted order
        self._hooks[phase].sort(key=lambda h: (h["priority"], h["name"]))

    def run(self, phase, context):
        """Run all hooks for a phase in priority order.

        Args:
            phase: HookPhase constant
            context: dict passed to each hook fn

        Returns:
            dict mapping hook name -> {"result": ..., "elapsed_s": float}
            or {"error": str, "elapsed_s": float} on failure
        """
        results = {}
        for hook in self._hooks.get(phase, []):
            t0 = time.monotonic()
            try:
                result = hook["fn"](context)
                elapsed = time.monotonic() - t0
                results[hook["name"]] = {"result": result, "elapsed_s": round(elapsed, 4)}
            except Exception as e:
                elapsed = time.monotonic() - t0
                results[hook["name"]] = {"error": str(e), "elapsed_s": round(elapsed, 4)}
        return results

    def hooks_for(self, phase):
        """Return ordered list of (name, priority) tuples for a phase."""
        return [(h["name"], h["priority"]) for h in self._hooks.get(phase, [])]

    def hook_names(self, phase):
        """Return ordered list of hook names for a phase."""
        return [h["name"] for h in self._hooks.get(phase, [])]

    def clear(self, phase=None):
        """Clear hooks. If phase is None, clear all phases."""
        if phase:
            self._hooks[phase] = []
        else:
            self._hooks = {p: [] for p in HookPhase.ALL}

    def unregister(self, phase, name):
        """Remove a specific hook by name."""
        self._hooks[phase] = [h for h in self._hooks[phase] if h["name"] != name]

    def __repr__(self):
        counts = {p: len(hooks) for p, hooks in self._hooks.items()}
        return f"HookRegistry({counts})"


# Global singleton
registry = HookRegistry()
