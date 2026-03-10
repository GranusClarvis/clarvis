"""PR Factory Phase 2 — Precision Index Builders.

Generates precision indexes for project agents:
- file_index: all source files with type/hash/tags
- symbol_index: exported classes/functions/types per file
- route_index: HTTP routes from Next.js/Express/Flask/FastAPI
- config_index: configuration files with key settings
- test_index: test files mapped to source modules

Indexes are stored in <agent_dir>/data/indexes/ with staleness tracking.

Usage:
    from clarvis.orch.pr_indexes import refresh_indexes
    report = refresh_indexes(agent_dir, workspace)
"""

import ast
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Constants ──

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".nuxt", "dist", "build",
    ".cache", ".turbo", "coverage", ".pytest_cache", "venv", ".venv", "env",
    "target", ".svelte-kit", ".output",
}

SOURCE_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py",
    ".rs",
    ".go",
    ".java", ".kt",
    ".rb",
    ".vue", ".svelte",
}

MAX_FILES = 500  # Safety cap for large repos


# ── File Index ──

def build_file_index(workspace: Path) -> dict:
    """Walk source dirs, record path/type/size/tags."""
    files = []
    count = 0

    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        rel_root = os.path.relpath(root, workspace)
        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1]
            if ext not in SOURCE_EXTS:
                continue

            count += 1
            if count > MAX_FILES:
                break

            fpath = os.path.join(root, fname)
            rel_path = os.path.join(rel_root, fname) if rel_root != "." else fname

            try:
                stat = os.stat(fpath)
                size = stat.st_size
            except OSError:
                size = 0

            tags = _auto_tag(rel_path, fname)

            files.append({
                "path": rel_path,
                "ext": ext,
                "size": size,
                "tags": tags,
            })

        if count > MAX_FILES:
            break

    return {"files": files, "total": count, "capped": count >= MAX_FILES}


def _auto_tag(rel_path: str, fname: str) -> list:
    """Assign tags based on path/name patterns."""
    tags = []
    lower = rel_path.lower()
    name_lower = fname.lower()

    if any(p in lower for p in ("test", "spec", "__tests__", "e2e")):
        tags.append("test")
    if any(p in lower for p in ("component", "components")):
        tags.append("component")
    if any(p in lower for p in ("api/", "routes/", "endpoint")):
        tags.append("api")
    if any(p in lower for p in ("lib/", "utils/", "helpers/", "util/")):
        tags.append("util")
    if any(p in lower for p in ("hook", "hooks/")):
        tags.append("hook")
    if any(p in lower for p in ("middleware", "guard")):
        tags.append("middleware")
    if any(p in lower for p in ("model", "schema", "types")):
        tags.append("model")
    if any(p in lower for p in ("config", "settings")):
        tags.append("config")
    if "page" in name_lower or "layout" in name_lower:
        tags.append("page")
    if "index" in name_lower:
        tags.append("entry")

    return tags


# ── Symbol Index ──

JS_EXPORT_RE = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|type|interface|enum)\s+(\w+)",
    re.MULTILINE,
)

GO_FUNC_RE = re.compile(r"^func\s+(?:\(.*?\)\s+)?(\w+)", re.MULTILINE)
GO_TYPE_RE = re.compile(r"^type\s+(\w+)\s+", re.MULTILINE)


def build_symbol_index(workspace: Path, stack: Optional[dict] = None) -> dict:
    """Parse exports/classes/functions from source files. Language-aware."""
    symbols = []
    count = 0
    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1]
            if ext not in SOURCE_EXTS:
                continue

            count += 1
            if count > MAX_FILES:
                break

            fpath = Path(root) / fname
            rel_path = str(fpath.relative_to(workspace))

            try:
                content = fpath.read_text(errors="replace")[:10000]
            except OSError:
                continue

            file_symbols = []

            if ext == ".py":
                file_symbols = _parse_python_symbols(content)
            elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
                file_symbols = _parse_js_symbols(content)
            elif ext == ".go":
                file_symbols = _parse_go_symbols(content)
            elif ext == ".rs":
                file_symbols = _parse_rust_symbols(content)

            if file_symbols:
                symbols.append({
                    "file": rel_path,
                    "symbols": file_symbols[:30],
                })

        if count > MAX_FILES:
            break

    return {"files_with_symbols": len(symbols), "symbols": symbols}


