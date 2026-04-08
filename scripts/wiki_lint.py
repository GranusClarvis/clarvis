#!/usr/bin/env python3
"""Wiki lint engine — check wiki health and catch common issues.

Checks:
  - Orphan pages (no inbound links from other wiki pages)
  - Broken links (links to nonexistent files)
  - Missing citations (claims without [Source: ...] markers)
  - Duplicate concepts (multiple pages covering the same topic)
  - Stale summaries (pages not updated in >90 days)
  - Oversized pages (>8000 chars body)
  - Underspecified pages (body <200 chars)
  - Source pages lacking wiki coverage (ingested but not compiled)

Usage:
    python3 wiki_lint.py lint                    # Full lint run
    python3 wiki_lint.py lint --check orphans    # Single check
    python3 wiki_lint.py lint --json             # JSON output
    python3 wiki_lint.py summary                 # Quick summary counts
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
WIKI_DIR = KNOWLEDGE / "wiki"
RAW_DIR = KNOWLEDGE / "raw"
LOGS_DIR = KNOWLEDGE / "logs"
SOURCES_JSONL = LOGS_DIR / "sources.jsonl"
TODAY = datetime.date.today()


# ============================================================
# Frontmatter parser (shared with wiki_compile)
# ============================================================

def _parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm_text = text[3:end].strip()
    result = {}
    current_key = None
    current_list = None
    for line in fm_text.split("\n"):
        if line.strip().startswith("- ") and current_key:
            val = line.strip()[2:].strip().strip('"').strip("'")
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(val)
            continue
        m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)', line)
        if m:
            current_key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            current_list = None
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
                result[current_key] = items
            elif val:
                result[current_key] = val
            else:
                result[current_key] = ""
                current_list = []
                result[current_key] = current_list
    return result


def _get_body(text: str) -> str:
    """Return text after frontmatter."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].strip()


# ============================================================
# Page scanner
# ============================================================

def scan_pages() -> dict[str, dict]:
    """Scan all wiki pages. Returns {rel_path: {path, slug, title, fm, body, links_out}}."""
    pages = {}
    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if not fm:
            continue
        if fm.get("redirect"):
            continue

        rel = str(md_file.relative_to(WIKI_DIR))
        body = _get_body(text)
        slug = fm.get("slug", md_file.stem)

        # Extract outbound wiki links
        links_out = set()
        for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', text):
            target = m.group(2)
            if target.endswith(".md") and not target.startswith("http"):
                # Resolve relative path
                resolved = (md_file.parent / target).resolve()
                if str(resolved).startswith(str(WIKI_DIR)):
                    links_out.add(str(resolved.relative_to(WIKI_DIR)))

        pages[rel] = {
            "path": md_file,
            "slug": slug,
            "title": fm.get("title", slug),
            "type": fm.get("type", "concept"),
            "fm": fm,
            "body": body,
            "body_len": len(body),
            "links_out": links_out,
            "updated": fm.get("updated", ""),
            "sources": fm.get("sources", []),
            "status": fm.get("status", "draft"),
            "tags": fm.get("tags", []),
        }
    return pages


# ============================================================
# Individual lint checks
# ============================================================

class LintIssue:
    """A single lint finding."""
    def __init__(self, check: str, severity: str, page: str, message: str):
        self.check = check
        self.severity = severity  # error, warning, info
        self.page = page
        self.message = message

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "page": self.page,
            "message": self.message,
        }

    def __str__(self) -> str:
        icon = {"error": "!", "warning": "~", "info": "·"}.get(self.severity, "?")
        return f"  [{icon}] {self.check:22s} {self.page:45s} {self.message}"


def check_orphans(pages: dict) -> list[LintIssue]:
    """Find pages with no inbound links."""
    issues = []
    # Build inbound link set
    linked_to = set()
    for rel, info in pages.items():
        linked_to.update(info["links_out"])

    for rel, info in pages.items():
        if rel not in linked_to:
            issues.append(LintIssue(
                "orphan_page", "warning", rel,
                f"No inbound links — '{info['title']}'"
            ))
    return issues


