#!/usr/bin/env python3
"""
MemoryBank — Ebbinghaus Forgetting Curve Reference Implementation
=================================================================

A clean, self-contained memory bank that models exponential forgetting
using the Ebbinghaus retention formula:

    R(t) = e^(-t / S)

where R is retention (0.0–1.0), t is elapsed time since last rehearsal,
and S is the memory's strength (grows with each recall via spaced repetition).

Spaced repetition boost:  S_new = S_old + boost * S_old^(-0.3)
  - Diminishing returns as strength grows
  - Base boost scaled by the memory's importance

Forgetting threshold: memories with R < 0.1 become inaccessible until
explicitly refreshed (they are not deleted).

Part of EXTERNAL_CHALLENGE:research-impl-03.
"""

from __future__ import annotations

import math
import dataclasses
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Memory:
    """A single memory entry with forgetting-curve metadata."""
    key: str
    content: str
    importance: float          # 0.0–1.0, affects strength boost on recall
    strength: float            # S in the Ebbinghaus formula
    created_at: float          # simulated time (hours) when first stored
    last_recalled: float       # simulated time (hours) of most recent recall
    recall_count: int = 0      # how many times this memory has been recalled
    forgotten: bool = False    # True when retention drops below threshold

    def retention(self, now: float) -> float:
        """Compute current retention R(t) = e^(-t/S)."""
        t = max(0.0, now - self.last_recalled)
        if self.strength <= 0:
            return 0.0
        return math.exp(-t / self.strength)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STRENGTH = 8.0       # initial S for a brand-new memory (hours)
FORGET_THRESHOLD = 0.1       # R below this → memory is "forgotten"
BOOST_BASE = 6.0             # base boost multiplier for spaced repetition
STRENGTH_EXPONENT = -0.3     # diminishing-returns exponent


# ---------------------------------------------------------------------------
# MemoryBank
# ---------------------------------------------------------------------------