def _parse_python_symbols(content: str) -> list:
    """Extract top-level classes and functions from Python source."""
    symbols = []
    try:
        tree = ast.parse(content)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                symbols.append({"name": node.name, "kind": "class"})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append({"name": node.name, "kind": "function"})
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        symbols.append({"name": target.id, "kind": "constant"})
    except SyntaxError:
        pass
    return symbols


def _parse_js_symbols(content: str) -> list:
    """Extract exported symbols from JS/TS source."""
    symbols = []
    for match in JS_EXPORT_RE.finditer(content):
        name = match.group(1)
        line = match.group(0)
        kind = "unknown"
        if "function" in line:
            kind = "function"
        elif "class" in line:
            kind = "class"
        elif "type" in line or "interface" in line:
            kind = "type"
        elif "enum" in line:
            kind = "enum"
        elif "const" in line or "let" in line or "var" in line:
            kind = "constant"
        symbols.append({"name": name, "kind": kind})
    return symbols


def _parse_go_symbols(content: str) -> list:
    """Extract exported functions and types from Go source."""
    symbols = []
    for match in GO_FUNC_RE.finditer(content):
        name = match.group(1)
        if name[0].isupper():
            symbols.append({"name": name, "kind": "function"})
    for match in GO_TYPE_RE.finditer(content):
        name = match.group(1)
        if name[0].isupper():
            symbols.append({"name": name, "kind": "type"})
    return symbols


def _parse_rust_symbols(content: str) -> list:
    """Extract pub functions and structs from Rust source."""
    symbols = []
    pub_fn = re.compile(r"pub\s+(?:async\s+)?fn\s+(\w+)", re.MULTILINE)
    pub_struct = re.compile(r"pub\s+struct\s+(\w+)", re.MULTILINE)
    pub_enum = re.compile(r"pub\s+enum\s+(\w+)", re.MULTILINE)
    pub_trait = re.compile(r"pub\s+trait\s+(\w+)", re.MULTILINE)

    for match in pub_fn.finditer(content):
        symbols.append({"name": match.group(1), "kind": "function"})
    for match in pub_struct.finditer(content):
        symbols.append({"name": match.group(1), "kind": "struct"})
    for match in pub_enum.finditer(content):
        symbols.append({"name": match.group(1), "kind": "enum"})
    for match in pub_trait.finditer(content):
        symbols.append({"name": match.group(1), "kind": "trait"})
    return symbols


# ── Route Index ──

def build_route_index(workspace: Path, stack: Optional[dict] = None) -> dict:
    """Detect routes from Next.js app dir, Express routers, Flask/FastAPI decorators."""
    routes = []
    frameworks = set()
    if stack:
        frameworks = set(stack.get("frameworks", []))

    app_dir = workspace / "app"
    if app_dir.is_dir() or "next.js" in frameworks:
        routes.extend(_scan_nextjs_routes(workspace))

    pages_dir = workspace / "pages"
    if pages_dir.is_dir():
        routes.extend(_scan_nextjs_pages_routes(workspace))

    routes.extend(_scan_decorator_routes(workspace))

    return {"routes": routes, "total": len(routes)}


def _scan_nextjs_routes(workspace: Path) -> list:
    """Scan Next.js app/ directory for file-based routes."""
    routes = []
    app_dir = workspace / "app"
    if not app_dir.is_dir():
        return routes

    for root, dirs, files in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        rel = os.path.relpath(root, app_dir)
        route_path = "/" if rel == "." else "/" + rel.replace("\\", "/")
        route_path = re.sub(r"/\([^)]+\)", "", route_path)

        for fname in files:
            if fname in ("page.tsx", "page.jsx", "page.ts", "page.js"):
                routes.append({"path": route_path, "type": "page", "file": os.path.join("app", rel, fname)})
            elif fname in ("layout.tsx", "layout.jsx"):
                routes.append({"path": route_path, "type": "layout", "file": os.path.join("app", rel, fname)})
            elif fname in ("route.tsx", "route.ts", "route.js"):
                routes.append({"path": route_path, "type": "api", "file": os.path.join("app", rel, fname)})

    return routes