def check_broken_links(pages: dict) -> list[LintIssue]:
    """Find links pointing to nonexistent files."""
    issues = []
    for rel, info in pages.items():
        text = info["path"].read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', text):
            target = m.group(2)
            if target.startswith("http") or target.startswith("#"):
                continue
            if not target.endswith(".md"):
                continue
            resolved = (info["path"].parent / target).resolve()
            if not resolved.exists():
                issues.append(LintIssue(
                    "broken_link", "error", rel,
                    f"Broken link: {target}"
                ))
    return issues


def check_missing_citations(pages: dict) -> list[LintIssue]:
    """Find pages with claims but no citation markers."""
    issues = []
    for rel, info in pages.items():
        body = info["body"]
        # Look for Key Claims section
        in_claims = False
        claim_count = 0
        cited_count = 0
        for line in body.split("\n"):
            if line.strip() == "## Key Claims":
                in_claims = True
                continue
            if in_claims:
                if line.startswith("## "):
                    break
                stripped = line.strip()
                if stripped.startswith("- ") and not stripped.startswith("- _"):
                    claim_count += 1
                    if "[Source:" in stripped or "[source:" in stripped or "](../" in stripped:
                        cited_count += 1

        if claim_count > 0 and cited_count < claim_count:
            uncited = claim_count - cited_count
            issues.append(LintIssue(
                "missing_citation", "warning", rel,
                f"{uncited}/{claim_count} claims lack citation markers"
            ))
    return issues


def check_duplicate_concepts(pages: dict) -> list[LintIssue]:
    """Find pages that may cover the same concept."""
    issues = []
    # Group by normalized title
    title_map: dict[str, list[str]] = {}
    for rel, info in pages.items():
        norm = re.sub(r"[^a-z0-9]", "", info["title"].lower())
        if norm:
            title_map.setdefault(norm, []).append(rel)

    for norm, rels in title_map.items():
        if len(rels) > 1:
            issues.append(LintIssue(
                "duplicate_concept", "warning", rels[0],
                f"Possible duplicate: {', '.join(rels)}"
            ))

    # Also check slug collisions
    slug_map: dict[str, list[str]] = {}
    for rel, info in pages.items():
        slug_map.setdefault(info["slug"], []).append(rel)
    for slug, rels in slug_map.items():
        if len(rels) > 1:
            issues.append(LintIssue(
                "duplicate_slug", "error", rels[0],
                f"Slug collision '{slug}': {', '.join(rels)}"
            ))

    return issues


def check_stale_pages(pages: dict, days: int = 90) -> list[LintIssue]:
    """Find pages not updated in >N days."""
    issues = []
    cutoff = TODAY - datetime.timedelta(days=days)
    for rel, info in pages.items():
        updated = info.get("updated", "")
        if not updated:
            issues.append(LintIssue(
                "stale_page", "info", rel,
                "No 'updated' date in frontmatter"
            ))
            continue
        try:
            updated_date = datetime.date.fromisoformat(updated)
            if updated_date < cutoff:
                age = (TODAY - updated_date).days
                issues.append(LintIssue(
                    "stale_page", "warning", rel,
                    f"Not updated in {age} days (since {updated})"
                ))
        except ValueError:
            pass
    return issues


def check_oversized(pages: dict, max_chars: int = 8000) -> list[LintIssue]:
    """Find pages with excessively long body text."""
    issues = []
    for rel, info in pages.items():
        if info["body_len"] > max_chars:
            issues.append(LintIssue(
                "oversized_page", "warning", rel,
                f"Body is {info['body_len']} chars (max {max_chars})"
            ))
    return issues


def check_underspecified(pages: dict, min_chars: int = 200) -> list[LintIssue]:
    """Find pages with too little content."""
    issues = []
    for rel, info in pages.items():
        if info["body_len"] < min_chars:
            issues.append(LintIssue(
                "underspecified", "warning", rel,
                f"Body is only {info['body_len']} chars (min {min_chars})"
            ))
    return issues


