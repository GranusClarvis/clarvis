"""
Tests for PR Factory Phase 2 — Deterministic Intake Artifacts + Precision Indexes.

Run: python3 -m pytest scripts/tests/test_pr_factory_intake.py -v
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from pr_factory_intake import (
    generate_project_brief,
    generate_stack_detect,
    generate_commands,
    generate_architecture_map,
    generate_trust_boundaries,
    refresh_artifacts,
    load_all_artifacts,
    format_artifacts_for_prompt,
    is_stale,
    _save_artifact,
)
from pr_factory_indexes import (
    build_file_index,
    build_symbol_index,
    build_route_index,
    build_config_index,
    build_test_index,
    refresh_indexes,
    load_all_indexes,
    format_indexes_for_prompt,
    _parse_python_symbols,
    _parse_js_symbols,
    _parse_go_symbols,
    _parse_rust_symbols,
    _auto_tag,
)


# ── Fixtures ──

@pytest.fixture
def workspace(tmp_path):
    """Create a realistic project workspace."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    # package.json
    (ws / "package.json").write_text(json.dumps({
        "name": "test-app",
        "description": "A test application",
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "test": "jest",
            "lint": "eslint .",
            "type-check": "tsc --noEmit",
        },
    }))

    # next.config.ts
    (ws / "next.config.ts").write_text("export default {};")

    # tsconfig.json
    (ws / "tsconfig.json").write_text('{"compilerOptions": {}}')

    # eslint config
    (ws / "eslint.config.mjs").write_text("export default [];")

    # README
    (ws / "README.md").write_text("# Test App\n\nA web application for testing.\n")

    # App directory (Next.js)
    app = ws / "app"
    app.mkdir()
    (app / "layout.tsx").write_text("export default function RootLayout() {}")
    (app / "page.tsx").write_text("export default function Home() {}")

    # API route
    api = app / "api" / "users"
    api.mkdir(parents=True)
    (api / "route.ts").write_text(
        "export async function GET() {}\n"
        "export async function POST() {}\n"
    )

    # Components
    comp = ws / "components"
    comp.mkdir()
    (comp / "Button.tsx").write_text(
        "export default function Button() {}\n"
        "export const ButtonVariant = 'primary';\n"
    )
    (comp / "Modal.tsx").write_text(
        "export interface ModalProps { open: boolean; }\n"
        "export default function Modal() {}\n"
    )

    # Lib
    lib = ws / "lib"
    lib.mkdir()
    (lib / "utils.ts").write_text(
        "export function cn(...args: string[]) { return args.join(' '); }\n"
        "export const API_URL = '/api';\n"
    )
    (lib / "auth.ts").write_text(
        "export async function getSession() {}\n"
    )

    # Test files
    tests = ws / "__tests__"
    tests.mkdir()
    (tests / "Button.test.tsx").write_text("test('renders', () => {})")

    # .env files
    (ws / ".env.example").write_text("DATABASE_URL=")
    (ws / ".env.local").write_text("SECRET=xxx")

    # CI
    gh = ws / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "ci.yml").write_text("name: CI")

    # git init for SHA-based staleness
    os.system(f"cd {ws} && git init -q && git add -A && git commit -q -m init")

    return ws


@pytest.fixture
def agent_dir(tmp_path):
    d = tmp_path / "agent"
    d.mkdir()
    (d / "data").mkdir()
    return d


# ── Project Brief Tests ──

class TestProjectBrief:
    def test_extracts_name_from_package_json(self, workspace):
        brief = generate_project_brief(workspace)
        assert brief["name"] == "test-app"

    def test_extracts_description(self, workspace):
        brief = generate_project_brief(workspace)
        assert brief["description"] == "A test application"

    def test_extracts_domain_from_readme(self, workspace):
        brief = generate_project_brief(workspace)
        assert brief["domain"]  # Should have first paragraph

    def test_lists_doc_files(self, workspace):
        brief = generate_project_brief(workspace)
        assert "README.md" in brief["doc_files"]

    def test_handles_missing_package_json(self, tmp_path):
        ws = tmp_path / "empty"
        ws.mkdir()
        brief = generate_project_brief(ws)
        assert brief["name"] == ""
        assert brief["description"] == ""

    def test_pyproject_fallback(self, tmp_path):
        ws = tmp_path / "pyws"
        ws.mkdir()
        (ws / "pyproject.toml").write_text(
            '[project]\nname = "my-py-app"\ndescription = "A Python app"\n'
        )
        brief = generate_project_brief(ws)
        assert brief["name"] == "my-py-app"


