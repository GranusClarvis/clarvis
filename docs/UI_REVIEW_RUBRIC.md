# UI Review Rubric — 7 axes

A consistent scoring frame for UI surfaces shipped by Clarvis or any
per-project agent. The rubric is intentionally small (7 axes) so it can
be applied in minutes against a screenshot + the project's UX plan.

The reference implementation lives at `clarvis/cognition/ui_review.py`
(`review_ui_artifact(screenshot_path, ux_plan_path) -> dict`). The first
applied card is at `memory/cron/bb_ui_review_2026-05-04.md` (BunnyBagz
`/play/coinflip`).

---

## The seven axes

Each axis is scored 1–5. A score of `0` means **needs_review** — the
scorer was not given the evidence to judge that axis. Each scored axis
must come with a one-line piece of concrete evidence (a file path, a
test name, a measurement, a manifest count) — no vibes-only scores.

| # | Axis | Weight | What a 5 looks like |
|---|---|---|---|
| 1 | Visual hierarchy        | 1.50 | LCP element is unmistakable within ~1s; one primary action per surface. |
| 2 | Thumb-zone CTA placement | 1.50 | Primary CTA in the bottom 30 % of mobile viewport, target ≥ 44 px tall. |
| 3 | Colour contrast         | 1.25 | WCAG-AA on body, AAA on primary CTA labels; 0 axe violations on the surface. |
| 4 | Type rhythm             | 1.00 | Heading is 1.4–2.4× body; body line-height ≥ 1.4; ≤ 3 sizes per surface. |
| 5 | Whitespace / breathing  | 1.00 | Section gaps ≥ 0.75 rem; no clipped or wall-of-text panels. |
| 6 | Brand consistency       | 1.00 | All colour usages reference design tokens; brand wordmark unmodified. |
| 7 | Accessibility surface   | 1.25 | Visible focus rings, aria-live result announcements, touch targets ≥ 44 px. |

The weights are deliberately conservative — visual hierarchy and
thumb-zone placement are the highest-leverage axes for a betting / wallet
flow on mobile, contrast and accessibility next, type/whitespace/brand
as polish multipliers. Re-tune only if a project's North Star is
materially different (e.g. a desktop-first dashboard).

### Pass thresholds

A card **passes** when:
- All 7 axes are scored (none in `needs_review`).
- Weighted overall ≥ **3.5 / 5**.
- No single axis below **3**.

A pass means "ship it"; a card that fails at least one threshold means
"document the gap before merging or open a follow-up".

---

## Per-axis evidence cookbook

Every axis lists what evidence the scorer needs. A per-project agent
should produce these *before* invoking `review_ui_artifact` so the
scorer is reading observed facts, not asking the LLM to hallucinate.

### 1. Visual hierarchy
- LCP element label (`<h1>` text or hero component).
- Count of primary CTAs visible above-the-fold (target: 1).
- Headline-to-body font-size ratio.
- Detection signal: title element + `aria-label="..."` + button selector.

### 2. Thumb-zone CTA placement
- Bottom-edge offset of the primary CTA (px or `%` of viewport).
- `min-height` (px) of the CTA element.
- A CI test that asserts the placement, e.g.
  `apps/web/src/__tests__/thumb-zone-audit.test.tsx`. Cite it.

### 3. Colour contrast
- A contrast-audit artefact for this route. The reference implementation
  in BunnyBagz lives at `apps/web/src/lib/contrast-audit.ts` and emits
  axe-shaped JSON; reuse the pattern in other repos.
- Failed-node count (dark + light), pass count, manifest size.
- Score 5 only if 0 violations across both themes.

### 4. Type rhythm
- Heading font-size + body font-size, both in `rem`.
- Body `line-height`.
- Count of distinct font sizes used on the surface.
- Score ≤ 3 when more than 3 sizes appear or ratio is outside 1.4–2.4×.

### 5. Whitespace / breathing room
- Page-level `gap` and `padding`.
- Panel-level `padding` and inter-card gap.
- Any clipped element observation from the screenshot.

### 6. Brand consistency
- Count of literal hex / rgb / named colours in the surface source.
- Token-coverage: `var(--<brand>-*)` references / total colour usages.
- Score 5 only when the count of literals is 0 (palette is fully
  tokenised).

### 7. Accessibility surface
- Presence of `aria-live` result region (for games / async actions).
- Presence of `:focus-visible` styles (custom or default).
- Smallest touch target (px).
- Keyboard reachability test, if any.

---

## Evidence sidecar format

`review_ui_artifact` reads `<screenshot_path>.evidence.json` if present.
The sidecar maps axis_id → `{score, evidence}`:

```json
{
  "visual_hierarchy":      {"score": 4, "evidence": "Single h1 + one CTA"},
  "thumb_zone_cta":        {"score": 5, "evidence": "min-height 64px, marginTop:auto"},
  "color_contrast":        {"score": 5, "evidence": "0/22 axe violations"},
  "type_rhythm":           {"score": 3, "evidence": "4 sizes (slightly above target)"},
  "whitespace_breathing":  {"score": 4, "evidence": "page gap 0.75rem"},
  "brand_consistency":     {"score": 5, "evidence": "no literal hex"},
  "accessibility_surface": {"score": 4, "evidence": "aria-live=polite, no :focus-visible"}
}
```

Per-project agents can also pass the same map as the
`evidence_overrides=` keyword to `review_ui_artifact` — useful when
running the rubric inline from a CI step or another script.

---

## Workflow for per-project agents

1. **Take a screenshot** of the surface in the canonical viewport
   (default: iPhone SE 375×667 for mobile-first flows). Save it under
   `memory/cron/screenshots/<project>_<route>_<date>.png` (or per the
   project's convention).
2. **Collect evidence** — read the rendered source, the project's UX
   plan, and any contrast / thumb-zone audit artefacts. Write the
   findings into `<screenshot>.evidence.json`.
3. **Score** — `python3 -m clarvis.cognition.ui_review review <shot>
   <ux_plan>` for raw JSON, or `card <shot> <ux_plan> <out.md>` for the
   markdown card.
4. **File the card** — drop the markdown at
   `memory/cron/<project>_ui_review_<date>.md` so Clarvis's digest
   pipeline ingests it.
5. **Open follow-ups** — every axis below 3 becomes a queue task
   (`[<PROJECT>_UI_<axis>]`).

---

## Reusing across projects

This rubric is tuned for mobile-first product surfaces. Re-use it as-is
on Star-World-Order, Skrumpey companion, and any future BB sub-surface.
For desktop-first or content-only surfaces, two adaptations are
acceptable:
- Reduce the weight of `thumb_zone_cta` (rule still applies on small
  viewports — desktop just keeps the score parked at 5 if the surface
  isn't mobile-targeted).
- Add a project-specific axis 8 in a fork of the rubric **without**
  editing the canonical 7. Anything that lives in the canonical 7
  must be project-agnostic.

The `RUBRIC_VERSION` constant in `ui_review.py` bumps any time the axis
list or the scoring rules change. Any card cites the version it was
scored under; an old card under v1.0 stays valid even after a v1.1.
