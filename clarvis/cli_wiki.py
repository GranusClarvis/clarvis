"""Clarvis Wiki CLI — knowledge vault management.

Subcommands:
    clarvis wiki ingest file <path>
    clarvis wiki ingest url <url>
    clarvis wiki query "question"
    clarvis wiki lint
    clarvis wiki rebuild-index
    clarvis wiki backfill
    clarvis wiki compile
    clarvis wiki sync
    clarvis wiki status
"""

import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts" / "wiki"


def _run(script: str, args: list[str], check: bool = True) -> int:
    """Run a wiki script, forwarding stdout/stderr."""
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    result = subprocess.run(cmd, cwd=str(SCRIPTS.parent))
    if check and result.returncode != 0:
        raise typer.Exit(result.returncode)
    return result.returncode


# ── ingest ────────────────────────────────────────────────────

ingest_app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
app.add_typer(ingest_app, name="ingest", help="Ingest sources into the knowledge vault.")


@ingest_app.command("file")
def ingest_file(
    path: str = typer.Argument(..., help="Path to file to ingest"),
    type: str = typer.Option("paper", "--type", "-t", help="Source type: paper|web|repo|transcript|image"),
):
    """Ingest a local file into raw sources."""
    _run("wiki_ingest.py", ["file", path, "--type", type])


@ingest_app.command("url")
def ingest_url(
    url: str = typer.Argument(..., help="URL to capture"),
    type: str = typer.Option("web", "--type", "-t", help="Source type"),
):
    """Capture a web URL as a raw source."""
    _run("wiki_ingest.py", ["url", url, "--type", type])


@ingest_app.command("repo")
def ingest_repo(
    repo: str = typer.Argument(..., help="GitHub URL or local repo path"),
    title: str = typer.Option(None, "--title", help="Override title"),
):
    """Ingest a GitHub repository."""
    args = ["repo", repo]
    if title:
        args += ["--title", title]
    _run("wiki_ingest.py", args)


@ingest_app.command("paper")
def ingest_paper(
    path: str = typer.Argument(..., help="Path to PDF"),
    title: str = typer.Option(None, "--title", help="Paper title"),
    arxiv_url: str = typer.Option(None, "--arxiv-url", help="arXiv URL"),
):
    """Ingest an academic paper."""
    args = ["paper", path]
    if title:
        args += ["--title", title]
    if arxiv_url:
        args += ["--arxiv-url", arxiv_url]
    _run("wiki_ingest.py", args)


