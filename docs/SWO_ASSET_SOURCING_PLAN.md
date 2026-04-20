# SWO Asset Sourcing Plan

> Defines how Star World Order sources, processes, and deploys pixel-art assets
> so the final product feels like one consistent star-themed pixel-art game.
> Source inventory: `docs/SWO_PIXEL_ART_INVENTORY.md`

---

## 1. House Style Definition

### Mood & Theme
**Dark cosmic sanctuary** — the player exists inside a mystical machine-temple drifting through space. Think: abandoned space cathedral, occult circuitry, starfield-lit stone corridors. Not grimdark horror — more reverent and ancient. Gold accents on deep purple/blue foundations.

### Master Palette (24 colors)

| Role | Colors | Hex Range |
|------|--------|-----------|
| **Deep base** | Void black, cosmic navy | `#0a0a12`, `#0d1b2a` |
| **Mid tones** | Astral purple, nebula blue, dark teal | `#2d1b69`, `#1b2d5e`, `#1a3a3a` |
| **Accents** | Star gold, ritual amber, blood garnet | `#d4a017`, `#c47f17`, `#8b1a1a` |
| **Mystical glow** | Arcane violet, plasma cyan, ghost green | `#9b59b6`, `#00d4ff`, `#39ff8e` |
| **Neutrals** | Ash grey, dust brown, bone white | `#4a4a5e`, `#3d2b1f`, `#d4c5a9` |
| **Highlights** | Pure white (sparingly), hot pink (rare) | `#ffffff`, `#ff2d7b` |

All sourced assets get palette-mapped to these 24 colors before integration. This is the single most important cohesion rule.

### Outline Treatment
**Dark outlines (1px, `#0a0a12`)** on all sprites. This matches the majority of dark-fantasy packs (Dungeon Crawl, Evil Dungeon, NightBorne, Necromancer). Assets from bright packs (Kenney, Anokolisa) need outline addition during post-processing.

### Animation Style
- **Companions**: 4-8 frame idle loops, 60ms/frame. Subtle breathing/floating preferred over static.
- **Effects/VFX**: 6-12 frames, 40-80ms/frame. Cosmic effects should have a slow-pulse quality.
- **Environment**: Ambient animations only (torches, water, particles). No environment should feel "busy."
- **UI**: No animation on UI chrome. Transitions handled by CSS, not sprite sheets.

### Composition Rules
- **Negative space matters**: Dark backgrounds are a feature, not emptiness. Never fill every tile.
- **Light sources are focal points**: Every scene should have 1-2 glow sources (torches, crystals, portals, stars).
- **Vertical hierarchy**: Important elements glow brighter. Background elements are desaturated.
- **No pixel-art mixing with vector/HD art**: Everything visible in the Sanctuary must be pixel-art. Non-pixel UI elements (buttons, text) use the Press Start 2P font to bridge the gap.

---

## 2. Pixel Size Standards

| Context | Canonical Size | Display Size | Notes |
|---------|---------------|-------------|-------|
| **Map tiles** | 32x32 | 32-64px CSS | World map grid base |
| **Companion sprites** | 64x64 | 64-128px CSS | Main companion display in panels |
| **Companion portraits** | 128x128 | 128px CSS | Detail views, chat avatars |
| **Environment props** | 32x32 | 32-64px CSS | Torches, chests, altars, decorations |
| **Icons (items/badges)** | 32x32 | 32-48px CSS | Inventory, quest badges, shop items |
| **UI ornaments** | 16x16 | 16-32px CSS | Borders, dividers, small decorations |
| **Backgrounds** | 576x324+ | Full viewport | Parallax layers, scaled with `image-rendering: pixelated` |
| **Effects/VFX** | 64x64 | 64-128px CSS | Spell effects, particles, transitions |
| **Empty states** | 128x128 | 128-256px CSS | "No companions yet" illustrations |

**Scaling rule**: Always scale by integer multiples (2x, 3x, 4x). Never fractional scale pixel art. Use CSS `image-rendering: pixelated` / `crisp-edges` everywhere.