# ── Stack Detection Tests ──

class TestStackDetect:
    def test_detects_language(self, workspace):
        stack = generate_stack_detect(workspace)
        assert "javascript/typescript" in stack["languages"]

    def test_detects_framework(self, workspace):
        stack = generate_stack_detect(workspace)
        assert "next.js" in stack["frameworks"]

    def test_detects_package_manager(self, workspace):
        stack = generate_stack_detect(workspace)
        assert stack["package_manager"] == "npm"

    def test_detects_linter(self, workspace):
        stack = generate_stack_detect(workspace)
        assert "eslint" in stack["tools"]["linter"]

    def test_records_config_files(self, workspace):
        stack = generate_stack_detect(workspace)
        assert "package.json" in stack["config_files_found"]

    def test_empty_workspace(self, tmp_path):
        ws = tmp_path / "empty"
        ws.mkdir()
        stack = generate_stack_detect(ws)
        assert stack["languages"] == []
        assert stack["frameworks"] == []


# ── Command Detection Tests ──

class TestCommands:
    def test_extracts_build_command(self, workspace):
        cmds = generate_commands(workspace)
        build = cmds["commands"]["build"]
        assert any("build" in c for c in build)

    def test_extracts_test_command(self, workspace):
        cmds = generate_commands(workspace)
        test = cmds["commands"]["test"]
        assert any("test" in c for c in test)

    def test_extracts_lint_command(self, workspace):
        cmds = generate_commands(workspace)
        lint = cmds["commands"]["lint"]
        assert any("lint" in c for c in lint)

    def test_includes_install_command(self, workspace):
        cmds = generate_commands(workspace)
        assert any("install" in c for c in cmds["commands"]["install"])

    def test_records_sources(self, workspace):
        cmds = generate_commands(workspace)
        assert "package.json" in cmds["sources"]


# ── Architecture Map Tests ──

class TestArchitectureMap:
    def test_detects_entrypoints(self, workspace):
        arch = generate_architecture_map(workspace)
        assert "app/layout.tsx" in arch["entrypoints"]
        assert "app/page.tsx" in arch["entrypoints"]

    def test_detects_source_dirs(self, workspace):
        arch = generate_architecture_map(workspace)
        paths = [d["path"] for d in arch["source_dirs"]]
        assert any("components" in p for p in paths)
        assert any("lib" in p for p in paths)

    def test_detects_top_level_dirs(self, workspace):
        arch = generate_architecture_map(workspace)
        assert "app" in arch["top_level_dirs"]
        assert "components" in arch["top_level_dirs"]

    def test_detects_config_files(self, workspace):
        arch = generate_architecture_map(workspace)
        assert "package.json" in arch["config_files"]


# ── Trust Boundaries Tests ──

class TestTrustBoundaries:
    def test_detects_env_files(self, workspace):
        trust = generate_trust_boundaries(workspace)
        assert any(".env.local" in f for f in trust["env_files"])
        assert any(".env.example" in f for f in trust["env_files"])

    def test_detects_ci_configs(self, workspace):
        trust = generate_trust_boundaries(workspace)
        assert any("ci.yml" in f for f in trust["ci_configs"])


# ── Staleness Tests ──

class TestStaleness:
    def test_stale_when_missing(self, agent_dir, workspace):
        assert is_stale(agent_dir, workspace, "project_brief") is True

    def test_not_stale_when_same_sha(self, agent_dir, workspace):
        data = generate_project_brief(workspace)
        # Get current SHA
        import subprocess
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=str(workspace)
        ).stdout.strip()
        _save_artifact(agent_dir, "project_brief", data, sha)
        assert is_stale(agent_dir, workspace, "project_brief") is False

    def test_stale_when_sha_missing_from_artifact(self, agent_dir, workspace):
        _save_artifact(agent_dir, "project_brief", {}, "")
        assert is_stale(agent_dir, workspace, "project_brief") is True


# ── Refresh Orchestrator Tests ──

