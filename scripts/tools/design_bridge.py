#!/usr/bin/env python3
"""CLI wrapper for clarvis.context.design_bridge.

Generates handoff packs for Claude Design sessions and processes exports.

Usage:
    python3 design_bridge.py pack --project swo --task "redesign sanctuary page"
    python3 design_bridge.py decide --task "create a new dashboard widget"
    python3 design_bridge.py ingest --export /path/to/export.html --project swo
    python3 design_bridge.py projects
    python3 design_bridge.py profile --project swo
"""

from clarvis.context.design_bridge import cli_main

if __name__ == "__main__":
    cli_main()