---

## 3. Sourcing Plan by Category

### 3.1 Companions

**The most visible asset class. Must feel unique and characterful.**

| Role | Primary Source | Why | Processing |
|------|---------------|-----|------------|
| **Generic companion base sprites** | #1 Dungeon Crawl (CC0, 32x32, 6000+) | Largest CC0 creature library. Dark fantasy native. | Upscale 2x to 64x64, palette-map |
| **Elite/rare companions** | #3 NightBorne + #4 Necromancer (NYP, 80-128px) | High-quality animated characters with dark glow effects | Resize to 64x64 standard, palette-map |
| **Monster-type companions** | #2 50+ Monsters Pack (CC0, 64x64) | Already at target size, dark 4-color palette per monster | Palette-map only |
| **Named/unique companions** | **Custom pixel art** | Named companions (lore-significant) must be original | Commission or generate per character |
| **Animated companion idles** | #7 LuizMelo Creatures (CC0) | Full idle/attack/death animation sets | Palette-map, crop to 64x64 |

**Style constraint for companions**: Every companion must have visible eyes or a glowing element so it reads as "alive" at 64px. Silhouette must be distinct — no two companions should have the same outline shape.

**Do NOT use for companions**: #6 RPG Monster Sprites (128x128 is oversized for the role, CraftPix RF license less flexible than CC0 alternatives), #32 Kenney Roguelike (too bright/cute, style clash).

### 3.2 World Map & Backgrounds

**Sets the entire mood. This is where cosmic + dark fantasy merge.**

| Layer | Primary Source | Why | Processing |
|-------|---------------|-----|------------|
| **Starfield backdrop** | #15 Stars Parallax (CC0, 2560x2560) | Transparent star layers over CSS dark gradient. Perfect parallax base. | Tint to palette blues/purples |
| **Cosmic background** | #14 Planets in Space (RF, 576x324) | 4 parallax cosmic BGs. Direct theme match. | Use as-is or light palette adjustment |
| **Map terrain tiles** | #28 Puny World (CC0, 16x16) | Complete overworld tileset, CC0. | Upscale 2x to 32x32, dark palette-map |
| **Map decoration** | #13 Level Map Pack (RF, 32x32) | Crystals, lava, fog, shadows — cosmic terrain features | Palette-map to master palette |
| **Gothic structures** | #10 Gothicvania Cold Corridors (NYP) | Dark parallax corridors for sanctuary interior zones | Use for sanctuary sub-areas |

