# BunnyBagz QA Defect Taxonomy (2026-05-10)

_Stable defect-class vocabulary that the QA harness should emit and that BB
follow-up tasks should be triaged against. Derived from the
2026-05-04 UI review, the 2026-05-09 keyboard-nav audit, the
2026-05-10 QA-harness run (`apps/web/test-results/qa-harness/`), and the six
open BB_QA_* / BB_PHASE3_* items in `memory/evolution/QUEUE.md` lines 692–697._

Each class is the contract between **what the harness emits** (a stable
`causeCode`) and **what the fix template looks like** (a file/component pattern
+ acceptance bar). When a new variant fails, the triager picks the class,
applies the template, and the harness re-asserts against the acceptance bar —
no re-derivation from raw `report.json` rows.

| # | Defect class | Severity | Harness cause-code(s) | Maps to open item |
|---|---|---|---|---|
| 1 | `mobile-horizontal-overflow` | HIGH | `horizontal-overflow`, `document-scrolls-horizontally`, `shell-exceeds-viewport`, `element-exceeds-viewport`, `element-exceeds-viewport-inside-scroller` | `BB_QA_HARNESS_DIAGNOSTICS_HARDENING` (vocabulary), reused by future surface fixes |
| 2 | `touch-target-floor` | HIGH | `touch-target-undersized`, `touch-target-near-miss` | `BB_QA_MOBILE_TOUCH_TARGET_FLOOR` (shipped; class kept as regression contract) |
| 3 | `light-theme-hydration` | HIGH | `hydration-mismatch` (infra) when SSR/CSR diverge under `data-theme="light"` | `BB_QA_WALLET_LIGHT_THEME_HYDRATION_FIX` |
| 4 | `legibility-floor-12px` | MED | `text-below-readable-floor` | `BB_QA_TRUST_STRIP_LEGIBILITY_PASS` |
| 5 | `animation-mount-missing` | MED | `{spec}-target-missing`, `{spec}-no-motion`, `{spec}-observation-failed` | `BB_QA_DICE_SETTLE_ANIMATION_RESTORE` |
| 6 | `focus-ring-invisible` | HIGH | (proposed) `focus-ring-invisible`; today emitted as UX_PLAN §7 audit notes in `bb_keyboard_nav_audit_2026-05-09.md` D1 | `BB_PHASE3_KBNAV_FOCUS_RING_FIX` (shipped) — class kept as regression contract; reused for any new dark-theme CTA |
| 7 | `tab-order-skip` | MED | (proposed) `tab-order-skip`, `focus-trap-missing` | `BB_PHASE3_KBNAV_FOCUS_RING_FIX` follow-up (D2 in the kbnav audit — WalletSheet has no Tab focus trap) |
| 8 | `harness-instrumentation-gap` | LOW | (meta) — emitted when a finding has no `causeCode`, no `selector`, no measured dimensions, or a `report.json` row that the renderer cannot per-variant-attribute | `BB_QA_HARNESS_DIAGNOSTICS_HARDENING` |

Severity rationale (project-wide rule):

- **HIGH** = blocks a user from completing a primary task on the phone-first
  surface (cannot scroll past the page, cannot hit a CTA, cannot see focus to
  re-key after a Tab, cannot trust what they see because the page re-renders).
- **MED** = primary task still completes, but a sub-task is degraded
  (illegible copy, missing settle feedback, focus order strange enough that
  power users abandon).
- **LOW** = harness/process gap, no user-visible defect.

---

## 1. `mobile-horizontal-overflow`

**Definition.** Any element extends past the mobile viewport width and is not
clipped by an `overflow:auto|scroll|hidden` ancestor — i.e. the user can swipe
the whole document sideways or sees a horizontal swipe band inside a
non-scrolling region.

**Detection heuristic.**

- Harness probe: `audits.mjs:auditMobileLayout` walks
  `document.querySelectorAll("*")`, computes `rect.right - vw > overflowTol`,
  and checks ancestor `getComputedStyle().overflowX ∉ {auto, scroll, hidden}`.
- Dedicated audit: `audits.mjs:auditHorizontalOverflow` (strict tolerance) at
  the document level — picks up the **first** offender and emits the route +
  selector + `right=Npx` for the report renderer.
- Viewports under test: 375×812 (`iphone-13`), 414×896 (`pixel-7`), 360×780
  (`galaxy-s23`). Desktop is not subject to this class.

**Severity.** HIGH — phone users cannot navigate past the offending strip.

