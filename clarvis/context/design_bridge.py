#!/usr/bin/env python3
"""Design bridge — generates handoff packs for Claude Design and processes exports back.

Gives Clarvis an operational path to Claude Design by producing structured prompts,
brand tokens, and component specs that an operator pastes into a Design session.
Also processes Design export bundles (HTML/ZIP) into implementation-ready specs.

CLI (via scripts/tools/design_bridge.py):
    design_bridge.py pack --project swo --task "redesign sanctuary page"
    design_bridge.py decide --task "create a new dashboard widget"
    design_bridge.py ingest --export /path/to/design_export.html --project swo
    design_bridge.py projects
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", str(Path(__file__).resolve().parents[2]))
DESIGN_DATA = Path(WORKSPACE) / "data" / "design_bridge"
PROFILES_DIR = DESIGN_DATA / "profiles"
EXPORTS_DIR = DESIGN_DATA / "exports"

# ---------------------------------------------------------------------------
# Project profiles — design tokens + conventions per managed project
# ---------------------------------------------------------------------------

_BUILTIN_PROFILES = {
    "swo": {
        "name": "Star World Order",
        "repo": "InverseAltruism/Star-World-Order",
        "stack": "Next.js 16, React 19, TypeScript, Tailwind CSS, Framer Motion, Supabase, Monad blockchain",
        "palette": {
            "background": "#0a0a1a",
            "surface": "#1a1a2e",
            "gold": "#ffd700",
            "purple": "#9966ff",
            "blue": "#4488ff",
            "green": "#3fb950",
            "text": "#e0e0e0",
            "muted": "#888888",
        },
        "typography": {
            "display": "Press Start 2P (pixel font, headers only)",
            "body": "JetBrains Mono (monospace, body text and UI)",
            "sizes": "Display: 1.5-2rem, Body: 0.875-1rem, Small: 0.75rem",
        },
        "motifs": [
            "Pixel corner markers on cards/panels",
            "Gold glow effects (box-shadow: 0 0 20px rgba(255,215,0,0.3))",
            "Subtle CRT scanline overlay (optional, on hero sections)",
            "Retro pixel borders (2px solid with corner notches)",
            "Dark glassmorphism panels (backdrop-blur: 12px)",
            "Star/constellation decorative elements",
        ],
        "component_patterns": [
            "Card-based layouts with pixel borders",
            "Gradient accent bars (gold → purple)",
            "Animated counters for stats/metrics",
            "Wallet-connected state indicators",
            "Loading: pixel-art spinner or pulsing gold dots",
        ],
        "constraints": [
            "Mobile-first responsive (320px min)",
            "Dark mode only (no light mode)",
            "Wallet auth via RainbowKit/wagmi",
            "All animations respect prefers-reduced-motion",
            "Pixel font ONLY for headers/labels, never body text",
        ],
    },
    "clarvis": {
        "name": "Clarvis Dashboard",
        "repo": "GranusClarvis/clarvis",
        "stack": "PixiJS (canvas), Python backend, SSE streaming, systemd",
        "palette": {
            "background": "#0a0e14",
            "surface": "#131a24",
            "accent_blue": "#58a6ff",
            "accent_purple": "#bc8cff",
            "accent_green": "#3fb950",
            "text": "#e6edf3",
            "muted": "#7d8590",
        },
        "typography": {
            "display": "SF Pro Display or system sans-serif",
            "body": "SF Mono / Fira Code (all metrics, data)",
            "sizes": "Compact: information-dense, small font preferred",
        },
        "motifs": [
            "Information-dense panels (think IDE/terminal)",
            "Minimal chrome, maximum data",
            "Subtle pulse animations for live data",
            "Graph/node visualizations for brain connections",
            "Status indicators: colored dots (green/yellow/red)",
        ],
        "component_patterns": [
            "Metric cards with sparkline graphs",
            "Real-time SSE-driven counters",
            "Collapsible sections for nested data",
            "Terminal-style log viewers",
        ],
        "constraints": [
            "Canvas-based (PixiJS), not DOM",
            "Must run on 1920x1080 dashboard display",
            "No external CDN dependencies",
            "Performance: 60fps target, <16ms frame budget",
        ],
    },
}


def _ensure_dirs():
    DESIGN_DATA.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(exist_ok=True)
    EXPORTS_DIR.mkdir(exist_ok=True)


def get_profile(project: str) -> dict:
    """Load project design profile (builtin or custom)."""
    if project in _BUILTIN_PROFILES:
        return _BUILTIN_PROFILES[project]
    custom = PROFILES_DIR / f"{project}.json"
    if custom.exists():
        return json.loads(custom.read_text())
    return {}


def list_projects() -> list[str]:
    """List available project profiles."""
    projects = list(_BUILTIN_PROFILES.keys())
    if PROFILES_DIR.exists():
        for f in PROFILES_DIR.glob("*.json"):
            name = f.stem
            if name not in projects:
                projects.append(name)
    return sorted(projects)


# ---------------------------------------------------------------------------
# Design decision framework
# ---------------------------------------------------------------------------

def decide(task: str) -> dict:
    """Recommend which tool to use for a design/UI task."""
    task_lower = task.lower()

    # Keywords that push toward Claude Design
    design_keywords = [
        "explore", "mockup", "wireframe", "prototype", "layout options",
        "design system", "visual direction", "pitch deck", "presentation",
        "brand", "redesign", "ui concept", "look and feel",
    ]
    # Keywords that push toward code-first
    code_keywords = [
        "implement", "fix", "bug", "refactor", "add button", "endpoint",
        "api", "backend", "script", "test", "ci", "deploy", "migration",
        "dashboard widget", "existing component",
    ]
    # Keywords for pixel art
    pixel_keywords = [
        "pixel art", "sprite", "nft art", "game asset", "tilemap",
        "animation frames", "character design",
    ]

    design_score = sum(1 for kw in design_keywords if kw in task_lower)
    code_score = sum(1 for kw in code_keywords if kw in task_lower)
    pixel_score = sum(1 for kw in pixel_keywords if kw in task_lower)

    if pixel_score > 0 and pixel_score >= design_score:
        recommendation = "pixel_art_tool"
        reason = "Task involves pixel-art assets — use Aseprite/Piskel for final art. Claude Design can explore concepts first."
    elif design_score > code_score:
        recommendation = "claude_design"
        reason = "Task is exploratory/visual — use Claude Design for iteration, then handoff to Claude Code for implementation."
    elif code_score > 0:
        recommendation = "code_first"
        reason = "Task is implementation-focused — proceed directly with Claude Code."
    else:
        recommendation = "claude_design"
        reason = "Ambiguous task — default to Claude Design for visual exploration when there's a UI component."

    return {
        "task": task,
        "recommendation": recommendation,
        "reason": reason,
        "scores": {"design": design_score, "code": code_score, "pixel_art": pixel_score},
    }


# ---------------------------------------------------------------------------
# Handoff pack generation
# ---------------------------------------------------------------------------

def generate_pack(project: str, task: str, include_tokens: bool = True) -> str:
    """Generate a Claude Design handoff pack — structured prompt for operator to paste."""
    profile = get_profile(project)
    if not profile:
        return f"ERROR: No design profile found for project '{project}'. Available: {list_projects()}"

    sections = []

    # Header
    sections.append(f"# Claude Design Brief — {profile['name']}")
    sections.append(f"**Task:** {task}")
    sections.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
    sections.append(f"**Stack:** {profile['stack']}")
    sections.append("")

    # Design tokens
    if include_tokens:
        sections.append("## Design Tokens")
        sections.append("")
        sections.append("### Color Palette")
        for name, value in profile["palette"].items():
            sections.append(f"- **{name}**: `{value}`")
        sections.append("")
        sections.append("### Typography")
        for key, val in profile["typography"].items():
            sections.append(f"- **{key}**: {val}")
        sections.append("")

    # Visual motifs
    if profile.get("motifs"):
        sections.append("## Visual Motifs")
        for motif in profile["motifs"]:
            sections.append(f"- {motif}")
        sections.append("")

    # Component patterns
    if profile.get("component_patterns"):
        sections.append("## Component Patterns")
        for pat in profile["component_patterns"]:
            sections.append(f"- {pat}")
        sections.append("")

    # Constraints
    if profile.get("constraints"):
        sections.append("## Constraints")
        for c in profile["constraints"]:
            sections.append(f"- {c}")
        sections.append("")

    # Instructions for Claude Design
    sections.append("## Instructions for This Session")
    sections.append("")
    sections.append(dedent(f"""\
        1. Use the color palette and typography above exactly.
        2. Create 2-3 visual directions for: {task}
        3. Each direction should be a full interactive prototype (not just wireframe).
        4. Apply the visual motifs listed above to give it the project's identity.
        5. Respect all constraints listed.
        6. When satisfied, export a **handoff bundle** (Design → Handoff) for implementation.
    """))

    # Footer
    sections.append("---")
    sections.append("_Generated by Clarvis design_bridge. Paste this into a Claude Design session._")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Export ingestion
# ---------------------------------------------------------------------------

def ingest_export(export_path: str, project: str) -> dict:
    """Process a Claude Design export file and create an implementation spec."""
    _ensure_dirs()
    path = Path(export_path)
    if not path.exists():
        return {"error": f"File not found: {export_path}"}

    content = path.read_text(errors="replace")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save a copy
    dest = EXPORTS_DIR / f"{project}_{timestamp}{path.suffix}"
    dest.write_text(content)

    # Extract basic structure info
    result = {
        "project": project,
        "source_file": str(path),
        "saved_to": str(dest),
        "timestamp": timestamp,
        "file_size": len(content),
        "file_type": path.suffix,
    }

    # If HTML, extract key structural elements
    if path.suffix in (".html", ".htm"):
        import re
        # Find component-like class names
        classes = set(re.findall(r'class="([^"]+)"', content))
        # Find color values
        colors = set(re.findall(r'#[0-9a-fA-F]{6}', content))
        # Find font references
        fonts = set(re.findall(r'font-family:\s*([^;}"]+)', content))

        result["extracted"] = {
            "unique_classes": len(classes),
            "colors_used": sorted(colors)[:20],
            "fonts_referenced": sorted(fonts),
            "approx_components": content.count("<section") + content.count("<div class"),
        }

        # Generate implementation notes
        profile = get_profile(project)
        if profile:
            palette_values = set(profile.get("palette", {}).values())
            off_palette = colors - palette_values
            if off_palette:
                result["warnings"] = [
                    f"Colors not in project palette: {sorted(off_palette)[:5]}",
                    "Consider mapping these to palette tokens before implementation.",
                ]

    return result


# ---------------------------------------------------------------------------
# CLI entry point (used by scripts/tools/design_bridge.py)
# ---------------------------------------------------------------------------

def cli_main(args: list[str] | None = None):
    """CLI dispatcher."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print(dedent("""\
            Usage:
              design_bridge.py pack --project <name> --task "description"
              design_bridge.py decide --task "description"
              design_bridge.py ingest --export <path> --project <name>
              design_bridge.py projects
              design_bridge.py profile --project <name>
        """))
        return

    cmd = args[0]

    # Parse flags
    project = ""
    task = ""
    export_path = ""
    i = 1
    while i < len(args):
        if args[i] == "--project" and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        elif args[i] == "--task" and i + 1 < len(args):
            task = args[i + 1]
            i += 2
        elif args[i] == "--export" and i + 1 < len(args):
            export_path = args[i + 1]
            i += 2
        else:
            if not task and cmd in ("pack", "decide"):
                task = args[i]
            i += 1

    if cmd == "pack":
        if not project or not task:
            print("ERROR: --project and --task required", file=sys.stderr)
            sys.exit(1)
        print(generate_pack(project, task))

    elif cmd == "decide":
        if not task:
            print("ERROR: --task required", file=sys.stderr)
            sys.exit(1)
        result = decide(task)
        print(f"Recommendation: {result['recommendation']}")
        print(f"Reason: {result['reason']}")
        print(f"Scores: design={result['scores']['design']}, code={result['scores']['code']}, pixel_art={result['scores']['pixel_art']}")

    elif cmd == "ingest":
        if not export_path or not project:
            print("ERROR: --export and --project required", file=sys.stderr)
            sys.exit(1)
        result = ingest_export(export_path, project)
        print(json.dumps(result, indent=2))

    elif cmd == "projects":
        for p in list_projects():
            profile = get_profile(p)
            print(f"  {p:12s} — {profile.get('name', '?')} ({profile.get('stack', 'unknown')[:50]})")

    elif cmd == "profile":
        if not project:
            print("ERROR: --project required", file=sys.stderr)
            sys.exit(1)
        profile = get_profile(project)
        if profile:
            print(json.dumps(profile, indent=2))
        else:
            print(f"No profile for '{project}'", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