def _scan_nextjs_pages_routes(workspace: Path) -> list:
    """Scan Next.js pages/ directory."""
    routes = []
    pages_dir = workspace / "pages"
    if not pages_dir.is_dir():
        return routes

    for root, dirs, files in os.walk(pages_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(root, pages_dir)

        for fname in files:
            ext = os.path.splitext(fname)[1]
            if ext not in (".tsx", ".jsx", ".ts", ".js"):
                continue
            name = os.path.splitext(fname)[0]
            if name.startswith("_"):
                continue
            route_path = "/" if rel == "." else "/" + rel.replace("\\", "/")
            if name != "index":
                route_path = route_path.rstrip("/") + "/" + name
            rtype = "api" if "api" in rel else "page"
            routes.append({"path": route_path, "type": rtype,
                           "file": os.path.join("pages", rel, fname)})

    return routes


def _scan_decorator_routes(workspace: Path) -> list:
    """Scan for Express/Flask/FastAPI route decorators in source files."""
    routes = []
    route_re = re.compile(
        r"""(?:@(?:app|router|api|bp)\s*\.\s*(?:get|post|put|delete|patch|route)\s*\(\s*['"]([^'"]+)['"])|"""
        r"""(?:router\s*\.\s*(?:get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"])""",
        re.MULTILINE,
    )

    count = 0
    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1]
            if ext not in (".py", ".ts", ".js", ".mjs"):
                continue

            count += 1
            if count > MAX_FILES:
                break

            fpath = os.path.join(root, fname)
            try:
                content = open(fpath, "r", errors="replace").read()[:8000]
            except OSError:
                continue

            for match in route_re.finditer(content):
                path = match.group(1) or match.group(2)
                if path:
                    rel_file = os.path.relpath(fpath, workspace)
                    routes.append({"path": path, "type": "api", "file": rel_file})

        if count > MAX_FILES:
            break

    return routes


# ── Config Index ──

def build_config_index(workspace: Path) -> dict:
    """Catalog configuration files with key settings."""
    configs = []

    config_patterns = [
        "package.json", "tsconfig.json", "tsconfig.*.json",
        "next.config.*", "vite.config.*", "webpack.config.*",
        "eslint.config.*", ".eslintrc*",
        "pyproject.toml", "setup.cfg", "setup.py",
        "Cargo.toml", "go.mod",
        "Makefile", "Dockerfile", "docker-compose.*",
        ".github/workflows/*.yml", ".github/workflows/*.yaml",
        "jest.config.*", "vitest.config.*", "playwright.config.*",
        "tailwind.config.*", "postcss.config.*",
        "hardhat.config.*", "foundry.toml",
    ]

    seen = set()
    for pattern in config_patterns:
        try:
            for match in workspace.glob(pattern):
                if match.is_file():
                    rel = str(match.relative_to(workspace))
                    if rel not in seen:
                        seen.add(rel)
                        configs.append({
                            "path": rel,
                            "size": match.stat().st_size,
                        })
        except OSError:
            pass

    return {"configs": configs, "total": len(configs)}


# ── Test Index ──

def build_test_index(workspace: Path) -> dict:
    """Map test files to source modules they likely test."""
    tests = []

    test_patterns = [
        "**/*.test.ts", "**/*.test.tsx", "**/*.test.js", "**/*.test.jsx",
        "**/*.spec.ts", "**/*.spec.tsx", "**/*.spec.js", "**/*.spec.jsx",
        "**/test_*.py", "**/*_test.py", "**/*_test.go",
    ]

    seen = set()
    for pattern in test_patterns:
        try:
            for match in workspace.glob(pattern):
                parts = match.parts
                if any(skip in parts for skip in SKIP_DIRS):
                    continue

                rel = str(match.relative_to(workspace))
                if rel in seen:
                    continue
                seen.add(rel)

                source = _infer_source_module(rel)
                tests.append({
                    "test_file": rel,
                    "likely_source": source,
                })
        except OSError:
            pass

    return {"tests": tests, "total": len(tests)}