def check_uncovered_sources() -> list[LintIssue]:
    """Find ingested sources that have no linked wiki pages."""
    issues = []
    if not SOURCES_JSONL.exists():
        return issues
    try:
        with open(SOURCES_JSONL) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("status") == "ingested" and not record.get("linked_pages"):
                    sid = record.get("source_id", "?")[:30]
                    title = record.get("title", "?")[:50]
                    issues.append(LintIssue(
                        "uncovered_source", "info", f"source:{sid}",
                        f"Ingested but not compiled: {title}"
                    ))
    except OSError:
        pass
    return issues


# ============================================================
# Lint runner
# ============================================================

ALL_CHECKS = {
    "orphans": check_orphans,
    "broken_links": check_broken_links,
    "missing_citations": check_missing_citations,
    "duplicates": check_duplicate_concepts,
    "stale": check_stale_pages,
    "oversized": check_oversized,
    "underspecified": check_underspecified,
    # uncovered_sources doesn't take pages arg — handled separately
}


def run_lint(checks: list[str] | None = None) -> list[LintIssue]:
    """Run specified lint checks (or all). Returns list of issues."""
    pages = scan_pages()
    all_issues = []

    run_checks = checks or list(ALL_CHECKS.keys()) + ["uncovered_sources"]

    for name in run_checks:
        if name == "uncovered_sources":
            all_issues.extend(check_uncovered_sources())
        elif name in ALL_CHECKS:
            all_issues.extend(ALL_CHECKS[name](pages))

    # Sort: errors first, then warnings, then info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    all_issues.sort(key=lambda i: (severity_order.get(i.severity, 9), i.check, i.page))
    return all_issues


def lint_summary(issues: list[LintIssue]) -> dict:
    """Summarize lint results."""
    by_check: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for issue in issues:
        by_check[issue.check] = by_check.get(issue.check, 0) + 1
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
    return {
        "total": len(issues),
        "by_severity": by_severity,
        "by_check": by_check,
    }


# ============================================================
# Health report generation (Task 3: WIKI_HEALTH_REPORT)
# ============================================================

def generate_health_report(issues: list[LintIssue] | None = None) -> str:
    """Generate a concise health report summarizing wiki state.

    Includes: wiki size, ingest velocity, orphan count, stale count,
    and top suggested repairs. Saved to knowledge/logs/lint-log.md.
    """
    if issues is None:
        issues = run_lint()
    summary = lint_summary(issues)
    pages = scan_pages()

    # Wiki size
    total_pages = len(pages)
    by_type: dict[str, int] = {}
    for info in pages.values():
        t = info.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    total_body_chars = sum(info["body_len"] for info in pages.values())

    # Ingest velocity — count sources ingested in last 7 days
    recent_sources = 0
    total_sources = 0
    seven_days_ago = TODAY - datetime.timedelta(days=7)
    if SOURCES_JSONL.exists():
        try:
            with open(SOURCES_JSONL) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        total_sources += 1
                        ts = record.get("ingested_at", "")[:10]
                        if ts:
                            try:
                                d = datetime.date.fromisoformat(ts)
                                if d >= seven_days_ago:
                                    recent_sources += 1
                            except ValueError:
                                pass
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    # Count issues by category
    orphan_count = summary["by_check"].get("orphan_page", 0)
    stale_count = summary["by_check"].get("stale_page", 0)
    broken_count = summary["by_check"].get("broken_link", 0)
    uncited_count = summary["by_check"].get("missing_citation", 0)
    duplicate_count = summary["by_check"].get("duplicate_concept", 0) + summary["by_check"].get("duplicate_slug", 0)
    uncovered_count = summary["by_check"].get("uncovered_source", 0)
    oversized_count = summary["by_check"].get("oversized_page", 0)
    underspec_count = summary["by_check"].get("underspecified", 0)

    errors = summary["by_severity"].get("error", 0)
    warnings = summary["by_severity"].get("warning", 0)

    # Top repairs
    top_repairs = []
    if errors > 0:
        error_issues = [i for i in issues if i.severity == "error"]
        for i in error_issues[:5]:
            top_repairs.append(f"- **{i.check}**: {i.page} — {i.message}")
    if warnings > 0 and len(top_repairs) < 8:
        warn_issues = [i for i in issues if i.severity == "warning"]
        for i in warn_issues[:5]:
            top_repairs.append(f"- {i.check}: {i.page} — {i.message}")

    # Health grade
    if errors == 0 and warnings <= 3:
        grade = "HEALTHY"
    elif errors == 0 and warnings <= 10:
        grade = "OK"
    elif errors <= 2:
        grade = "NEEDS ATTENTION"
    else:
        grade = "UNHEALTHY"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    type_lines = "\n".join(f"  - {t}: {c}" for t, c in sorted(by_type.items()))

    report = f"""# Wiki Health Report

_Generated {now_str} — Grade: **{grade}**_

## Size
- **{total_pages}** wiki pages ({total_body_chars:,} chars total body text)
{type_lines}
- **{total_sources}** source registry entries

## Ingest Velocity
- **{recent_sources}** sources ingested in last 7 days
- **{uncovered_count}** ingested sources still awaiting wiki compilation

## Quality Summary
| Check | Count | Severity |
|-------|-------|----------|
| Orphan pages | {orphan_count} | warning |
| Broken links | {broken_count} | error |
| Missing citations | {uncited_count} | warning |
| Duplicate concepts | {duplicate_count} | warning |
| Stale pages (>90d) | {stale_count} | warning |
| Oversized pages | {oversized_count} | warning |
| Underspecified pages | {underspec_count} | warning |
| Uncovered sources | {uncovered_count} | info |

**Totals**: {errors} error(s), {warnings} warning(s), {summary['by_severity'].get('info', 0)} info

## Top Suggested Repairs

{chr(10).join(top_repairs) if top_repairs else '_No critical repairs needed._'}

## Trend
_Track this report over time to detect regressions._

---
_Generated by `wiki_lint.py health` — {now_str}_
"""
    return report