class TestRefreshArtifacts:
    def test_refresh_generates_all_artifacts(self, agent_dir, workspace):
        report = refresh_artifacts(agent_dir, workspace)
        assert "project_brief" in report["refreshed"]
        assert "stack_detect" in report["refreshed"]
        assert "commands" in report["refreshed"]
        assert "architecture_map" in report["refreshed"]
        assert "trust_boundaries" in report["refreshed"]
        assert report["errors"] == []

    def test_refresh_creates_artifact_files(self, agent_dir, workspace):
        refresh_artifacts(agent_dir, workspace)
        artifacts_dir = agent_dir / "data" / "artifacts"
        assert (artifacts_dir / "project_brief.json").exists()
        assert (artifacts_dir / "stack_detect.json").exists()
        assert (artifacts_dir / "commands.json").exists()

    def test_second_refresh_skips(self, agent_dir, workspace):
        refresh_artifacts(agent_dir, workspace)
        report2 = refresh_artifacts(agent_dir, workspace)
        # All should be skipped on second run (same SHA)
        assert len(report2["skipped"]) == 5
        assert len(report2["refreshed"]) == 0


# ── Load + Format Tests ──

class TestLoadAndFormat:
    def test_load_all_artifacts(self, agent_dir, workspace):
        refresh_artifacts(agent_dir, workspace)
        artifacts = load_all_artifacts(agent_dir)
        assert "project_brief" in artifacts
        assert "stack_detect" in artifacts

    def test_format_artifacts_for_prompt(self, agent_dir, workspace):
        refresh_artifacts(agent_dir, workspace)
        artifacts = load_all_artifacts(agent_dir)
        text = format_artifacts_for_prompt(artifacts)
        assert "test-app" in text
        assert "next.js" in text


# ── Symbol Index Tests ──

class TestSymbolIndex:
    def test_parses_js_exports(self):
        content = """
export default function Home() {}
export const API_URL = '/api';
export class UserService {}
export type UserInput = { name: string };
export interface Props { id: number }
export enum Status { Active, Inactive }
"""
        symbols = _parse_js_symbols(content)
        names = {s["name"] for s in symbols}
        assert "Home" in names
        assert "API_URL" in names
        assert "UserService" in names
        assert "UserInput" in names
        assert "Props" in names
        assert "Status" in names

    def test_parses_python_symbols(self):
        content = """
class UserModel:
    pass

def get_user(id: int):
    pass

async def create_user():
    pass

MAX_RETRIES = 3
"""
        symbols = _parse_python_symbols(content)
        names = {s["name"] for s in symbols}
        assert "UserModel" in names
        assert "get_user" in names
        assert "create_user" in names
        assert "MAX_RETRIES" in names

    def test_parses_go_symbols(self):
        content = """
func HandleRequest(w http.ResponseWriter, r *http.Request) {}
func (s *Server) Start() {}
type Config struct {}
func privateHelper() {}
"""
        symbols = _parse_go_symbols(content)
        names = {s["name"] for s in symbols}
        assert "HandleRequest" in names
        assert "Start" in names
        assert "Config" in names
        assert "privateHelper" not in names  # unexported

    def test_parses_rust_symbols(self):
        content = """
pub fn process(input: &str) -> Result<()> {}
pub struct AppState { db: Pool }
pub enum Error { NotFound, Internal }
pub trait Handler { fn handle(&self); }
fn private_fn() {}
"""
        symbols = _parse_rust_symbols(content)
        names = {s["name"] for s in symbols}
        assert "process" in names
        assert "AppState" in names
        assert "Error" in names
        assert "Handler" in names
        assert "private_fn" not in names  # not pub

    def test_build_symbol_index_on_workspace(self, workspace):
        idx = build_symbol_index(workspace)
        assert idx["files_with_symbols"] > 0
        # Should find exports from our component files
        all_names = set()
        for entry in idx["symbols"]:
            for s in entry["symbols"]:
                all_names.add(s["name"])
        assert "Button" in all_names or "Modal" in all_names


# ── File Index Tests ──