**Fix template.**

- File pattern: the component whose rendered DOM is wider than the surface
  shell (often a `<TrustStrip>`, `<RecentBets>` row, or a wallet sheet
  identity row).
- Pattern: wrap the offending row in a `flex` container with
  `flex-wrap: wrap` or `overflow-x: auto` + explicit
  `max-width: 100%` on the parent; never on the shell `<main>`. Tabular rows
  should switch to vertical stacks under `(max-width: 480px)` rather than
  shrinking the cells below the legibility floor.
- Acceptance bar:
  - `audits.mjs:HORIZONTAL_OVERFLOW_TOLERANCE_PX` audit emits **zero**
    `horizontal-overflow` findings for the surface on all three mobile
    viewports.
  - Vitest: `apps/web/src/<component>/__tests__/<component>.test.tsx` includes
    a `width: 360` jsdom render asserting
    `getBoundingClientRect().right <= 360`.

---

## 2. `touch-target-floor`

**Definition.** An interactive element (button, link, `role=button`, native
`input/select`, or an element with a click handler) renders with `min(width,
height) < 44px` in mobile viewports.

**Detection heuristic.**

- Probe: `audits.mjs` lines 213–254. `touchMin = TOUCH_TARGET_MIN = 44`.
- Two cause codes:
  - `touch-target-undersized` — `small < touchMin - 6` (≤37 px). Hard fail.
  - `touch-target-near-miss` — `touchMin - 6 ≤ small < touchMin` (38–43 px).
    Soft fail.
- Selector capture: `buildSelectorForElement` in `audits.mjs` produces a
  stable `[data-testid="..."]` or tag+aria-label string.

**Severity.** HIGH — direct hit-rate impact on phone.

**Fix template.**

- Two utility classes exist in `globals.css` (shipped under
  `BB_QA_MOBILE_TOUCH_TARGET_FLOOR`):
  - `.bb-hit-target-44` — `inline-flex` 44×44 box (use when the **rendered**
    box can grow).
  - `.bb-hit-target-44--inline` — `padding-block` + negative `margin-block` —
    44×44 hit area without changing the rendered box (use inside narrow
    strips like `<TrustStrip>` or `<LegalFooter>`).
