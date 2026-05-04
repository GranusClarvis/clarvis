"""7-axis UI quality review rubric for Claude-Code-driven UX audits.

A consistent scoring frame any per-project agent can apply to a rendered
surface (screenshot + UX plan) before merging UI work. The seven axes are
fixed; the evidence collection is project-specific.

Axes (1–5 each, 5 = excellent):
  1. visual_hierarchy     — LCP element clarity, eye-flow, primary
                             affordance is obvious within ~1s.
  2. thumb_zone_cta       — primary CTA is in the bottom 30 % of the
                             mobile viewport with >=44 px target.
  3. color_contrast       — WCAG-AA on body text, AAA on primary CTA
                             labels. Delegates to a per-repo
                             ``contrast-audit`` artefact when present.
  4. type_rhythm          — heading vs body size ratio is between 1.4×
                             and 2.4×; line-height >= 1.4 on body.
  5. whitespace_breathing — section gaps >= 0.75rem, no clipped
                             elements, no walls of text.
  6. brand_consistency    — palette adherence: tokenised colours, no
                             stray literals, brand wordmark unmodified.
  7. accessibility_surface — visible focus rings, aria-live for results,
                              touch-target >= 44 px, keyboard reachability.

Evidence model:
  ``review_ui_artifact(screenshot_path, ux_plan_path)`` looks for an
  evidence sidecar at ``<screenshot_path>.evidence.json``. The sidecar
  is the deterministic input — it lets per-project agents collect
  evidence in whatever way fits their stack (contrast-audit JSON,
  Playwright bbox extraction, manual annotation) and feed a stable
  document into this scorer. When the sidecar is missing, axes default
  to ``needs_review`` (score=0) with a hint about what evidence the
  scorer needs to produce a real score.

Output schema (versioned via ``RUBRIC_VERSION``):
    {
      "rubric_version": "1.0",
      "screenshot": str,
      "ux_plan": str,
      "axes": {
          axis_id: {
              "name": str,
              "score": int (0–5; 0 = needs_review),
              "evidence": str (one-line),
              "rule": str (what '5' looks like),
              "weight": float,
          }, ...
      },
      "overall": float (0–5, weighted mean over scored axes),
      "passing": bool (overall >= 3.5 and no axis < 3),
      "scored_count": int,
      "needs_review": [axis_id, ...],
    }

CLI:
  python3 -m clarvis.cognition.ui_review review <screenshot> <ux_plan>
  python3 -m clarvis.cognition.ui_review card    <screenshot> <ux_plan> [out.md]
  python3 -m clarvis.cognition.ui_review schema
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

RUBRIC_VERSION = "1.0"

# Pass thresholds — tuned so a card with one axis at 2 still flags as
# failing, but a card with everything at 3 passes ("acceptable, ship").
PASSING_OVERALL = 3.5
PASSING_MIN_AXIS = 3


@dataclass(frozen=True)
class AxisSpec:
    axis_id: str
    name: str
    rule: str  # one-line description of what a "5" looks like
    weight: float  # contribution to overall score
    needs: str  # what evidence the scorer needs to produce a real score


# Order is meaningful — preserved when serialising and rendering cards.
AXES: List[AxisSpec] = [
    AxisSpec(
        axis_id="visual_hierarchy",
        name="Visual hierarchy",
        rule="LCP element is unmistakable within ~1s; one primary action per surface.",
        weight=1.5,
        needs="LCP element label, count of competing CTAs, headline-to-body ratio.",
    ),
    AxisSpec(
        axis_id="thumb_zone_cta",
        name="Thumb-zone CTA placement",
        rule="Primary CTA in the bottom 30% of mobile viewport, target >=44px tall.",
        weight=1.5,
        needs="bottom-edge offset of primary CTA + min-height in px (or test name).",
    ),
    AxisSpec(
        axis_id="color_contrast",
        name="Colour contrast",
        rule="WCAG-AA on body, AAA on primary CTA labels; 0 axe violations on the surface.",
        weight=1.25,
        needs="contrast-audit summary: failed-node count for this route in dark+light.",
    ),
    AxisSpec(
        axis_id="type_rhythm",
        name="Type rhythm",
        rule="Heading is 1.4–2.4× body; body line-height >=1.4; <=3 sizes per surface.",
        weight=1.0,
        needs="heading + body font-size in rem, line-height, count of distinct sizes.",
    ),
    AxisSpec(
        axis_id="whitespace_breathing",
        name="Whitespace / breathing room",
        rule="Section gaps >=0.75rem; no clipped or wall-of-text panels.",
        weight=1.0,
        needs="gap/padding values used + qualitative breath observation.",
    ),
    AxisSpec(
        axis_id="brand_consistency",
        name="Brand consistency",
        rule="All colour usages reference design tokens; brand wordmark unmodified.",
        weight=1.0,
        needs="count of literal hex/rgb in this surface's source, token-coverage %.",
    ),
    AxisSpec(
        axis_id="accessibility_surface",
        name="Accessibility surface",
        rule="Visible focus rings, aria-live result announcements, touch targets >=44px.",
        weight=1.25,
        needs="focus-style audit, aria-live presence, min touch-target size.",
    ),
]

AXIS_BY_ID: Dict[str, AxisSpec] = {a.axis_id: a for a in AXES}


def _validate_score(value: Any) -> int:
    """Return an int in [0, 5]; 0 reserved for 'needs_review'."""
    try:
        s = int(value)
    except (TypeError, ValueError):
        return 0
    if s < 0:
        return 0
    if s > 5:
        return 5
    return s


def _read_evidence(screenshot_path: str) -> Dict[str, Dict[str, Any]]:
    """Load sidecar evidence file if present.

    The sidecar lives at ``<screenshot_path>.evidence.json`` and maps
    axis_id -> {"score": int, "evidence": str}. Anything else is ignored.
    Missing file returns {} (every axis becomes needs_review).
    """
    sidecar = Path(str(screenshot_path) + ".evidence.json")
    if not sidecar.exists():
        return {}
    try:
        raw = json.loads(sidecar.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for axis_id, payload in raw.items():
        if axis_id not in AXIS_BY_ID:
            continue
        if not isinstance(payload, dict):
            continue
        out[axis_id] = {
            "score": _validate_score(payload.get("score", 0)),
            "evidence": str(payload.get("evidence", "")).strip(),
        }
    return out


def review_ui_artifact(
    screenshot_path: str,
    ux_plan_path: str,
    evidence_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> dict:
    """Produce a scored review card for a UI surface.

    Args:
        screenshot_path: Path to a rendered screenshot. Need not exist on
            disk — the path is recorded in the card and used to locate
            the evidence sidecar.
        ux_plan_path: Path to the project's UX plan document. Recorded
            in the card; not parsed by this scorer (per-project agents
            consult it when collecting evidence).
        evidence_overrides: Optional in-memory evidence map (same shape
            as the sidecar JSON). Useful for tests and ad-hoc reviews.

    Returns:
        A dict matching the schema in the module docstring.
    """
    evidence = dict(_read_evidence(screenshot_path))
    if evidence_overrides:
        for axis_id, payload in evidence_overrides.items():
            if axis_id not in AXIS_BY_ID or not isinstance(payload, dict):
                continue
            evidence[axis_id] = {
                "score": _validate_score(payload.get("score", 0)),
                "evidence": str(payload.get("evidence", "")).strip(),
            }

    axes: Dict[str, Dict[str, Any]] = {}
    needs_review: List[str] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for spec in AXES:
        ev = evidence.get(spec.axis_id)
        if ev and ev["score"] > 0:
            score = ev["score"]
            evidence_line = ev["evidence"] or "(no evidence provided)"
        else:
            score = 0
            evidence_line = f"needs_review — provide: {spec.needs}"
            needs_review.append(spec.axis_id)
        axes[spec.axis_id] = {
            "name": spec.name,
            "score": score,
            "evidence": evidence_line,
            "rule": spec.rule,
            "weight": spec.weight,
        }
        if score > 0:
            weighted_sum += score * spec.weight
            weight_total += spec.weight

    overall = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    scored_count = len(AXES) - len(needs_review)
    min_axis_score = min(
        (a["score"] for a in axes.values() if a["score"] > 0),
        default=0,
    )
    passing = (
        scored_count == len(AXES)
        and overall >= PASSING_OVERALL
        and min_axis_score >= PASSING_MIN_AXIS
    )

    return {
        "rubric_version": RUBRIC_VERSION,
        "screenshot": str(screenshot_path),
        "ux_plan": str(ux_plan_path),
        "axes": axes,
        "overall": round(overall, 2),
        "passing": passing,
        "scored_count": scored_count,
        "needs_review": needs_review,
    }


def render_card(review: dict, title: Optional[str] = None) -> str:
    """Render a markdown card from a review dict.

    The output format is what gets dropped at
    ``memory/cron/bb_ui_review_<date>.md`` so per-project agents and
    Clarvis's digest pipeline can ingest the same shape.
    """
    title = title or f"UI Review — {review.get('screenshot', '<unknown>')}"
    overall = review.get("overall", 0.0)
    passing = review.get("passing", False)
    verdict = "PASS" if passing else "REVIEW"
    lines = [
        f"# {title}",
        "",
        f"- Rubric version: `{review.get('rubric_version', '?')}`",
        f"- Screenshot: `{review.get('screenshot', '')}`",
        f"- UX plan: `{review.get('ux_plan', '')}`",
        f"- Overall: **{overall:.2f}/5** — {verdict}",
        f"- Scored: {review.get('scored_count', 0)}/{len(AXES)} axes",
        "",
        "| # | Axis | Score | Evidence |",
        "|---|---|---|---|",
    ]
    for i, spec in enumerate(AXES, start=1):
        a = review["axes"][spec.axis_id]
        score_cell = f"{a['score']}/5" if a["score"] > 0 else "—"
        # Pipe-escape evidence so it doesn't break the markdown table.
        evidence_cell = a["evidence"].replace("|", r"\|")
        lines.append(f"| {i} | {a['name']} | {score_cell} | {evidence_cell} |")
    if review.get("needs_review"):
        lines += [
            "",
            "## Needs evidence",
            "",
        ]
        for axis_id in review["needs_review"]:
            spec = AXIS_BY_ID[axis_id]
            lines.append(f"- **{spec.name}** — {spec.needs}")
    lines += [
        "",
        "## Rules (what a 5 looks like)",
        "",
    ]
    for spec in AXES:
        lines.append(f"- **{spec.name}** — {spec.rule}")
    return "\n".join(lines) + "\n"


def schema() -> dict:
    """Machine-readable rubric schema — useful for per-project agents."""
    return {
        "rubric_version": RUBRIC_VERSION,
        "passing_overall": PASSING_OVERALL,
        "passing_min_axis": PASSING_MIN_AXIS,
        "axes": [
            {
                "axis_id": a.axis_id,
                "name": a.name,
                "rule": a.rule,
                "weight": a.weight,
                "needs": a.needs,
            }
            for a in AXES
        ],
    }


def _cli(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__.split("CLI:")[1].strip(), file=sys.stderr)
        return 1
    cmd = argv[1]
    if cmd == "schema":
        print(json.dumps(schema(), indent=2))
        return 0
    if cmd in ("review", "card") and len(argv) >= 4:
        screenshot, ux_plan = argv[2], argv[3]
        review = review_ui_artifact(screenshot, ux_plan)
        if cmd == "review":
            print(json.dumps(review, indent=2))
            return 0
        # cmd == "card"
        out = argv[4] if len(argv) >= 5 else None
        md = render_card(review)
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(md)
            print(f"wrote {out}")
        else:
            print(md)
        return 0
    print("usage: ui_review.py {review|card|schema} [args]", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