class TestFileIndex:
    def test_indexes_source_files(self, workspace):
        idx = build_file_index(workspace)
        assert idx["total"] > 0
        paths = {f["path"] for f in idx["files"]}
        assert any("Button.tsx" in p for p in paths)
        assert any("utils.ts" in p for p in paths)

    def test_auto_tags(self):
        assert "component" in _auto_tag("components/Button.tsx", "Button.tsx")
        assert "test" in _auto_tag("__tests__/foo.test.ts", "foo.test.ts")
        assert "api" in _auto_tag("api/users/route.ts", "route.ts")
        assert "util" in _auto_tag("lib/utils.ts", "utils.ts")

    def test_skips_node_modules(self, workspace):
        nm = workspace / "node_modules" / "react"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {};")
        idx = build_file_index(workspace)
        paths = {f["path"] for f in idx["files"]}
        assert not any("node_modules" in p for p in paths)


# ── Route Index Tests ──

class TestRouteIndex:
    def test_detects_nextjs_app_routes(self, workspace):
        idx = build_route_index(workspace)
        paths = [r["path"] for r in idx["routes"]]
        assert "/" in paths  # page.tsx
        assert any("users" in p for p in paths)  # api route

    def test_detects_route_types(self, workspace):
        idx = build_route_index(workspace)
        types = {r["type"] for r in idx["routes"]}
        assert "page" in types
        assert "api" in types or "layout" in types


# ── Config Index Tests ──

class TestConfigIndex:
    def test_finds_config_files(self, workspace):
        idx = build_config_index(workspace)
        paths = {c["path"] for c in idx["configs"]}
        assert "package.json" in paths
        assert "tsconfig.json" in paths


# ── Test Index Tests ──

class TestTestIndex:
    def test_maps_test_files(self, workspace):
        idx = build_test_index(workspace)
        assert idx["total"] > 0
        test_files = [t["test_file"] for t in idx["tests"]]
        assert any("Button.test.tsx" in t for t in test_files)

    def test_infers_source_module(self):
        from pr_factory_indexes import _infer_source_module
        assert _infer_source_module("Button.test.tsx") == "Button.tsx"
        assert _infer_source_module("test_utils.py") == "utils.py"
        assert _infer_source_module("handler_test.go") == "handler.go"


# ── Index Refresh Tests ──

class TestRefreshIndexes:
    def test_refresh_generates_all_indexes(self, agent_dir, workspace):
        report = refresh_indexes(agent_dir, workspace)
        assert "file_index" in report["refreshed"]
        assert "symbol_index" in report["refreshed"]
        assert "route_index" in report["refreshed"]
        assert "config_index" in report["refreshed"]
        assert "test_index" in report["refreshed"]
        assert report["errors"] == []

    def test_second_refresh_skips(self, agent_dir, workspace):
        refresh_indexes(agent_dir, workspace)
        report2 = refresh_indexes(agent_dir, workspace)
        assert len(report2["skipped"]) == 5
        assert len(report2["refreshed"]) == 0


# ── Format Indexes Tests ──

class TestFormatIndexes:
    def test_format_includes_routes(self, agent_dir, workspace):
        refresh_indexes(agent_dir, workspace)
        indexes = load_all_indexes(agent_dir)
        text = format_indexes_for_prompt(indexes)
        assert "Routes" in text or "route" in text.lower()

    def test_format_includes_file_distribution(self, agent_dir, workspace):
        refresh_indexes(agent_dir, workspace)
        indexes = load_all_indexes(agent_dir)
        text = format_indexes_for_prompt(indexes)
        # Should have some content
        assert len(text) > 20


# ── Integration: Artifacts + Indexes Together ──

class TestIntegration:
    def test_full_intake_pipeline(self, agent_dir, workspace):
        """End-to-end: refresh both artifacts and indexes, format for prompt."""
        art_report = refresh_artifacts(agent_dir, workspace)
        idx_report = refresh_indexes(agent_dir, workspace)

        assert art_report["errors"] == []
        assert idx_report["errors"] == []

        artifacts = load_all_artifacts(agent_dir)
        indexes = load_all_indexes(agent_dir)

        art_text = format_artifacts_for_prompt(artifacts)
        idx_text = format_indexes_for_prompt(indexes)

        # Combined text should be reasonable size
        combined = art_text + "\n\n" + idx_text
        assert len(combined) < 10000  # not too large
        assert len(combined) > 100  # not empty
