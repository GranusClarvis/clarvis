#!/usr/bin/env python3
"""PR Factory Phase 2 — Deterministic Intake Artifacts.

Generates repo-level artifacts for project agents:
- project_brief: product description, domain, constraints from README/configs
- stack_detect: languages, frameworks, package managers, tools
- commands: install/build/test/lint/typecheck extracted from config files
- architecture_map: entrypoints, module layout, directory structure

Artifacts are stored in <agent_dir>/data/artifacts/ with staleness tracking
via git SHA comparison.

Usage:
    from pr_factory_intake import refresh_artifacts
    report = refresh_artifacts(agent_dir, workspace)
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Project Brief ──

def generate_project_brief(workspace: Path) -> dict:
    """Scan README, docs, and config files for product description."""
    brief = {
        "name": "",
        "description": "",
        "domain": "",
        "constraints": [],
        "doc_files": [],
    }

    # Try package.json first (most structured)
    pkg = workspace / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            brief["name"] = data.get("name", "")
            brief["description"] = data.get("description", "")
        except (json.JSONDecodeError, OSError):
            pass

    # Try pyproject.toml
    pyproj = workspace / "pyproject.toml"
    if pyproj.exists() and not brief["name"]:
        try:
            text = pyproj.read_text()
            for line in text.splitlines():
                if line.strip().startswith("name"):
                    brief["name"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.strip().startswith("description"):
                    brief["description"] = line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass

    # Try Cargo.toml
    cargo = workspace / "Cargo.toml"
    if cargo.exists() and not brief["name"]:
        try:
            text = cargo.read_text()
            for line in text.splitlines():
                if line.strip().startswith("name"):
                    brief["name"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except OSError:
            pass

    # Extract domain/constraints from README
    for readme_name in ("README.md", "readme.md", "README.rst", "README"):
        readme = workspace / readme_name
        if readme.exists():
            try:
                text = readme.read_text()[:3000]
                brief["doc_files"].append(readme_name)
                # First paragraph as domain hint (skip badges/headers)
                lines = [l.strip() for l in text.splitlines()
                         if l.strip() and not l.startswith("#") and not l.startswith("[")
                         and not l.startswith("!")]
                if lines:
                    brief["domain"] = lines[0][:200]
                break
            except OSError:
                pass

    # Scan for CLAUDE.md constraints
    claude_md = workspace / "CLAUDE.md"
    if claude_md.exists():
        try:
            text = claude_md.read_text()[:4000]
            brief["doc_files"].append("CLAUDE.md")
            # Extract constraints-like lines (bullet points under constraint-ish headers)
            in_constraints = False
            for line in text.splitlines():
                lower = line.lower().strip()
                if any(kw in lower for kw in ("constraint", "rule", "important", "never", "always")):
                    if lower.startswith("#"):
                        in_constraints = True
                        continue
                if in_constraints:
                    if line.strip().startswith("- "):
                        brief["constraints"].append(line.strip()[2:][:150])
                    elif line.strip().startswith("#"):
                        in_constraints = False
                if len(brief["constraints"]) >= 10:
                    break
        except OSError:
            pass

    # Check for docs/ directory
    docs_dir = workspace / "docs"
    if docs_dir.is_dir():
        try:
            doc_files = [f.name for f in docs_dir.iterdir()
                         if f.is_file() and f.suffix in (".md", ".rst", ".txt")][:10]
            brief["doc_files"].extend(doc_files)
        except OSError:
            pass

    return brief


# ── Stack Detection ──

CONFIG_FILES = {
    "package.json": {"language": "javascript/typescript", "pm": "npm"},
    "yarn.lock": {"pm": "yarn"},
    "pnpm-lock.yaml": {"pm": "pnpm"},
    "bun.lockb": {"pm": "bun"},
    "pyproject.toml": {"language": "python"},
    "setup.py": {"language": "python"},
    "requirements.txt": {"language": "python"},
    "Cargo.toml": {"language": "rust"},
    "go.mod": {"language": "go"},
    "Gemfile": {"language": "ruby"},
    "build.gradle": {"language": "java/kotlin"},
    "pom.xml": {"language": "java"},
    "mix.exs": {"language": "elixir"},
}

FRAMEWORK_MARKERS = {
    "next.config.ts": "next.js",
    "next.config.js": "next.js",
    "next.config.mjs": "next.js",
    "nuxt.config.ts": "nuxt",
    "nuxt.config.js": "nuxt",
    "angular.json": "angular",
    "svelte.config.js": "svelte",
    "vite.config.ts": "vite",
    "vite.config.js": "vite",
    "remix.config.js": "remix",
    "astro.config.mjs": "astro",
    "tailwind.config.ts": "tailwind",
    "tailwind.config.js": "tailwind",
    "postcss.config.mjs": "postcss",
    "postcss.config.js": "postcss",
    "hardhat.config.ts": "hardhat",
    "hardhat.config.js": "hardhat",
    "foundry.toml": "foundry",
    "truffle-config.js": "truffle",
    "django/settings.py": "django",
    "manage.py": "django",
    "app.py": "flask-candidate",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker-compose",
    "docker-compose.yaml": "docker-compose",
}


def generate_stack_detect(workspace: Path) -> dict:
    """Detect languages, frameworks, package managers, and tools."""
    stack = {
        "languages": [],
        "frameworks": [],
        "package_manager": None,
        "tools": {
            "linter": [],
            "formatter": [],
            "bundler": [],
            "test": [],
        },
        "config_files_found": [],
    }

    seen_langs = set()

    # Check config files
    for filename, info in CONFIG_FILES.items():
        if (workspace / filename).exists():
            stack["config_files_found"].append(filename)
            lang = info.get("language")
            if lang and lang not in seen_langs:
                stack["languages"].append(lang)
                seen_langs.add(lang)
            pm = info.get("pm")
            if pm and not stack["package_manager"]:
                stack["package_manager"] = pm

    # Check framework markers
    seen_fw = set()
    for filename, fw in FRAMEWORK_MARKERS.items():
        if (workspace / filename).exists():
            if fw not in seen_fw:
                stack["frameworks"].append(fw)
                seen_fw.add(fw)

    # Detect tools from config files
    tool_config_map = {
        ".eslintrc": "eslint", ".eslintrc.js": "eslint", ".eslintrc.json": "eslint",
        "eslint.config.mjs": "eslint", "eslint.config.js": "eslint",
        ".prettierrc": "prettier", ".prettierrc.js": "prettier",
        "biome.json": "biome",
        "jest.config.js": "jest", "jest.config.ts": "jest",
        "vitest.config.ts": "vitest", "vitest.config.js": "vitest",
        "cypress.config.ts": "cypress", "cypress.config.js": "cypress",
        "playwright.config.ts": "playwright",
        ".babelrc": "babel", "babel.config.js": "babel",
        "tsconfig.json": "typescript",
        "webpack.config.js": "webpack",
        "rollup.config.js": "rollup",
        "esbuild.config.js": "esbuild",
        "ruff.toml": "ruff", ".flake8": "flake8",
        "mypy.ini": "mypy", ".mypy.ini": "mypy",
        "pytest.ini": "pytest", "setup.cfg": "pytest-candidate",
    }

    tool_categories = {
        "eslint": "linter", "biome": "linter", "ruff": "linter", "flake8": "linter",
        "prettier": "formatter", "biome": "formatter",
        "jest": "test", "vitest": "test", "cypress": "test", "playwright": "test", "pytest": "test",
        "webpack": "bundler", "rollup": "bundler", "esbuild": "bundler",
        "typescript": "linter",
    }

    for filename, tool in tool_config_map.items():
        if (workspace / filename).exists():
            cat = tool_categories.get(tool, "linter")
            if tool not in stack["tools"][cat]:
                stack["tools"][cat].append(tool)

    return stack


# ── Command Detection ──

def generate_commands(workspace: Path) -> dict:
    """Extract install/build/test/lint/typecheck commands from config files."""
    commands = {
        "install": [],
        "build": [],
        "test": [],
        "lint": [],
        "typecheck": [],
        "dev": [],
    }
    sources = []

    # package.json scripts
    pkg = workspace / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            scripts = data.get("scripts", {})
            sources.append("package.json")

            pm = "npm"
            if (workspace / "yarn.lock").exists():
                pm = "yarn"
            elif (workspace / "pnpm-lock.yaml").exists():
                pm = "pnpm"
            elif (workspace / "bun.lockb").exists():
                pm = "bun"

            script_map = {
                "install": ["install", "postinstall"],
                "build": ["build", "compile"],
                "test": ["test", "test:unit", "test:e2e", "test:integration"],
                "lint": ["lint", "lint:fix"],
                "typecheck": ["type-check", "typecheck", "tsc"],
                "dev": ["dev", "start", "serve"],
            }

            for category, script_names in script_map.items():
                for sn in script_names:
                    if sn in scripts:
                        cmd = f"{pm} run {sn}" if pm != "npm" else f"npm run {sn}"
                        if cmd not in commands[category]:
                            commands[category].append(cmd)

            # Add install command
            install_cmd = f"{pm} install"
            if install_cmd not in commands["install"]:
                commands["install"].insert(0, install_cmd)

        except (json.JSONDecodeError, OSError):
            pass

    # Makefile
    makefile = workspace / "Makefile"
    if makefile.exists():
        try:
            text = makefile.read_text()[:5000]
            sources.append("Makefile")
            for line in text.splitlines():
                if line and not line.startswith("\t") and not line.startswith("#"):
                    target = line.split(":")[0].strip()
                    target_map = {
                        "build": "build", "test": "test", "lint": "lint",
                        "install": "install", "dev": "dev", "check": "typecheck",
                    }
                    for key, cat in target_map.items():
                        if target == key:
                            cmd = f"make {target}"
                            if cmd not in commands[cat]:
                                commands[cat].append(cmd)
        except OSError:
            pass

    # pyproject.toml (basic)
    pyproj = workspace / "pyproject.toml"
    if pyproj.exists():
        try:
            text = pyproj.read_text()[:3000]
            sources.append("pyproject.toml")
            if "pytest" in text:
                cmd = "python3 -m pytest"
                if cmd not in commands["test"]:
                    commands["test"].append(cmd)
            if "ruff" in text:
                cmd = "ruff check ."
                if cmd not in commands["lint"]:
                    commands["lint"].append(cmd)
            if "mypy" in text:
                cmd = "mypy ."
                if cmd not in commands["typecheck"]:
                    commands["typecheck"].append(cmd)
        except OSError:
            pass

    return {"commands": commands, "sources": sources}


# ── Architecture Map ──

# Directories to always skip when scanning
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".nuxt", "dist", "build",
    ".cache", ".turbo", "coverage", ".pytest_cache", "venv", ".venv", "env",
    "target",  # Rust
}


def generate_architecture_map(workspace: Path) -> dict:
    """Build a structural map: entrypoints, module layout, directory tree."""
    arch = {
        "entrypoints": [],
        "source_dirs": [],
        "test_dirs": [],
        "config_files": [],
        "top_level_dirs": [],
    }

    # Top-level directory listing
    try:
        for item in sorted(workspace.iterdir()):
            if item.name.startswith(".") or item.name in SKIP_DIRS:
                continue
            if item.is_dir():
                arch["top_level_dirs"].append(item.name)
            elif item.is_file() and item.suffix in (".json", ".toml", ".yaml", ".yml",
                                                      ".ts", ".js", ".mjs", ".cfg"):
                arch["config_files"].append(item.name)
    except OSError:
        pass

    # Detect entrypoints
    entrypoint_candidates = [
        "app/layout.tsx", "app/page.tsx",  # Next.js App Router
        "pages/_app.tsx", "pages/index.tsx",  # Next.js Pages Router
        "src/index.tsx", "src/index.ts", "src/main.tsx", "src/main.ts",
        "src/App.tsx", "src/App.vue",
        "index.ts", "index.js",
        "main.py", "app.py", "manage.py",
        "src/main.rs", "src/lib.rs",
        "main.go", "cmd/main.go",
    ]
    for ep in entrypoint_candidates:
        if (workspace / ep).exists():
            arch["entrypoints"].append(ep)

    # Walk source directories (limit depth to 3 for speed)
    _walk_dirs(workspace, arch, max_depth=3)

    return arch


def _walk_dirs(workspace: Path, arch: dict, max_depth: int = 3):
    """Walk source tree to find source and test directories."""
    source_exts = {".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".rb"}
    test_patterns = {"test", "tests", "__tests__", "spec", "specs", "e2e"}

    def _scan(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = list(path.iterdir())
        except OSError:
            return

        file_count = 0
        has_source = False
        is_test_dir = path.name.lower() in test_patterns

        for entry in entries:
            if entry.name.startswith(".") or entry.name in SKIP_DIRS:
                continue
            if entry.is_file() and entry.suffix in source_exts:
                file_count += 1
                has_source = True
            elif entry.is_dir():
                _scan(entry, depth + 1)

        if has_source and file_count > 0:
            rel = str(path.relative_to(workspace))
            info = {"path": rel, "file_count": file_count}
            if is_test_dir or any(tp in rel.lower() for tp in test_patterns):
                arch["test_dirs"].append(info)
            else:
                arch["source_dirs"].append(info)

    for item in workspace.iterdir():
        if item.name.startswith(".") or item.name in SKIP_DIRS:
            continue
        if item.is_dir():
            _scan(item, 1)


# ── Trust Boundaries ──

def generate_trust_boundaries(workspace: Path) -> dict:
    """Identify security-sensitive areas: env files, secrets, auth modules."""
    boundaries = {
        "env_files": [],
        "secret_patterns": [],
        "auth_modules": [],
        "ci_configs": [],
    }

    # Env files
    for pattern in (".env", ".env.local", ".env.production", ".env.development"):
        if (workspace / pattern).exists():
            boundaries["env_files"].append(pattern)

    # .env.example (safe to read for structure)
    for pattern in (".env.example", ".env.sample", ".env.template"):
        if (workspace / pattern).exists():
            boundaries["env_files"].append(f"{pattern} (template)")

    # Auth-related directories
    auth_dirs = ["auth", "authentication", "middleware/auth", "lib/auth",
                 "src/auth", "app/api/auth", "api/auth"]
    for d in auth_dirs:
        if (workspace / d).is_dir():
            boundaries["auth_modules"].append(d)

    # CI configs
    gh_workflows = workspace / ".github" / "workflows"
    if gh_workflows.is_dir():
        try:
            for f in gh_workflows.iterdir():
                if f.suffix in (".yml", ".yaml"):
                    boundaries["ci_configs"].append(f".github/workflows/{f.name}")
        except OSError:
            pass

    return boundaries


# ── Staleness + Orchestrator ──

def _get_git_sha(workspace: Path) -> Optional[str]:
    """Get current HEAD SHA for staleness check."""
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
    """Count files changed since old_sha."""
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
    return 999  # assume stale if can't check


def _artifacts_dir(agent_dir: Path) -> Path:
    d = agent_dir / "data" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_artifact(agent_dir: Path, name: str) -> Optional[dict]:
    """Load an artifact from disk, return None if missing."""
    path = _artifacts_dir(agent_dir) / f"{name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_artifact(agent_dir: Path, name: str, data: dict, sha: str):
    """Save artifact with metadata."""
    wrapped = {
        "generated_at_sha": sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    path = _artifacts_dir(agent_dir) / f"{name}.json"
    path.write_text(json.dumps(wrapped, indent=2))


def is_stale(agent_dir: Path, workspace: Path, artifact_name: str,
             min_changed_files: int = 5) -> bool:
    """Check if an artifact needs regeneration.

    Stale if: missing, SHA differs AND >min_changed_files changed.
    """
    existing = _load_artifact(agent_dir, artifact_name)
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


def refresh_artifacts(agent_dir: Path, workspace: Path) -> dict:
    """Regenerate stale artifacts. Returns freshness report."""
    report = {"refreshed": [], "skipped": [], "errors": []}
    current_sha = _get_git_sha(workspace) or "unknown"

    artifact_generators = {
        "project_brief": generate_project_brief,
        "stack_detect": generate_stack_detect,
        "commands": generate_commands,
        "architecture_map": generate_architecture_map,
        "trust_boundaries": generate_trust_boundaries,
    }

    for name, generator in artifact_generators.items():
        try:
            if is_stale(agent_dir, workspace, name):
                data = generator(workspace)
                _save_artifact(agent_dir, name, data, current_sha)
                report["refreshed"].append(name)
            else:
                report["skipped"].append(name)
        except Exception as e:
            report["errors"].append(f"{name}: {e}")

    return report


def load_all_artifacts(agent_dir: Path) -> dict:
    """Load all artifacts for prompt injection. Returns dict of name->data."""
    artifacts = {}
    artifacts_dir = _artifacts_dir(agent_dir)
    for f in artifacts_dir.iterdir():
        if f.suffix == ".json":
            try:
                raw = json.loads(f.read_text())
                artifacts[f.stem] = raw.get("data", raw)
            except (json.JSONDecodeError, OSError):
                pass
    return artifacts


def format_artifacts_for_prompt(artifacts: dict, max_tokens: int = 1500) -> str:
    """Format loaded artifacts into a prompt-friendly string."""
    sections = []

    brief = artifacts.get("project_brief", {})
    if brief:
        lines = []
        if brief.get("name"):
            lines.append(f"**Project**: {brief['name']}")
        if brief.get("description"):
            lines.append(f"**Description**: {brief['description']}")
        if brief.get("domain"):
            lines.append(f"**Domain**: {brief['domain'][:100]}")
        if brief.get("constraints"):
            lines.append("**Constraints**: " + "; ".join(brief["constraints"][:5]))
        if lines:
            sections.append("### Project Brief\n" + "\n".join(lines))

    stack = artifacts.get("stack_detect", {})
    if stack:
        lines = []
        if stack.get("languages"):
            lines.append(f"**Languages**: {', '.join(stack['languages'])}")
        if stack.get("frameworks"):
            lines.append(f"**Frameworks**: {', '.join(stack['frameworks'])}")
        if stack.get("package_manager"):
            lines.append(f"**Package Manager**: {stack['package_manager']}")
        tools = stack.get("tools", {})
        active_tools = {k: v for k, v in tools.items() if v}
        if active_tools:
            parts = [f"{k}: {', '.join(v)}" for k, v in active_tools.items()]
            lines.append(f"**Tools**: {' | '.join(parts)}")
        if lines:
            sections.append("### Stack\n" + "\n".join(lines))

    cmds = artifacts.get("commands", {})
    if cmds and cmds.get("commands"):
        lines = []
        for cat, cmd_list in cmds["commands"].items():
            if cmd_list:
                lines.append(f"- **{cat}**: {' ; '.join(cmd_list)}")
        if lines:
            sections.append("### Commands\n" + "\n".join(lines))

    arch = artifacts.get("architecture_map", {})
    if arch:
        lines = []
        if arch.get("entrypoints"):
            lines.append(f"**Entrypoints**: {', '.join(arch['entrypoints'][:5])}")
        if arch.get("source_dirs"):
            dirs = [f"{d['path']}/ ({d['file_count']})" for d in arch["source_dirs"][:8]]
            lines.append(f"**Source dirs**: {', '.join(dirs)}")
        if arch.get("test_dirs"):
            tdirs = [f"{d['path']}/ ({d['file_count']})" for d in arch["test_dirs"][:4]]
            lines.append(f"**Test dirs**: {', '.join(tdirs)}")
        if lines:
            sections.append("### Architecture\n" + "\n".join(lines))

    trust = artifacts.get("trust_boundaries", {})
    if trust:
        lines = []
        if trust.get("env_files"):
            lines.append(f"**Env files**: {', '.join(trust['env_files'])}")
        if trust.get("auth_modules"):
            lines.append(f"**Auth modules**: {', '.join(trust['auth_modules'])}")
        if trust.get("ci_configs"):
            lines.append(f"**CI configs**: {', '.join(trust['ci_configs'][:5])}")
        if lines:
            sections.append("### Trust Boundaries\n" + "\n".join(lines))

    result = "\n\n".join(sections)
    # Hard token cap
    if len(result) > max_tokens * 4:  # rough char-to-token ratio
        result = result[:max_tokens * 4] + "\n\n[... truncated]"
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: pr_factory_intake.py <agent_dir> <workspace>")
        sys.exit(1)
    agent_dir = Path(sys.argv[1])
    workspace = Path(sys.argv[2])
    report = refresh_artifacts(agent_dir, workspace)
    print(json.dumps(report, indent=2))