def _infer_source_module(test_path: str) -> Optional[str]:
    """Infer the source module a test file is testing."""
    fname = os.path.basename(test_path)

    for suffix in (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                   ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx"):
        if fname.endswith(suffix):
            base = fname[:-len(suffix)]
            ext = suffix.split(".")[-1]
            return base + "." + ext

    if fname.startswith("test_") and fname.endswith(".py"):
        return fname[5:]

    if fname.endswith("_test.py"):
        return fname[:-8] + ".py"

    if fname.endswith("_test.go"):
        return fname[:-8] + ".go"

    return None


# ── Staleness + Orchestrator ──

def _get_git_sha(workspace: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(workspace)
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_changed_file_count(workspace: Path, old_sha: str) -> int:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", old_sha, "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(workspace)
        )
        if result.returncode == 0:
            return len([l for l in result.stdout.strip().splitlines() if l])
    except (subprocess.TimeoutExpired, OSError):
        pass
    return 999


def _indexes_dir(agent_dir: Path) -> Path:
    d = agent_dir / "data" / "indexes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_index(agent_dir: Path, name: str) -> Optional[dict]:
    path = _indexes_dir(agent_dir) / f"{name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_index(agent_dir: Path, name: str, data: dict, sha: str):
    wrapped = {
        "generated_at_sha": sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    path = _indexes_dir(agent_dir) / f"{name}.json"
    path.write_text(json.dumps(wrapped, indent=2))


def is_stale(agent_dir: Path, workspace: Path, index_name: str,
             min_changed_files: int = 3) -> bool:
    """Check if an index needs regeneration."""
    existing = _load_index(agent_dir, index_name)
    if not existing:
        return True

    old_sha = existing.get("generated_at_sha")
    if not old_sha:
        return True

    current_sha = _get_git_sha(workspace)
    if not current_sha or old_sha == current_sha:
        return False

    changed = _get_changed_file_count(workspace, old_sha)
    return changed >= min_changed_files


def refresh_indexes(agent_dir: Path, workspace: Path,
                    stack: Optional[dict] = None) -> dict:
    """Regenerate stale indexes. Returns freshness report."""
    report = {"refreshed": [], "skipped": [], "errors": []}
    current_sha = _get_git_sha(workspace) or "unknown"

    if stack is None:
        stack_file = agent_dir / "data" / "artifacts" / "stack_detect.json"
        if stack_file.exists():
            try:
                raw = json.loads(stack_file.read_text())
                stack = raw.get("data", raw)
            except (json.JSONDecodeError, OSError):
                stack = {}

    index_builders = [
        ("file_index", lambda: build_file_index(workspace)),
        ("symbol_index", lambda: build_symbol_index(workspace, stack)),
        ("route_index", lambda: build_route_index(workspace, stack)),
        ("config_index", lambda: build_config_index(workspace)),
        ("test_index", lambda: build_test_index(workspace)),
    ]

    for name, builder in index_builders:
        try:
            if is_stale(agent_dir, workspace, name):
                data = builder()
                _save_index(agent_dir, name, data, current_sha)
                report["refreshed"].append(name)
            else:
                report["skipped"].append(name)
        except Exception as e:
            report["errors"].append(f"{name}: {e}")

    return report


def load_all_indexes(agent_dir: Path) -> dict:
    """Load all indexes for prompt injection."""
    indexes = {}
    idx_dir = _indexes_dir(agent_dir)
    if not idx_dir.exists():
        return indexes
    for f in idx_dir.iterdir():
        if f.suffix == ".json":
            try:
                raw = json.loads(f.read_text())
                indexes[f.stem] = raw.get("data", raw)
            except (json.JSONDecodeError, OSError):
                pass
    return indexes


def format_indexes_for_prompt(indexes: dict, max_tokens: int = 800) -> str:
    """Format indexes into a concise prompt-friendly string."""
    sections = []

    routes = indexes.get("route_index", {})
    if routes and routes.get("routes"):
        lines = [f"- `{r['path']}` ({r['type']}) \u2192 {r['file']}"
                 for r in routes["routes"][:15]]
        sections.append("### Routes\n" + "\n".join(lines))

    tests = indexes.get("test_index", {})
    if tests and tests.get("tests"):
        lines = [f"- {t['test_file']} \u2192 {t.get('likely_source', '?')}"
                 for t in tests["tests"][:10]]
        sections.append("### Test Map\n" + "\n".join(lines))

    file_idx = indexes.get("file_index", {})
    if file_idx and file_idx.get("files"):
        tag_counts = {}
        for f in file_idx["files"]:
            for tag in f.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if tag_counts:
            parts = [f"{tag}={count}" for tag, count in
                     sorted(tag_counts.items(), key=lambda x: -x[1])[:8]]
            sections.append(f"### File Distribution\n{', '.join(parts)} ({file_idx['total']} total)")

    result = "\n\n".join(sections)
    if len(result) > max_tokens * 4:
        result = result[:max_tokens * 4] + "\n\n[... truncated]"
    return result