class MemoryBank:
    """
    A memory store with Ebbinghaus forgetting curves and spaced repetition.

    Time is simulated: call ``tick(hours)`` to advance the internal clock.
    """

    def __init__(self) -> None:
        self._memories: dict[str, Memory] = {}
        self._now: float = 0.0          # simulated clock (hours)
        self._forgotten_count: int = 0  # memories that crossed the threshold

    # -- public API ---------------------------------------------------------

    def store(self, key: str, content: str, importance: float = 0.5) -> Memory:
        """Store a new memory (or overwrite an existing one)."""
        importance = max(0.0, min(1.0, importance))
        initial_strength = DEFAULT_STRENGTH * (0.5 + importance)
        mem = Memory(
            key=key,
            content=content,
            importance=importance,
            strength=initial_strength,
            created_at=self._now,
            last_recalled=self._now,
        )
        self._memories[key] = mem
        return mem

    def recall(self, key: str) -> Optional[str]:
        """
        Attempt to recall a memory by key.

        Returns the content if the memory exists and retention >= threshold,
        otherwise returns None.  A successful recall boosts the memory's
        strength via spaced repetition.
        """
        mem = self._memories.get(key)
        if mem is None:
            return None

        r = mem.retention(self._now)
        if r < FORGET_THRESHOLD:
            mem.forgotten = True
            return None

        # Spaced-repetition boost
        boost = BOOST_BASE * mem.importance
        mem.strength += boost * (mem.strength ** STRENGTH_EXPONENT)
        mem.last_recalled = self._now
        mem.recall_count += 1
        mem.forgotten = False
        return mem.content

    def refresh(self, key: str) -> Optional[str]:
        """
        Re-learn a forgotten memory (resets its last_recalled time and
        gives a small strength boost).  Returns content or None if the
        key does not exist at all.
        """
        mem = self._memories.get(key)
        if mem is None:
            return None
        mem.last_recalled = self._now
        mem.strength += BOOST_BASE * 0.5 * mem.importance
        mem.recall_count += 1
        mem.forgotten = False
        if mem.forgotten:
            self._forgotten_count = max(0, self._forgotten_count - 1)
        return mem.content

    def search(self, query: str) -> list[tuple[str, str, float]]:
        """
        Simple substring search across all *accessible* memories.

        Returns list of (key, content, retention) sorted by retention desc.
        """
        query_lower = query.lower()
        results: list[tuple[str, str, float]] = []
        for mem in self._memories.values():
            r = mem.retention(self._now)
            if r < FORGET_THRESHOLD:
                continue
            if query_lower in mem.content.lower() or query_lower in mem.key.lower():
                results.append((mem.key, mem.content, round(r, 4)))
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def tick(self, hours: float = 1.0) -> None:
        """Advance simulated time and update forgotten flags."""
        self._now += hours
        self._update_forgotten()

    def stats(self) -> dict:
        """Return summary statistics."""
        total = len(self._memories)
        if total == 0:
            return {"total": 0, "accessible": 0, "forgotten": 0, "avg_retention": 0.0}
        retentions = [m.retention(self._now) for m in self._memories.values()]
        forgotten = sum(1 for r in retentions if r < FORGET_THRESHOLD)
        avg_r = sum(retentions) / total
        return {
            "total": total,
            "accessible": total - forgotten,
            "forgotten": forgotten,
            "avg_retention": round(avg_r, 4),
            "simulated_hours": round(self._now, 2),
        }

    def dump(self) -> list[dict]:
        """Return all memories with current retention values."""
        out = []
        for mem in self._memories.values():
            r = mem.retention(self._now)
            out.append({
                "key": mem.key,
                "importance": mem.importance,
                "strength": round(mem.strength, 3),
                "retention": round(r, 4),
                "recall_count": mem.recall_count,
                "forgotten": r < FORGET_THRESHOLD,
                "age_hours": round(self._now - mem.created_at, 1),
            })
        out.sort(key=lambda x: x["retention"], reverse=True)
        return out

    # -- integration hook ---------------------------------------------------

    @classmethod
    def from_clarvis_brain(cls, brain_instance) -> "MemoryBank":
        """
        Import memories from a Clarvis brain instance (best-effort).

        Expects brain_instance to have a ``search(query, n)`` method that
        returns objects with ``.document`` and ``.metadata`` attributes.
        """
        bank = cls()
        try:
            results = brain_instance.search("*", n=100)
            for item in results:
                doc = getattr(item, "document", str(item))
                meta = getattr(item, "metadata", {})
                key = meta.get("id", doc[:40])
                importance = float(meta.get("importance", 0.5))
                bank.store(key, doc, importance)
        except Exception as exc:
            print(f"[MemoryBank] from_clarvis_brain partial import: {exc}")
        return bank

    # -- internal -----------------------------------------------------------

    def _update_forgotten(self) -> None:
        """Mark memories below the forgetting threshold."""
        for mem in self._memories.values():
            r = mem.retention(self._now)
            if r < FORGET_THRESHOLD and not mem.forgotten:
                mem.forgotten = True
                self._forgotten_count += 1


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

def _bar(value: float, width: int = 30) -> str:
    """Render a simple ASCII bar."""
    filled = int(value * width)
    return "#" * filled + "." * (width - filled)