@ingest_app.command("registry")
def ingest_registry(
    action: str = typer.Argument("list", help="list|stats|get"),
    source_id: str = typer.Argument(None, help="Source ID (for get)"),
    status: str = typer.Option(None, "--status", help="Filter: pending|ingested|failed"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max entries"),
):
    """Query the source registry."""
    args = ["registry", action]
    if source_id:
        args.append(source_id)
    if status:
        args += ["--status", status]
    args += ["--limit", str(limit)]
    _run("wiki_ingest.py", args)


# ── drop (operator source drop) ──────────────────────────────

@app.command("drop")
def drop(
    source: str = typer.Argument(..., help="File path or URL to ingest"),
    type: str = typer.Option(None, "--type", "-t", help="Source type: paper|web|repo|transcript|image"),
    title: str = typer.Option(None, "--title", help="Override title"),
):
    """Drop a source into the wiki — operator shortcut for ingest + compile.

    Accepts file paths, URLs, or GitHub repo URLs. The operator's intent
    to ingest acts as the promotion gate — no further qualification needed.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(SCRIPTS))
        from wiki_hooks import operator_drop
        result = operator_drop(source, source_type=type, title=title)
        if "error" in result:
            typer.echo(f"Error: {result['error']}", err=True)
            raise typer.Exit(1)
        typer.echo(f"Ingested: {result.get('source_id', 'unknown')}")
        typer.echo(f"Raw path: {result.get('raw_path', 'n/a')}")
        typer.echo(f"Title: {result.get('title', 'n/a')}")
        # Auto-compile
        typer.echo("\nCompiling to wiki page...")
        sid = result.get("source_id")
        if sid:
            _run("wiki_compile.py", ["compile", "--source-id", sid], check=False)
    except ImportError:
        typer.echo("wiki_hooks module not available — falling back to raw ingest", err=True)
        args = ["file", source]
        if type:
            args += ["--type", type]
        _run("wiki_ingest.py", args)


# ── query ─────────────────────────────────────────────────────

@app.command("query")
def query(
    question: str = typer.Argument(..., help="Research question to answer"),
    type: str = typer.Option("question", "--type", "-t", help="Output type: question|synthesis"),
):
    """Answer a research question from wiki + raw sources."""
    _run("wiki_query.py", ["ask", question, "--type", type])


@app.command("list-answers")
def list_answers():
    """List saved question answers."""
    _run("wiki_query.py", ["list"])


@app.command("show")
def show(slug: str = typer.Argument(..., help="Answer slug to display")):
    """Show a saved answer by slug."""
    _run("wiki_query.py", ["show", slug])


# ── lint ──────────────────────────────────────────────────────

@app.command("lint")
def lint(
    check: str = typer.Option(None, "--check", "-c", help="Single check: orphans|broken_links|..."),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Run wiki lint checks."""
    args = ["lint"]
    if check:
        args += ["--check", check]
    if json_output:
        args.append("--json")
    _run("wiki_lint.py", args)


@app.command("lint-summary")
def lint_summary():
    """Quick lint summary counts."""
    _run("wiki_lint.py", ["summary"])


# ── rebuild-index ─────────────────────────────────────────────

@app.command("rebuild-index")
def rebuild_index(
    section: str = typer.Option(None, "--section", "-s", help="Rebuild only one section"),
):
    """Regenerate all wiki index pages."""
    args = ["rebuild"]
    if section:
        args += ["--section", section]
    _run("wiki_index.py", args)


# ── compile ───────────────────────────────────────────────────

@app.command("compile")
def compile(
    source_id: str = typer.Option(None, "--source-id", help="Compile a specific source"),
    all_pending: bool = typer.Option(False, "--all-pending", help="Compile all pending sources"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
):
    """Compile raw sources into wiki pages."""
    args = ["compile"]
    if source_id:
        args += ["--source-id", source_id]
    if all_pending:
        args.append("--all-pending")
    if dry_run:
        args.append("--dry-run")
    _run("wiki_ingest.py", args)


# ── backfill ──────────────────────────────────────────────────

@app.command("backfill")
def backfill(
    action: str = typer.Argument("scan", help="scan|run"),
    limit: int = typer.Option(30, "--limit", "-n", help="Max items to process"),
    compile_only: bool = typer.Option(False, "--compile-only", help="Only compile already-ingested"),
):
    """Backfill knowledge from existing research/docs."""
    args = [action]
    if action == "run":
        args += ["--limit", str(limit)]
        if compile_only:
            args.append("--compile-only")
    _run("wiki_backfill.py", args)


# ── sync ──────────────────────────────────────────────────────

@app.command("sync")
def sync(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
):
    """Sync wiki pages to ClarvisDB brain."""
    args = []
    if dry_run:
        args.append("--dry-run")
    rc = _run("wiki_brain_sync.py", args, check=False)
    if rc != 0:
        typer.echo("Sync completed with warnings.", err=True)


# ── status ────────────────────────────────────────────────────

# ── maintenance ────────────────────────────────────────────────

@app.command("maintenance")
def maintenance(
    job: str = typer.Argument("full", help="Job: lint|drift|promote|full"),
    limit: int = typer.Option(5, "--limit", "-n", help="Promotion limit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
):
    """Run wiki maintenance: lint, drift detection, research promotion."""
    args = [job]
    if limit != 5:
        args += ["--limit", str(limit)]
    if dry_run:
        args.append("--dry-run")
    _run("wiki_maintenance.py", args)


# ── status ────────────────────────────────────────────────────

@app.command("status")
def status():
    """Show wiki vault status: page counts, lint summary, index freshness."""
    from pathlib import Path as P
    import os
    import datetime

    knowledge = P(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")) / "knowledge"
    wiki = knowledge / "wiki"

    sections = ["concepts", "projects", "people", "syntheses", "questions", "timelines", "procedures"]
    total = 0
    typer.echo("=== Clarvis Knowledge Vault Status ===\n")
    typer.echo("Wiki pages:")
    for sec in sections:
        d = wiki / sec
        if d.is_dir():
            pages = [f for f in d.glob("*.md") if f.name != "index.md"]
            count = len(pages)
            total += count
            typer.echo(f"  {sec:15s} {count:3d} pages")
    typer.echo(f"  {'TOTAL':15s} {total:3d} pages\n")

    # Raw source counts
    raw = knowledge / "raw"
    typer.echo("Raw sources:")
    for sub in sorted(raw.iterdir()):
        if sub.is_dir() and sub.name != "attachments":
            files = list(sub.glob("*.md"))
            typer.echo(f"  {sub.name:15s} {len(files):3d} files")

    # Source registry count
    sources_jsonl = knowledge / "logs" / "sources.jsonl"
    if sources_jsonl.exists():
        line_count = sum(1 for _ in open(sources_jsonl))
        typer.echo(f"\nSource registry: {line_count} entries")

    # Last lint
    lint_log = knowledge / "logs" / "lint-log.md"
    if lint_log.exists():
        mtime = datetime.datetime.fromtimestamp(lint_log.stat().st_mtime)
        age = datetime.datetime.now() - mtime
        typer.echo(f"Last lint: {mtime.strftime('%Y-%m-%d %H:%M')} ({age.seconds // 3600}h ago)")

    typer.echo()