**Backbone strategy**: Stars Parallax (#15) as the ever-present base layer. Planets in Space (#14) for zone-specific cosmic backdrops. Puny World (#28) recolored dark for navigable terrain. This three-layer stack (stars + cosmic + terrain) creates the SWO look.

### 3.3 Environment Tiles & Props

**Interior sanctuary spaces, dungeon-like areas, ritual chambers.**

| Use Case | Primary Source | Backup | Processing |
|----------|---------------|--------|------------|
| **Sanctuary rooms** | #8 Evil Dungeon (CC-BY 4.0) | #12 CraftPix Dungeon | Palette-map. Attribution required for #8. |
| **Gothic details** | #9 Undead Tileset (RF, 16x16) | #11 Ansimuz Legacy (CC0) | Upscale 2x, palette-map |
| **Animated props** (torches, traps, water) | #12 2D Top-Down Dungeon (RF) | #8 Evil Dungeon | Palette-map |
| **Ritual/occult decorations** | #8 Evil Dungeon pentagrams + altars | #34 Dark Fantasy Scenery (CC0) | Direct use, palette-map |
| **Cosmic environment** | #33 Cosmic Lilac (NYP, 16x16) | #13 Level Map Pack | Lilac palette already close to SWO; minor adjustment |

**Core backbone**: Evil Dungeon (#8) + Undead Tileset (#9) form the sanctuary interior style. Cosmic Lilac (#33) bridges dungeon and space aesthetics.

### 3.4 UI Ornaments & Chrome

**Frames, panels, buttons, borders for Sanctuary UI.**

| Element | Primary Source | Why | Processing |
|---------|---------------|-----|------------|
| **UI structural kit** | #21 Kenney Pixel UI (CC0, 750 elements) | Best coverage: panels, buttons, sliders, frames. CC0 = unlimited modification. | Full dark palette recolor — replace all brights with palette golds/purples |
| **RPG-flavored UI** | #20 CraftPix Basic UI (RF) | Shop, inventory, crafting panels pre-built | Dark recolor |
| **Decorative borders** | Custom / #22 Magic Icons | Crystal/gem decorative accents for panel corners | Palette-map |

**Key decision**: Kenney (#21) as structural foundation (it has the most complete set of UI primitives), then skin it dark. CraftPix (#20) for RPG-specific layouts (shop grid, inventory slots). Never use Kenney's default bright colors.

### 3.5 Quest Badges & Item Icons

| Use Case | Primary Source | Backup | Processing |
|----------|---------------|--------|------------|
| **General RPG icons** (weapons, potions, gear) | #18 496 RPG Icons (CC0, 34x34) | #31 Anokolisa 50+ weapons | Resize to 32x32, palette-map |
| **Cosmic/sci-fi badges** | #19 20 Sci-Fi Icons (NYP, 128x128) | Custom | Downscale to 32x32 for badges, 64x64 for quest headers |
| **Magic item icons** | #22 Magic Pixel Art (CC-BY 3.0, 16x16) | #1 Dungeon Crawl item sprites | Upscale 2x, palette-map |
| **SWO-specific badges** (faction, seasonal, achievement) | **Custom pixel art** | — | Must be original — these are identity assets |

### 3.6 Shop Items & Collectibles

| Item Type | Source Strategy |
|-----------|----------------|
| **Consumables** (potions, scrolls) | #18 RPG Icons + #1 Dungeon Crawl item sprites |
| **Equipment** (weapons, armor) | #18 RPG Icons (most complete set) |
| **Cosmic artifacts** | #19 Sci-Fi Icons + custom |
| **Decorative items** (sanctuary furniture) | #8 Evil Dungeon props + #9 Undead Tileset objects |
| **Currency/tokens** | **Custom only** — $SWO token icon must be original |

### 3.7 Effects & VFX

| Effect Type | Primary Source | Processing |
|-------------|---------------|------------|
| **Spell/ability effects** | #23 Pixel Art Spells (CC0, B&W) | Tint to cosmic purple (#9b59b6) or plasma cyan (#00d4ff) |
| **Dark combat VFX** | #24 Gothicvania Magic (NYP) | Dark Bolt + Lightning already fit. Minor palette tweak. |
| **Energy/star bursts** | #25 Pixel Effects Pack (CC-BY 4.0) | Palette-map to glow colors |
| **Ambient particles** | #26 Particle Pack (CC0) | Tint to star gold for ambient, violet for magic zones |
| **Portal/transition** | #27 Magic Mirror/Portal (CC0) | Good for zone transitions, summon animations |

**Color rule for effects**: All VFX use only the "Mystical glow" and "Highlights" rows from the master palette. Effects should never introduce colors outside the 24-color palette.

### 3.8 Empty States & Illustrations

| Context | Strategy |
|---------|----------|
| "No companions yet" | Custom 128x128 illustration: lone star in void, text below |
| "Quest log empty" | Custom 128x128: closed book with star emblem |
| "Shop coming soon" | Custom 128x128: shuttered cosmic storefront |
| Loading/skeleton states | Shimmer effect over dark panels (CSS, not pixel art) |

Empty states are brand touchpoints — always custom. They're small (one 128x128 sprite each) and define first impressions.

---

## 4. Backbone vs. Supplemental Sources

### Backbone (define the visual DNA)

These packs set the house style. All other assets must match their feel.

| Pack | Role | Why Backbone |
|------|------|-------------|
| **#1 Dungeon Crawl 32x32** | Creature + item library | CC0, 6000+ sprites, dark fantasy native. Largest single coherent set. |
| **#8 Evil Dungeon** | Sanctuary interior style | Pentagrams, demons, traps — defines the ritual-space aesthetic |
| **#15 Stars Parallax** | Cosmic backdrop | Every screen's background starts here |
| **#14 Planets in Space** | Cosmic environment | Zone-specific cosmic atmosphere |
| **#21 Kenney Pixel UI** | UI structural foundation | 750 elements, CC0, most complete primitive set |

If an asset from a supplemental pack clashes with these five backbone sources, the supplemental asset loses.

### Supplemental (fill gaps, add variety)

| Pack | Best For | Limitation |
|------|----------|-----------|
| #2 50+ Monsters | Additional companion variety | Limited to 112 sprites |
| #3 NightBorne | Elite companion showcase | Single character, NYP license |
| #4 Necromancer | Mystical NPC archetype | Single character, NYP license |
| #9 Undead Tileset | Gothic ground details | 16x16 needs upscaling |
| #10 Gothicvania Corridors | Sanctuary sub-zones | Specific use case only |
| #13 Level Map Pack | Map decorations | Needs palette work |
| #18 496 RPG Icons | Item icon library | 34x34 non-standard, needs resize |
| #19 Sci-Fi Icons | Cosmic badge/quest icons | Only 20 icons |
| #20 CraftPix UI | RPG UI layouts | Needs dark recolor |
| #23 Pixel Art Spells | VFX library | B&W, needs tinting |
| #28 Puny World | Overworld terrain | 16x16, needs dark recolor |
| #33 Cosmic Lilac | Space-dungeon bridge | Small set (87 tiles) |

---

## 5. Assets That Don't Fit SWO

These are technically usable but would break aesthetic coherence:

| Pack | Problem | Verdict |
|------|---------|---------|
| **#21 Kenney UI** (default colors) | Bright, cheerful, rounded — looks like a casual mobile game | Use structure only, full recolor mandatory |
| **#32 Kenney Roguelike** (1700 tiles) | Flat, bright, cartoony. No amount of recoloring fixes the silhouette style. | Skip for visible assets. Minimap/debug only. |
| **#29 RPG Town** | FF6-style bright town. Too cheerful even recolored. | Skip unless heavily modified |
| **#30 Overworld Tileset** | Classic bright-green RPG overworld. Wrong mood entirely. | Skip |
| **#36 Freepik** | Mixed quality, attribution friction, inconsistent style | Skip |
| **#39 Tiny Creatures** | Kenney-compatible bright style, 16x16 too small | Skip |
| **#31 Anokolisa** (characters) | Heroes are bright/colorful anime-adjacent style | Use dungeon tilesets only, skip characters |

---

## 6. Sourced vs. Custom vs. Claude Design

### Decision Matrix

| Criterion | Use Sourced Packs | Use Custom Pixel Art | Use Claude Design |
|-----------|-------------------|---------------------|-------------------|
| **Identity/branding** | Never | Always | Layouts only |
| **Named characters** | Never | Always | Reference mockups |
| **Generic creatures** | Yes (palette-mapped) | Only if no fit | No |
| **Environment tiles** | Yes (backbone packs) | Gap-fill only | No |
| **UI structure** | Yes (Kenney recolored) | Decorative accents | Page layouts, flows |
| **Icons (standard RPG)** | Yes (#18 icons) | Only SWO-specific | No |
| **Backgrounds** | Yes (#14, #15) | Only unique zones | No |
| **Effects/VFX** | Yes (recolored) | Signature moves only | No |
| **Empty states** | Never | Always | Composition drafts |
| **Token/currency icons** | Never | Always | No |
| **Page layouts** | No | No | Yes — wireframes + component placement |
| **Color/mood exploration** | No | No | Yes — palette studies, mood boards |

### When Claude Design adds value
Claude Design generates layouts, wireframes, and component compositions — not pixel art. Use it for:
- **Page structure**: Where does the companion panel sit? How wide is the sidebar? What's the scroll behavior?
- **Responsive breakpoints**: Mobile vs. desktop sanctuary layout
- **Interaction flows**: What happens when you click a companion? State diagrams.
- **Color distribution mockups**: How much gold vs. purple on a given screen?

Never ask Claude Design to produce final pixel-art sprites. It produces reference compositions that guide where sourced/custom pixel art gets placed.

---

## 7. Post-Processing Pipeline

Every sourced asset goes through this pipeline before integration:

```
1. RESIZE     → Scale to canonical size (integer multiple)
2. PALETTE    → Map all colors to the 24-color master palette
3. OUTLINE    → Add/normalize 1px dark outline (#0a0a12)
4. ALPHA      → Clean up transparency (no semi-transparent pixels)
5. NAMING     → Rename to SWO convention: {category}_{name}_{size}_{frame}.png
6. MANIFEST   → Add entry to asset_manifest.json (source, license, attribution)
7. REVIEW     → Visual QA: does it look like it belongs next to backbone assets?
```

**Tooling recommendation**: A Python script using Pillow for steps 1-4, producing output in `public/assets/pixel/` with a generated manifest. This script should be in the SWO repo so any contributor can re-process assets.

---

## 8. Attribution Manifest

Assets with attribution requirements:

| Pack | License | Attribution Required |
|------|---------|---------------------|
| #8 Evil Dungeon | CC-BY 4.0 | Yes — credit author in credits page |
| #18 496 RPG Icons (if CC-BY) | CC0 | No |
| #22 Magic Pixel Art | CC-BY 3.0 | Yes |
| #25 Pixel Effects Pack | CC-BY 4.0 | Yes |
| #30 Overworld Tileset | CC-BY 3.0 | Yes (if used) |

**Implementation**: Add a `/credits` page to SWO listing all attributed sources. Also maintain `public/assets/ATTRIBUTION.md` in the repo.

---

## 9. Priority Implementation Order

| Phase | Assets to Source | Enables |
|-------|-----------------|---------|
| **Phase 1: Core visuals** | Stars Parallax (#15) + Planets (#14) backgrounds, Dungeon Crawl (#1) companion sprites, Evil Dungeon (#8) sanctuary tiles | Sanctuary looks like a real game instead of placeholder UI |
| **Phase 2: UI skin** | Kenney UI (#21) recolored dark, 496 RPG Icons (#18) | Shop, inventory, quest log have proper pixel UI |
| **Phase 3: Effects & polish** | Pixel Spells (#23), Gothicvania Magic (#24), Particle Pack (#26) | Companion abilities, ambient atmosphere |
| **Phase 4: World map** | Puny World (#28) recolored, Level Map (#13), Cosmic Lilac (#33) | Explorable world map with cosmic terrain |
| **Phase 5: Custom originals** | Named companions, SWO token icon, faction emblems, empty states | Brand identity layer on top of sourced foundation |

---

## 10. Budget Considerations

| Source Type | Cost | Volume |
|-------------|------|--------|
| CC0 packs (OpenGameArt, Kenney) | Free | ~9000+ sprites |
| RF packs (CraftPix) | Free (freebie tier) | ~200 sprites |
| NYP packs (itch.io) | $0 minimum, tip optional | ~300 sprites |
| Custom pixel art (commission) | $5-50 per sprite | As needed |
| Custom pixel art (AI-assisted) | Time only | As needed |

Total sourced library: ~9500 sprites at $0 cost. Custom work needed for ~20-30 identity-critical sprites.

---

*Document: `docs/SWO_ASSET_SOURCING_PLAN.md` — Created 2026-04-20*
*Source inventory: `docs/SWO_PIXEL_ART_INVENTORY.md`*
*Project tracker: `memory/evolution/SWO_TRACKER.md`*