def demo() -> None:
    """
    Demonstrate the MemoryBank with forgetting curves and spaced repetition.

    Creates 10 memories, simulates 72 hours, recalls some periodically,
    and prints retention curves showing decay vs. reinforcement.
    """
    print("=" * 70)
    print("  MemoryBank Demo — Ebbinghaus Forgetting Curves")
    print("=" * 70)

    bank = MemoryBank()

    # -- Store 10 sample memories with varying importance -------------------
    samples = [
        ("capital-france",    "The capital of France is Paris",              0.9),
        ("pi-digits",         "Pi is approximately 3.14159265358979",        0.7),
        ("grocery-list",      "Buy milk, eggs, bread, and butter",          0.3),
        ("meeting-tuesday",   "Team meeting is on Tuesday at 10am",         0.4),
        ("python-import",     "Use 'import math' for math functions",       0.8),
        ("birthday-mom",      "Mom's birthday is March 15th",               0.6),
        ("wifi-password",     "WiFi password: correct-horse-battery",       0.5),
        ("git-rebase",        "git rebase -i HEAD~3 for interactive rebase", 0.7),
        ("random-fact",       "A group of flamingos is called a flamboyance", 0.2),
        ("quadratic",         "x = (-b +/- sqrt(b^2-4ac)) / 2a",           0.85),
    ]

    for key, content, imp in samples:
        bank.store(key, content, importance=imp)
    print(f"\nStored {len(samples)} memories.\n")

    # -- Define which memories get periodic recall (spaced repetition) ------
    recall_schedule: dict[str, list[int]] = {
        # key → list of hours at which we recall it
        "capital-france":  [1, 4, 12, 36],      # frequent review
        "python-import":   [2, 8, 24],           # moderate review
        "quadratic":       [3, 12, 48],           # spaced review
        "birthday-mom":    [6, 24],               # occasional review
    }

    # -- Simulate 72 hours, hour by hour -----------------------------------
    # Track retention history for curve display
    history: dict[str, list[float]] = {key: [] for key, _, _ in samples}

    for hour in range(73):
        # Perform scheduled recalls
        for key, schedule in recall_schedule.items():
            if hour in schedule:
                result = bank.recall(key)
                if result:
                    pass  # successful recall, strength boosted

        # Record retention snapshot
        for mem in bank._memories.values():
            history[mem.key].append(mem.retention(bank._now))

        # Advance time
        if hour < 72:
            bank.tick(hours=1)

    # -- Print retention curves ---------------------------------------------
    print("-" * 70)
    print("  Retention Curves (72 hours)    [# = retained, . = decayed]")
    print("-" * 70)

    recalled_keys = set(recall_schedule.keys())
    # Show recalled memories first, then unrehearsed
    sorted_keys = sorted(history.keys(),
                         key=lambda k: (k not in recalled_keys,
                                        -history[k][-1]))

    for key in sorted_keys:
        vals = history[key]
        r_final = vals[-1]
        recalled = key in recalled_keys
        tag = " [recalled]" if recalled else ""
        status = "ALIVE" if r_final >= FORGET_THRESHOLD else "FORGOTTEN"
        mem = bank._memories[key]
        print(f"\n  {key}{tag}")
        print(f"    importance={mem.importance:.1f}  strength={mem.strength:.2f}"
              f"  recalls={mem.recall_count}  R={r_final:.4f}  [{status}]")

        # Show curve at 6 time-points: 0h, 12h, 24h, 36h, 48h, 72h
        checkpoints = [0, 12, 24, 36, 48, 72]
        line = "    "
        for cp in checkpoints:
            r = vals[cp] if cp < len(vals) else vals[-1]
            line += f"  {cp:2d}h:{r:.2f}"
        print(line)
        print(f"    [{_bar(r_final)}] {r_final:.1%}")

    # -- Summary ------------------------------------------------------------
    print("\n" + "=" * 70)
    s = bank.stats()
    print(f"  Summary at t={s['simulated_hours']}h:")
    print(f"    Total memories:     {s['total']}")
    print(f"    Still accessible:   {s['accessible']}")
    print(f"    Forgotten (R<0.1):  {s['forgotten']}")
    print(f"    Average retention:  {s['avg_retention']:.4f}")
    print("=" * 70)

    # -- Search demo --------------------------------------------------------
    for query in ["capital", "password", "math"]:
        print(f"\n  Search demo: query='{query}'")
        results = bank.search(query)
        if results:
            for key, content, r in results:
                print(f"    [{r:.2f}] {key}: {content}")
        else:
            print("    (no accessible matches — forgotten or no match)")

    print()


if __name__ == "__main__":
    demo()