# ============================================================
# CLI
# ============================================================

def cmd_lint(args):
    checks = [args.check] if args.check else None
    issues = run_lint(checks)
    summary = lint_summary(issues)

    if args.json:
        output = {
            "issues": [i.to_dict() for i in issues],
            "summary": summary,
        }
        print(json.dumps(output, indent=2))
        return 0

    if not issues:
        print("No issues found.")
        return 0

    for issue in issues:
        print(str(issue))

    print(f"\nSummary: {summary['total']} issue(s) — "
          f"{summary['by_severity'].get('error', 0)} error(s), "
          f"{summary['by_severity'].get('warning', 0)} warning(s), "
          f"{summary['by_severity'].get('info', 0)} info")
    return 1 if summary["by_severity"].get("error", 0) > 0 else 0


def cmd_summary(args):
    issues = run_lint()
    summary = lint_summary(issues)
    pages = scan_pages()
    print(f"Wiki pages: {len(pages)}")
    for check, count in sorted(summary["by_check"].items()):
        print(f"  {check}: {count}")
    grade = "HEALTHY" if summary["by_severity"].get("error", 0) == 0 and summary["by_severity"].get("warning", 0) <= 3 else "NEEDS ATTENTION"
    print(f"\nGrade: {grade}")
    return 0


def cmd_health(args):
    """Generate and save health report."""
    issues = run_lint()
    report = generate_health_report(issues)

    if args.dry_run:
        print(report)
        return 0

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOGS_DIR / "lint-log.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Health report saved: {report_path.relative_to(WORKSPACE)}")

    summary = lint_summary(issues)
    errors = summary["by_severity"].get("error", 0)
    warnings = summary["by_severity"].get("warning", 0)
    print(f"  {len(scan_pages())} pages, {summary['total']} issues "
          f"({errors} errors, {warnings} warnings)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Clarvis wiki lint engine")
    sub = parser.add_subparsers(dest="command")

    p_lint = sub.add_parser("lint", help="Run lint checks on wiki")
    p_lint.add_argument("--check", choices=list(ALL_CHECKS.keys()) + ["uncovered_sources"],
                        help="Run only this check")
    p_lint.add_argument("--json", action="store_true", help="Output as JSON")

    sub.add_parser("summary", help="Quick summary of wiki health")

    p_health = sub.add_parser("health", help="Generate full health report")
    p_health.add_argument("--dry-run", action="store_true", help="Print report without saving")

    args = parser.parse_args()
    handlers = {
        "lint": cmd_lint,
        "summary": cmd_summary,
        "health": cmd_health,
    }
    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