- Library-internal elements (e.g. RainbowKit's `data-testid="rk-connect-button"`)
  need an `!important` global override (precedent set in the shipped fix).
- Acceptance bar:
  - `report.json` per-variant `touch-target-undersized` count = **0** on all
    three mobile viewports.
  - `report.json` per-variant `touch-target-near-miss` count ≤ **2** across
    the entire surface (the soft band is a budget, not a floor).
  - Vitest fixture renders the surface and asserts
    `getBoundingClientRect()` width ≥ 44 and height ≥ 44 for every
    `data-testid` matching `/-link$|-button$|-cta$|^rk-/`.

---

## 3. `light-theme-hydration`

**Definition.** React emits a hydration-mismatch console error when the
harness sets `localStorage["bunnybagz:theme"]="light"` (or
`<html data-theme="light">` via `addInitScript`) and then mounts. The SSR HTML
is dark-default; the CSR pass sees the light cookie and re-renders, which
diverges DOM attributes (toggle button text, `aria-label`, theme-keyed
class names).

**Detection heuristic.**

- Console listener: `audits.mjs` lines 879–924 — patterns
  `/hydration failed/i`, `/server rendered text didn't match the client/i`,
  `/server\/client branch/i`.
- Emits `infra` finding with cause-code `hydration-mismatch`, route + selector
  scoped from the React error frame when available.
- Only surfaces with theme-keyed branches are vulnerable; today: `WalletSheet`
  (toggle), `wallet-page`, `wallet-profile-history`.

**Severity.** HIGH — React falls back to client render, the user sees a flash,
and the page-level state machine momentarily desyncs.

**Fix template.**

- File pattern: any `useState(detectInitialThemeOrSimilar())` initialiser that
  reads `localStorage` / `window` / `document.documentElement.dataset`.
- Replace with `useState("dark")` (or the SSR-stable default) + a mount
  `useEffect` that resolves the real value and gates dataset/localStorage
  writes on a `hydrated` flag. Keep the bootstrap `<head>` script
  (`layout-bootstrap.ts`) painting the right palette on first frame so the
  user never sees the dark flash.
- Acceptance bar:
  - Regression test: `apps/web/src/<route>/__tests__/page.test.tsx` includes
    a `light-theme-hydration` describe-block — `renderToString` →
    `localStorage["bunnybagz:theme"]="light"` → `hydrateRoot` with
    `onCaughtError`/`onRecoverableError`/`onUncaughtError` asserting no
    error message matches `/hydration|didn't match|server rendered/i`.
  - Verified red-when-reverted: the test must fail without the fix and pass
    with it (the `BB_QA_WALLET_LIGHT_THEME_HYDRATION_FIX` ship-note
    documents this verification step).
  - `report.json` per-variant `hydration-mismatch` count = **0** in both
    themes.

---

## 4. `legibility-floor-12px`

**Definition.** Visible text renders with `computedFontSize < 12px` on a
mobile viewport. The 12 px floor is the audit's chosen `textMin` and aligns
with WCAG-2.2 sub-criterion 1.4.4 read on a phone at a normal arm's-length
distance.

**Detection heuristic.**

- Probe: `audits.mjs` lines 270–296, cause-code `text-below-readable-floor`.
- Iterates all elements with non-empty `textContent`, reads
  `parseFloat(getComputedStyle(el).fontSize)`, flags `< 12`.
- Excludes screen-reader-only nodes (`clip: rect(...)`, `width: 1px`).
- Hotspots seen in QA: `<TrustStrip>` 0.625rem (10 px) helper copy, footer
  legal links at 0.75rem (12 px — at floor, borderline), pill chips inside
  `<RecentBets>` at 0.625rem.

**Severity.** MED — copy is read-on-demand (not the primary CTA path), but
trust copy must be legible or the trust surface fails its job.

**Fix template.**

- File pattern: components whose inline `style={{ fontSize: "..." }}` or
  Tailwind/CSS class sets a size below 0.75rem (12 px).
- Resize to `0.8125rem` (13 px) as the BB minimum, paired with
  `letter-spacing: 0.01em` to maintain rhythm. For badge/pill chips, prefer
  a `0.875rem` (14 px) bump and reduce horizontal padding to preserve the
  pill shape.
- Acceptance bar:
  - `report.json` per-variant `text-below-readable-floor` count = **0** for
    the surface on all three mobile viewports.
  - Vitest assertion in the component's test file: every visible text node
    has `parseFloat(getComputedStyle(node).fontSize) >= 12`.

---

## 5. `animation-mount-missing`

**Definition.** A scenario probe (e.g. dice settle, win confetti, loss
shake) expects an animated element to be visible in the DOM before its
trigger fires, but the element is conditionally rendered and only mounts
on settle — so `locator.isVisible()` returns `false` and the harness emits
`{spec}-target-missing`. Even when mounted, the harness may emit
`{spec}-no-motion` if the `data-state` snapshot doesn't actually change.

**Detection heuristic.**

- Probe: `audits.mjs` lines 434–502.
  - `{spec.name}-target-missing` — pre-trigger `locator.isVisible()` returned
    false.
  - `{spec.name}-snapshot-failed` — `snapshotMotionState` threw.
  - `{spec.name}-trigger-failed` — the scenario trigger itself failed.
  - `{spec.name}-observation-failed` — post-trigger snapshot threw.
  - `{spec.name}-no-motion` — pre/post snapshots are bit-identical.
- Scenario contract: the testid is **always** in DOM, and the visible
  state is communicated via `data-state` + `opacity` + `left` (or rotation,
  translate, etc., depending on the spec).

**Severity.** MED — the game-loop still resolves, but the user gets no
visual settle feedback, which is the difference between "I won, where's my
confetti?" and "I won! 🎉".

**Fix template.**

- File pattern: component for the animated target (e.g.
  `apps/web/src/components/DiceSlider.tsx`).
- Always mount the element with a sentinel `data-state="idle"`, transitioning
  to `data-state="settled"` post-event. Use CSS transitions on `opacity`
  and `transform`/`left` keyed off `data-state`. Lock the duration to a
  named constant (e.g. `DICE_RESULT_ANIMATION_MS=350ms`) so the QA snapshot
  window is deterministic. Keep `aria-hidden="true"` pre-settle to avoid
  AT leak.
- Acceptance bar:
  - Vitest: assert idle render mounts the testid with `data-state="idle"`,
    `opacity:0`; assert settled render flips both. Reduced-motion variants
    skip the transition but still set `data-state="settled"`.
  - Playwright `e2e/<game>.connected.spec.ts` asserts pre-trigger
    `data-state=idle, data-result-value=""` then post-`dispatchSettle`
    `data-state=settled, data-result-value=N, data-result-won=true|false`.
  - `report.json` per-variant `*-target-missing` count = **0**.

---

## 6. `focus-ring-invisible`

**Definition.** An interactive element has no theme-aware `:focus-visible`
style and falls back to the Chromium UA outline (`auto 1px rgb(16, 16, 16)`),
which is invisible against `--bb-bg-dark`. Indistinguishable focus state on
dark theme.

**Detection heuristic.**

- Today: surfaced manually by `bb_keyboard_nav_audit_2026-05-09.md` D1, which
  probes via Playwright `getComputedStyle(el).outline` after `.focus()`.
- Proposed harness probe (per
  `BB_QA_HARNESS_DIAGNOSTICS_HARDENING` follow-up): walk every focusable
  element matching `:where(button, a[href], [role=button], [tabindex='0'])`,
  call `.focus()`, read `outlineColor`, fail if
  `rgba(0, 0, 0, 0)` **or** if the colour's WCAG contrast against the
  computed `background-color` of the element/ancestor < 3:1 in the active
  theme.
- Cause-code: `focus-ring-invisible`. Themes: dark + light, both audited.

**Severity.** HIGH — keyboard users on dark theme literally cannot tell
where focus is, which fails UX_PLAN §7 ("Color contrast ≥AA in both themes"
and "visible focus rings").

**Fix template.**

- File pattern: `apps/web/src/app/globals.css` — add a single global
  `:focus-visible` rule painting a 2 px `var(--bb-brand-gold)` outline with
  2 px offset on `:where(button, a[href], [role=button], [tabindex='0'])`,
  plus a 1 px ink inner-ring for AA contrast on gold CTAs. The dice slider
  already does this (`globals.css:253–263`) — generalise the pattern.
- Acceptance bar:
  - Vitest: for every `data-testid$="-primary-cta"`,
    `getComputedStyle(el).outlineColor !== "rgba(0, 0, 0, 0)"` after
    `.focus()` in **both** themes.
  - Playwright kbnav harness rerun: every surface scores ≥4/5 on both
    themes for axis 7 (UX_PLAN §7).
  - `report.json` per-variant `focus-ring-invisible` count = **0** in both
    themes.

---

## 7. `tab-order-skip`

**Definition.** Either (a) Tab order on a surface is not linear — focus
visibly jumps backward or skips a logically-grouped region — or (b) a modal
(`role=dialog` + `aria-modal=true`) allows Tab to escape into the page
beneath. Includes the `focus-trap-missing` sub-case.

**Detection heuristic.**

- Today: surfaced manually by `bb_keyboard_nav_audit_2026-05-09.md` D2 for
  `WalletSheet` (no focus trap; Esc handler works but Tab escapes).
- Proposed harness probe: replay 30 Tab presses, record the active element
  per step, assert (a) `clientRect.top` increases monotonically within a
  region and (b) when a `role=dialog[aria-modal=true]` is open, the cycle
  of focused elements stays inside it (`dialog.contains(active) === true`
  for all steps).
- Cause-codes: `tab-order-skip`, `focus-trap-missing`.

**Severity.** MED — keyboard users can still complete the flow with effort
on the game surfaces; HIGH for modals (Esc-close mitigates but doesn't
eliminate the bug).

**Fix template.**

- For order: rely on DOM order — do not use `tabindex > 0`. If a panel is
  intentionally focus-late (e.g. a result region), set `tabindex="-1"` and
  call `.focus()` from the settle handler instead.
- For trap: in `WalletSheet`, on open `useEffect`: query
  `dialog.querySelectorAll(":where(button, a[href], [tabindex='0'])"))`,
  focus the first, and on `Tab`/`Shift+Tab` from the last/first element
  loop to the other end. Esc handler at `WalletSheet.tsx:290` already exists
  — extend the same hook.
- Acceptance bar:
  - Playwright kbnav harness rerun emits **zero** `tab-order-skip` and
    **zero** `focus-trap-missing` findings.
  - Vitest unit test for `<WalletSheet>` opens the sheet, fires synthetic
    Tab events, asserts focused element ∈ sheet's descendants for the full
    cycle (use `@testing-library/user-event` `tab()`).

---

## 8. `harness-instrumentation-gap`

**Definition.** A QA finding is emitted with insufficient instrumentation to
triage without re-running: missing `causeCode`, missing `selector`, missing
measured dimensions, missing per-variant attribution, or a `report.md` row
that aggregates "horizontal overflow flagged in ~30 variants" without
listing them. The finding cannot be class-coded by any of classes 1–7.

**Detection heuristic.**

- Meta-audit on `report.json` itself, performed by
  `BB_QA_HARNESS_DIAGNOSTICS_HARDENING`:
  - Every finding has `causeCode ∈ {...known set...}`.
  - Every finding has `selector` (or `route` for infra/document-level).
  - Every UX/layout finding has measured dimensions where applicable.
  - Every finding has a per-variant key so `report.mjs` can render an
    indented bullet under the variant.
- Cause-code: `harness-instrumentation-gap`. Emitted by the meta-audit, not
  by surface audits.

**Severity.** LOW — no user-visible defect, but every instance forces the
triager to re-run the harness or fall back to dev-tools, which is the exact
slowdown this taxonomy exists to prevent.

**Fix template.**

- File pattern: `apps/web/scripts/qa/audits.mjs` for the offending probe
  (or `report.mjs` for the renderer). Add the missing field to the
  `findings.push({...})` call site; update `buildSelectorForElement` if the
  gap is "selector blank for this DOM shape".
- Acceptance bar:
  - Fixture test in `qa-audit-selector.test.ts` (or sibling) covers the
    previously-blind DOM shape with at least one fixture row.
  - `report.json` per-variant `harness-instrumentation-gap` count = **0**
    on the next QA run.
  - Cross-check: every cause-code in `report.json` belongs to the set
    enumerated in this taxonomy. Add a new class (with detection + fix
    template) if a novel code appears.

---

## Cross-reference back to open BB items

| Open item (QUEUE.md line) | Primary class(es) | Notes |
|---|---|---|
| `BB_QA_DICE_SETTLE_ANIMATION_RESTORE` (231, shipped) | 5 `animation-mount-missing` | Class kept as regression contract; testid mount + `data-state` flip is the pattern. |
| `BB_QA_WALLET_LIGHT_THEME_HYDRATION_FIX` (233, shipped) | 3 `light-theme-hydration` | SSR-stable default + mount-effect resolve pattern. |
| `BB_QA_TRUST_STRIP_LEGIBILITY_PASS` (shipped) | 4 `legibility-floor-12px` | TrustStrip / footer copy bump to 0.8125rem. |
| `BB_QA_MOBILE_TOUCH_TARGET_FLOOR` (229, shipped) | 2 `touch-target-floor` | `.bb-hit-target-44` + `--inline` utilities; library-internal override pattern. |
| `BB_PHASE3_KBNAV_FOCUS_RING_FIX` (kbnav D1, shipped) | 6 `focus-ring-invisible` | Global `:focus-visible` rule in `globals.css`. |
| `BB_QA_HARNESS_DIAGNOSTICS_HARDENING` (692 anchor, shipped) | 8 `harness-instrumentation-gap` | Should emit cause-codes from this taxonomy; meta-audit asserts the set. |
| `BB_QA_DEFECT_CLASS_TAXONOMY` (692) | — | This document. |
| `BB_PHASE3_VISUAL_REGRESSION_BASELINE_EARLY_SLICE` (693) | (none — locks pixels, not classes) | Baseline freeze precedes class-by-class fixes so each PR is measured against frozen ground-truth. |
| `BB_QA_CLOSEOUT_BURNDOWN` (697) | — | Burndown doc cites this taxonomy as the per-class acceptance contract. |
| Follow-up `tab-order-skip` work (kbnav D2 — WalletSheet focus trap) | 7 `tab-order-skip` | Not yet ticketed; class definition pre-stages the harness probe + fix template so the future PR is a one-off application. |

## Lifecycle rules

1. **Adding a class.** Any novel `causeCode` the harness emits that does not
   map to classes 1–8 must be promoted to a new class with detection +
   severity + fix template + cross-reference in the same PR that adds the
   probe. The meta-audit (class 8) is the gate.
2. **Retiring a class.** A class is retired only when its acceptance bar has
   held green across **three** consecutive weekly QA runs and the underlying
   probe has been demoted to a `tier-2` slow-path. The class definition
   stays in this file with a `RETIRED YYYY-MM-DD` header.
3. **Severity mutation.** Severity is project-policy, not per-PR. Mutate it
   here, then re-triage open items against the new policy.

_End of taxonomy — 8 classes, each with detection + severity + fix template
+ cross-reference. Re-emit `causeCode` from this set in the next QA run._
