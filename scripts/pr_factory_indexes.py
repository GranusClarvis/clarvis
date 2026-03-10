"""PR Factory Phase 2 — Precision Index Builders — DEPRECATED wrapper.

Canonical module: clarvis.orch.pr_indexes
This file delegates to the spine module for backward compatibility.

Usage (new):
    from clarvis.orch.pr_indexes import refresh_indexes
Usage (legacy, still works):
    from pr_factory_indexes import refresh_indexes
"""
import warnings as _w
_w.warn("pr_factory_indexes is deprecated; use clarvis.orch.pr_indexes", DeprecationWarning, stacklevel=2)

from clarvis.orch.pr_indexes import (  # noqa: F401
    build_file_index,
    build_symbol_index,
    build_route_index,
    build_config_index,
    build_test_index,
    refresh_indexes,
    load_all_indexes,
    format_indexes_for_prompt,
    is_stale,
    SKIP_DIRS,
    SOURCE_EXTS,
    MAX_FILES,
    # Private but used by tests
    _infer_source_module,
    _auto_tag,
    _parse_python_symbols,
    _parse_js_symbols,
    _parse_go_symbols,
    _parse_rust_symbols,
)

__all__ = [
    "build_file_index",
    "build_symbol_index",
    "build_route_index",
    "build_config_index",
    "build_test_index",
    "refresh_indexes",
    "load_all_indexes",
    "format_indexes_for_prompt",
    "is_stale",
    "SKIP_DIRS",
    "SOURCE_EXTS",
    "MAX_FILES",
]

if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    if len(sys.argv) < 3:
        print("Usage: pr_factory_indexes.py <agent_dir> <workspace>")
        sys.exit(1)
    agent_dir = Path(sys.argv[1])
    workspace = Path(sys.argv[2])
    report = refresh_indexes(agent_dir, workspace)
    print(json.dumps(report, indent=2))
