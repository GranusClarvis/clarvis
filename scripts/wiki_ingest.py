#!/usr/bin/env python3
"""Wiki ingest pipeline — source registry, local file ingest, and web capture.

Handles Layer 1 (raw sources) of the Clarvis knowledge wiki:
  - Registers every ingested asset in knowledge/logs/sources.jsonl
  - Stores raw artifacts in knowledge/raw/{type}/
  - Extracts basic metadata (title, entities, concepts)
  - Proposes destination wiki pages

Usage:
    python3 wiki_ingest.py file <path> [--type paper|web|repo|transcript|image]
    python3 wiki_ingest.py url <url> [--type web]
    python3 wiki_ingest.py repo <github-url-or-local-path> [--title TITLE]
    python3 wiki_ingest.py paper <pdf-path> [--title TITLE] [--arxiv-url URL]
    python3 wiki_ingest.py compile [--source-id ID] [--all-pending] [--dry-run]
    python3 wiki_ingest.py registry list [--status pending|ingested|failed] [--limit N]
    python3 wiki_ingest.py registry stats
    python3 wiki_ingest.py registry get <source_id>
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

# --- Constants ---

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
RAW_DIR = KNOWLEDGE / "raw"
LOGS_DIR = KNOWLEDGE / "logs"
SOURCES_JSONL = LOGS_DIR / "sources.jsonl"
WIKI_DIR = KNOWLEDGE / "wiki"

SOURCE_TYPES = ("paper", "web", "repo", "transcript", "image")
FILE_EXT_TYPE_MAP = {
    ".pdf": "paper",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".svg": "image",
    ".md": "web",  # default for markdown; caller can override
    ".txt": "transcript",
    ".html": "web", ".htm": "web",
}

TODAY = datetime.date.today().isoformat()


# ============================================================
# Source Registry — JSONL read/write for knowledge/logs/sources.jsonl
# ============================================================

class SourceRegistry:
    """Append-only JSONL registry tracking every ingested asset.

    Schema per line (JSON object):
        source_id       str   Deterministic ID: {date}-{type}-{hash8}
        source_url      str   Original URL or absolute file path
        raw_path        str   Relative path under knowledge/ (e.g. raw/web/2026-04-08-web-a1b2c3d4.md)
        ingest_ts       str   ISO-8601 timestamp of ingest
        checksum_sha256 str   SHA-256 hex digest of stored raw file
        source_type     str   paper|web|repo|transcript|image
        status          str   ingested|failed|pending
        title           str   Extracted or supplied title
        file_size       int   Bytes of raw file
        entities        list  Extracted entity strings
        concepts        list  Extracted concept/topic strings
        linked_pages    list  Wiki page slugs this source feeds
        confidence      str   high|medium|low
        meta            dict  Extra metadata (author, date, venue, etc.)
    """

    def __init__(self, path: Path = SOURCES_JSONL):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> None:
        """Append a single record to the registry."""
        with open(self.path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        """Read all records."""
        if not self.path.exists():
            return []
        records = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def find_by_checksum(self, checksum: str) -> dict | None:
        """Check if a file with this checksum was already ingested."""
        for rec in self.read_all():
            if rec.get("checksum_sha256") == checksum:
                return rec
        return None

    def find_by_url(self, url: str) -> dict | None:
        """Check if a URL was already ingested."""
        for rec in self.read_all():
            if rec.get("source_url") == url:
                return rec
        return None

    def find_by_id(self, source_id: str) -> dict | None:
        """Find a record by source_id."""
        for rec in self.read_all():
            if rec.get("source_id") == source_id:
                return rec
        return None

    def stats(self) -> dict:
        """Return summary statistics."""
        records = self.read_all()
        by_type = {}
        by_status = {}
        total_bytes = 0
        for r in records:
            t = r.get("source_type", "unknown")
            s = r.get("status", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1
            total_bytes += r.get("file_size", 0)
        return {
            "total": len(records),
            "by_type": by_type,
            "by_status": by_status,
            "total_bytes": total_bytes,
        }

    def list_filtered(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """List records, optionally filtered by status."""
        records = self.read_all()
        if status:
            records = [r for r in records if r.get("status") == status]
        return records[-limit:]


# ============================================================
# Helpers
# ============================================================

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_source_id(source_type: str, checksum: str, date: str = TODAY) -> str:
    """Deterministic slug: {date}-{type}-{hash8}."""
    return f"{date}-{source_type}-{checksum[:8]}"


def detect_type_from_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    return FILE_EXT_TYPE_MAP.get(ext, "web")


def extract_title_from_markdown(text: str) -> str:
    """Extract first H1 or first non-empty line as title."""
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line and not line.startswith("---"):
            return line[:120]
    return "Untitled"


def extract_title_from_html(html: str) -> str:
    """Extract <title> or first <h1> from HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()[:200]
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)[:200]
    except Exception:
        pass
    m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    return "Untitled"


def extract_entities_heuristic(text: str) -> list[str]:
    """Simple heuristic entity extraction — capitalized multi-word phrases."""
    # Find capitalized phrases (2+ words) that appear to be proper nouns
    candidates = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    # Deduplicate, keep order
    seen = set()
    entities = []
    for c in candidates:
        c_lower = c.lower()
        if c_lower not in seen and len(c) > 4:
            seen.add(c_lower)
            entities.append(c)
    return entities[:20]


def extract_concepts_heuristic(text: str) -> list[str]:
    """Extract likely concept terms — bold/italic phrases, header words, linked terms."""
    concepts = set()
    # Markdown bold
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        t = m.group(1).strip()
        if 3 < len(t) < 80:
            concepts.add(t)
    # Markdown headers
    for m in re.finditer(r"^#{1,3}\s+(.+)$", text, re.MULTILINE):
        t = m.group(1).strip()
        if 3 < len(t) < 80:
            concepts.add(t)
    # Markdown links text
    for m in re.finditer(r"\[([^\]]+)\]\(", text):
        t = m.group(1).strip()
        if 3 < len(t) < 80:
            concepts.add(t)
    return sorted(concepts)[:30]


def propose_wiki_pages(title: str, concepts: list[str], source_type: str) -> list[str]:
    """Propose wiki page slugs that this source could feed."""
    slugs = []
    # Main page from title
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    if slug and len(slug) > 3:
        slugs.append(slug)
    # From top concepts
    for c in concepts[:5]:
        s = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")[:60]
        if s and len(s) > 3 and s not in slugs:
            slugs.append(s)
    return slugs


def html_to_markdown(html: str) -> str:
    """Convert HTML to clean markdown using markdownify + BeautifulSoup."""
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md

    soup = BeautifulSoup(html, "html.parser")
    # Remove script, style, nav, footer, aside elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()
    # Try to find main content area
    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
    target = main if main else soup.body if soup.body else soup
    text = md(str(target), heading_style="ATX", strip=["img"])
    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ============================================================
# Ingest: Local File
# ============================================================

def ingest_file(file_path: str, source_type: str | None = None, title: str | None = None) -> dict:
    """Ingest a local file into knowledge/raw/ and register it.

    Returns the source registry record.
    """
    registry = SourceRegistry()
    src = Path(file_path).resolve()

    if not src.exists():
        return {"error": f"File not found: {file_path}"}

    data = src.read_bytes()
    checksum = compute_sha256(data)

    # Dedup check
    existing = registry.find_by_checksum(checksum)
    if existing:
        return {"error": "duplicate", "existing": existing}

    # Determine type
    if not source_type:
        source_type = detect_type_from_path(str(src))
    if source_type not in SOURCE_TYPES:
        source_type = "web"

    # Determine destination
    source_id = make_source_id(source_type, checksum)
    if source_type == "image":
        ext = src.suffix.lower() or ".png"
        dest_name = f"{source_id}{ext}"
    else:
        dest_name = f"{source_id}.md"

    dest_dir = RAW_DIR / source_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / dest_name

    # For non-markdown text files, just copy; for HTML, convert
    text_content = ""
    if source_type == "image":
        shutil.copy2(src, dest)
    elif src.suffix.lower() in (".html", ".htm"):
        html = data.decode("utf-8", errors="replace")
        if not title:
            title = extract_title_from_html(html)
        text_content = html_to_markdown(html)
        # Prepend metadata header
        header = f"---\nsource: {src}\ntitle: \"{title}\"\ningested: {TODAY}\n---\n\n"
        dest.write_text(header + text_content, encoding="utf-8")
    elif src.suffix.lower() == ".pdf":
        # Store PDF as-is, change dest extension
        dest = dest_dir / f"{source_id}.pdf"
        shutil.copy2(src, dest)
        text_content = f"[PDF file: {src.name}]"
    else:
        # Markdown or text — copy with metadata header
        text_content = data.decode("utf-8", errors="replace")
        if not title:
            title = extract_title_from_markdown(text_content)
        header = f"---\nsource: {src}\ntitle: \"{title}\"\ningested: {TODAY}\n---\n\n"
        dest.write_text(header + text_content, encoding="utf-8")

    if not title:
        title = src.stem.replace("-", " ").replace("_", " ").title()

    # Extract metadata
    entities = extract_entities_heuristic(text_content) if text_content else []
    concepts = extract_concepts_heuristic(text_content) if text_content else []
    proposed = propose_wiki_pages(title, concepts, source_type)

    # Build record
    raw_path = str(dest.relative_to(KNOWLEDGE))
    record = {
        "source_id": source_id,
        "source_url": str(src),
        "raw_path": raw_path,
        "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checksum_sha256": checksum,
        "source_type": source_type,
        "status": "ingested",
        "title": title,
        "file_size": len(data),
        "entities": entities,
        "concepts": concepts,
        "linked_pages": [],
        "proposed_pages": proposed,
        "confidence": "medium",
        "meta": {},
    }

    registry.append(record)
    return record


# ============================================================
# Ingest: Web Capture
# ============================================================

def ingest_url(url: str, source_type: str = "web", title: str | None = None) -> dict:
    """Fetch a URL, convert to markdown, store as raw artifact, and register.

    Returns the source registry record.
    """
    import requests

    registry = SourceRegistry()

    # Dedup check by URL
    existing = registry.find_by_url(url)
    if existing:
        return {"error": "duplicate_url", "existing": existing}

    # Fetch
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ClarvisBot/1.0; +https://github.com/GranusClarvis/clarvis)"
        }
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        # Register the failure
        record = {
            "source_id": make_source_id("web", hashlib.sha256(url.encode()).hexdigest()),
            "source_url": url,
            "raw_path": "",
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": "",
            "source_type": source_type,
            "status": "failed",
            "title": title or url,
            "file_size": 0,
            "entities": [],
            "concepts": [],
            "linked_pages": [],
            "proposed_pages": [],
            "confidence": "low",
            "meta": {"error": str(e)},
        }
        registry.append(record)
        return record

    content_type = resp.headers.get("Content-Type", "")
    raw_bytes = resp.content
    checksum = compute_sha256(raw_bytes)

    # Dedup by content
    existing = registry.find_by_checksum(checksum)
    if existing:
        return {"error": "duplicate", "existing": existing}

    source_id = make_source_id(source_type, checksum)

    # Handle images
    if "image/" in content_type:
        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/svg+xml": ".svg"}
        ext = ext_map.get(content_type.split(";")[0].strip(), ".png")
        dest_dir = RAW_DIR / "images"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{source_id}{ext}"
        dest.write_bytes(raw_bytes)

        record = {
            "source_id": source_id,
            "source_url": url,
            "raw_path": str(dest.relative_to(KNOWLEDGE)),
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "source_type": "image",
            "status": "ingested",
            "title": title or Path(urllib.parse.urlparse(url).path).stem or "image",
            "file_size": len(raw_bytes),
            "entities": [],
            "concepts": [],
            "linked_pages": [],
            "proposed_pages": [],
            "confidence": "medium",
            "meta": {"content_type": content_type, "url": url},
        }
        registry.append(record)
        return record

    # Handle PDF
    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        dest_dir = RAW_DIR / "papers"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{source_id}.pdf"
        dest.write_bytes(raw_bytes)

        record = {
            "source_id": source_id,
            "source_url": url,
            "raw_path": str(dest.relative_to(KNOWLEDGE)),
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "source_type": "paper",
            "status": "ingested",
            "title": title or Path(urllib.parse.urlparse(url).path).stem or "paper",
            "file_size": len(raw_bytes),
            "entities": [],
            "concepts": [],
            "linked_pages": [],
            "proposed_pages": [],
            "confidence": "medium",
            "meta": {"content_type": content_type, "url": url},
        }
        registry.append(record)
        return record

    # Handle HTML / text — convert to markdown
    html = raw_bytes.decode("utf-8", errors="replace")

    if not title:
        title = extract_title_from_html(html)

    md_content = html_to_markdown(html)

    # Extract URL metadata
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc

    # Build raw file with frontmatter
    header_lines = [
        "---",
        f'source_url: "{url}"',
        f'title: "{title}"',
        f'domain: "{domain}"',
        f"captured: {TODAY}",
        f'ingested: {datetime.datetime.now(datetime.timezone.utc).isoformat()}',
        "---",
        "",
    ]
    full_content = "\n".join(header_lines) + md_content

    dest_dir = RAW_DIR / "web"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{source_id}.md"
    dest.write_text(full_content, encoding="utf-8")

    # Extract metadata
    entities = extract_entities_heuristic(md_content)
    concepts = extract_concepts_heuristic(md_content)
    proposed = propose_wiki_pages(title, concepts, source_type)

    record = {
        "source_id": source_id,
        "source_url": url,
        "raw_path": str(dest.relative_to(KNOWLEDGE)),
        "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checksum_sha256": checksum,
        "source_type": source_type,
        "status": "ingested",
        "title": title,
        "file_size": len(full_content.encode("utf-8")),
        "entities": entities,
        "concepts": concepts,
        "linked_pages": [],
        "proposed_pages": proposed,
        "confidence": "medium",
        "meta": {
            "domain": domain,
            "content_type": content_type,
            "url": url,
            "captured_date": TODAY,
        },
    }

    registry.append(record)
    return record


# ============================================================
# Ingest: Repository (GitHub URL or local path)
# ============================================================

def _clone_or_locate_repo(repo_ref: str) -> tuple[Path, str, bool]:
    """Resolve a repo reference to a local directory.

    Returns (local_path, canonical_url, is_temp_clone).
    """
    import subprocess
    import tempfile

    # GitHub URL patterns
    gh_match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo_ref)
    if gh_match:
        url = f"https://github.com/{gh_match.group(1)}.git"
        tmp = Path(tempfile.mkdtemp(prefix="clarvis_repo_"))
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", url, str(tmp / "repo")],
            capture_output=True, timeout=120, check=True,
        )
        return tmp / "repo", f"https://github.com/{gh_match.group(1)}", True

    # Local directory
    local = Path(repo_ref).resolve()
    if local.is_dir():
        # Try to extract remote URL
        try:
            result = subprocess.run(
                ["git", "-C", str(local), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=10,
            )
            origin = result.stdout.strip() if result.returncode == 0 else str(local)
        except Exception:
            origin = str(local)
        return local, origin, False

    raise ValueError(f"Cannot resolve repo: {repo_ref} (not a GitHub URL or local directory)")


def _analyze_repo_structure(repo_path: Path) -> dict:
    """Analyze a repo directory and return structured metadata.

    Returns dict with keys: readme, structure, languages, notable_files,
    file_count, dir_count, top_dirs, description.
    """
    import subprocess

    result = {
        "readme": "",
        "structure": "",
        "languages": [],
        "notable_files": [],
        "file_count": 0,
        "dir_count": 0,
        "top_dirs": [],
        "description": "",
    }

    # Read README
    for name in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
        readme_path = repo_path / name
        if readme_path.exists():
            try:
                result["readme"] = readme_path.read_text(encoding="utf-8", errors="replace")[:15000]
            except Exception:
                pass
            break

    # Count files and dirs, detect languages
    ext_counts: dict[str, int] = {}
    notable_names = {
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "Makefile", "Cargo.toml", "go.mod", "package.json", "pyproject.toml",
        "setup.py", "setup.cfg", "requirements.txt", "tsconfig.json",
        ".github/workflows", "LICENSE", "CONTRIBUTING.md",
    }
    notable_found = []

    try:
        # Use git ls-files if available, else walk
        ls_result = subprocess.run(
            ["git", "-C", str(repo_path), "ls-files"],
            capture_output=True, text=True, timeout=15,
        )
        if ls_result.returncode == 0:
            files = [f for f in ls_result.stdout.strip().split("\n") if f]
        else:
            files = []
            for root, dirs, fnames in os.walk(repo_path):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "vendor")]
                for fn in fnames:
                    files.append(os.path.relpath(os.path.join(root, fn), repo_path))
    except Exception:
        files = []

    dirs_seen = set()
    for f in files:
        result["file_count"] += 1
        parts = Path(f).parts
        if len(parts) > 1:
            dirs_seen.add(parts[0])
        ext = Path(f).suffix.lower()
        if ext:
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        basename = Path(f).name
        if basename in notable_names or f.startswith(".github/workflows"):
            notable_found.append(f)

    result["dir_count"] = len(dirs_seen)
    result["top_dirs"] = sorted(dirs_seen)[:20]
    result["notable_files"] = notable_found[:15]

    # Detect languages from extensions
    ext_to_lang = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".c": "C",
        ".cpp": "C++", ".cs": "C#", ".swift": "Swift", ".kt": "Kotlin",
        ".sol": "Solidity", ".sh": "Shell", ".lua": "Lua", ".zig": "Zig",
        ".ex": "Elixir", ".hs": "Haskell", ".ml": "OCaml", ".php": "PHP",
    }
    lang_counts = {}
    for ext, count in ext_counts.items():
        lang = ext_to_lang.get(ext)
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + count
    result["languages"] = [lang for lang, _ in sorted(lang_counts.items(), key=lambda x: -x[1])][:5]

    # Build structure summary (top-level tree)
    tree_lines = []
    for d in sorted(dirs_seen)[:15]:
        tree_lines.append(f"  {d}/")
    root_files = [Path(f).name for f in files if "/" not in f and "\\" not in f]
    for rf in sorted(root_files)[:10]:
        tree_lines.append(f"  {rf}")
    result["structure"] = "\n".join(tree_lines)

    # Extract description from README first paragraph
    if result["readme"]:
        lines = result["readme"].split("\n")
        desc_lines = []
        started = False
        for line in lines:
            stripped = line.strip()
            if not started:
                if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                    started = True
                    desc_lines.append(stripped)
            else:
                if not stripped:
                    break
                desc_lines.append(stripped)
        result["description"] = " ".join(desc_lines)[:500]

    return result


def ingest_repo(repo_ref: str, title: str | None = None) -> dict:
    """Ingest a GitHub repo URL or local repo path.

    Clones (shallow) if GitHub URL. Analyzes structure, README, notable files.
    Stores a structured markdown analysis in knowledge/raw/repos/.
    Returns the source registry record.
    """
    import shutil as _shutil

    registry = SourceRegistry()

    # Dedup by URL
    existing = registry.find_by_url(repo_ref)
    if existing:
        return {"error": "duplicate_url", "existing": existing}

    # Resolve repo
    try:
        repo_path, canonical_url, is_temp = _clone_or_locate_repo(repo_ref)
    except Exception as e:
        record = {
            "source_id": make_source_id("repo", hashlib.sha256(repo_ref.encode()).hexdigest()),
            "source_url": repo_ref,
            "raw_path": "",
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": "",
            "source_type": "repo",
            "status": "failed",
            "title": title or repo_ref,
            "file_size": 0,
            "entities": [],
            "concepts": [],
            "linked_pages": [],
            "proposed_pages": [],
            "confidence": "low",
            "meta": {"error": str(e)},
        }
        registry.append(record)
        return record

    try:
        analysis = _analyze_repo_structure(repo_path)

        if not title:
            title = Path(canonical_url.rstrip("/")).name.replace(".git", "") if canonical_url.startswith("http") else repo_path.name

        # Build raw analysis markdown
        readme_section = analysis["readme"][:8000] if analysis["readme"] else "_No README found._"
        langs = ", ".join(analysis["languages"]) if analysis["languages"] else "Unknown"
        notable = "\n".join(f"- `{f}`" for f in analysis["notable_files"]) if analysis["notable_files"] else "- _None detected_"
        struct = analysis["structure"] or "_Empty_"
        description = analysis["description"] or "_No description extracted._"

        md_content = f"""---
source_url: "{canonical_url}"
title: "{title}"
source_type: repo
ingested: {TODAY}
languages: [{langs}]
file_count: {analysis['file_count']}
dir_count: {analysis['dir_count']}
---

# {title}

{description}

## Repository Structure

```
{struct}
```

**Files**: {analysis['file_count']} | **Top-level dirs**: {analysis['dir_count']} | **Languages**: {langs}

## Notable Files

{notable}

## README (truncated)

{readme_section}

## Open Questions

- What are the main architectural decisions and trade-offs?
- How does this relate to Clarvis's architecture or goals?
- Are there reusable patterns or libraries worth adopting?
"""

        # Checksum the analysis content
        content_bytes = md_content.encode("utf-8")
        checksum = compute_sha256(content_bytes)

        # Check content dedup
        existing = registry.find_by_checksum(checksum)
        if existing:
            return {"error": "duplicate", "existing": existing}

        source_id = make_source_id("repo", checksum)
        dest_dir = RAW_DIR / "repos"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{source_id}.md"
        dest.write_text(md_content, encoding="utf-8")

        # Extract metadata
        entities = extract_entities_heuristic(md_content)
        concepts = extract_concepts_heuristic(md_content)
        proposed = propose_wiki_pages(title, concepts, "repo")

        raw_path = str(dest.relative_to(KNOWLEDGE))
        record = {
            "source_id": source_id,
            "source_url": repo_ref,
            "raw_path": raw_path,
            "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "source_type": "repo",
            "status": "ingested",
            "title": title,
            "file_size": len(content_bytes),
            "entities": entities,
            "concepts": concepts,
            "linked_pages": [],
            "proposed_pages": proposed,
            "confidence": "medium",
            "meta": {
                "canonical_url": canonical_url,
                "languages": analysis["languages"],
                "file_count": analysis["file_count"],
                "dir_count": analysis["dir_count"],
                "notable_files": analysis["notable_files"],
                "top_dirs": analysis["top_dirs"],
            },
        }
        registry.append(record)
        return record

    finally:
        # Clean up temp clone
        if is_temp:
            parent = repo_path.parent
            try:
                _shutil.rmtree(parent, ignore_errors=True)
            except Exception:
                pass


# ============================================================
# Ingest: Paper / PDF
# ============================================================

def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF file. Tries PyMuPDF, then pdfplumber, then falls back to filename."""
    # Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        pages = []
        for i, page in enumerate(doc):
            if i >= 30:  # Limit to first 30 pages
                break
            pages.append(page.get_text())
        doc.close()
        text = "\n\n".join(pages)
        if text.strip():
            return text[:50000]
    except ImportError:
        pass
    except Exception:
        pass

    # Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages):
                if i >= 30:
                    break
                t = page.extract_text()
                if t:
                    pages.append(t)
            text = "\n\n".join(pages)
            if text.strip():
                return text[:50000]
    except ImportError:
        pass
    except Exception:
        pass

    return ""


def _extract_paper_metadata(text: str, filename: str = "") -> dict:
    """Extract paper metadata from text: title, authors, abstract, year."""
    meta: dict = {"title": "", "authors": [], "abstract": "", "year": "", "arxiv": ""}

    lines = text.split("\n")
    non_empty = [l.strip() for l in lines if l.strip()]

    # Title: usually the first non-empty line or first long line
    if non_empty:
        meta["title"] = non_empty[0][:200]

    # ArXiv ID from text or filename
    arxiv_match = re.search(r"(\d{4}\.\d{4,5})", text[:5000])
    if arxiv_match:
        meta["arxiv"] = arxiv_match.group(1)
    elif filename:
        arxiv_match = re.search(r"(\d{4}\.\d{4,5})", filename)
        if arxiv_match:
            meta["arxiv"] = arxiv_match.group(1)

    # Abstract
    abs_match = re.search(r"(?:Abstract|ABSTRACT)[:\s]*\n?(.*?)(?:\n\s*\n|\n(?:1[\.\s]|Introduction|INTRODUCTION))", text[:10000], re.DOTALL)
    if abs_match:
        meta["abstract"] = abs_match.group(1).strip()[:2000]

    # Year
    year_match = re.search(r"(20[12]\d)", text[:3000])
    if year_match:
        meta["year"] = year_match.group(1)

    # Authors heuristic: lines between title and abstract that contain commas or "and"
    if len(non_empty) > 1:
        for i, line in enumerate(non_empty[1:6], 1):
            if ("," in line or " and " in line.lower()) and len(line) < 500:
                if not any(kw in line.lower() for kw in ("abstract", "introduction", "keywords", "http")):
                    meta["authors"].append(line)

    return meta


def ingest_paper(file_path: str, title: str | None = None, arxiv_url: str | None = None) -> dict:
    """Ingest a PDF paper: store PDF, extract text, create markdown summary.

    Returns the source registry record.
    """
    registry = SourceRegistry()
    src = Path(file_path).resolve()

    if not src.exists():
        return {"error": f"File not found: {file_path}"}

    data = src.read_bytes()
    checksum = compute_sha256(data)

    # Dedup
    existing = registry.find_by_checksum(checksum)
    if existing:
        return {"error": "duplicate", "existing": existing}

    source_id = make_source_id("paper", checksum)

    # Store the PDF itself
    pdf_dir = RAW_DIR / "papers"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_dest = pdf_dir / f"{source_id}.pdf"
    shutil.copy2(src, pdf_dest)

    # Extract text and metadata
    extracted_text = _extract_pdf_text(src)
    meta = _extract_paper_metadata(extracted_text, src.name)

    if not title:
        title = meta["title"] or src.stem.replace("-", " ").replace("_", " ").title()

    abstract = meta["abstract"] or "_No abstract extracted. Manual review recommended._"
    authors_str = "; ".join(meta["authors"][:5]) if meta["authors"] else "_Unknown_"
    year = meta["year"] or TODAY[:4]
    arxiv_id = meta["arxiv"] or ""

    # Build markdown summary alongside the PDF
    md_content = f"""---
source_url: "{arxiv_url or str(src)}"
title: "{title}"
source_type: paper
ingested: {TODAY}
pdf_path: "raw/papers/{source_id}.pdf"
authors: "{authors_str}"
year: {year}
arxiv: "{arxiv_id}"
---

# {title}

**Authors**: {authors_str}
**Year**: {year}
{f'**ArXiv**: {arxiv_id}' if arxiv_id else ''}
{f'**URL**: {arxiv_url}' if arxiv_url else ''}

## Abstract

{abstract}

## Key Claims

- _Extracted claims pending manual review._

## Relevance to Clarvis

- _To be assessed during wiki compilation._

## Open Questions

- What are the main limitations acknowledged by the authors?
- Which claims are directly testable in Clarvis's architecture?
- Are there follow-up papers or implementations to track?

## Extracted Text (first 3000 chars)

{extracted_text[:3000] if extracted_text else '_PDF text extraction failed. Install PyMuPDF (`pip install pymupdf`) for extraction._'}
"""

    # Store the markdown summary
    paper_dir = RAW_DIR / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    md_dest = paper_dir / f"{source_id}.md"
    md_dest.write_text(md_content, encoding="utf-8")

    # Extract metadata from the markdown
    entities = extract_entities_heuristic(md_content)
    concepts = extract_concepts_heuristic(md_content)
    proposed = propose_wiki_pages(title, concepts, "paper")

    raw_path = str(md_dest.relative_to(KNOWLEDGE))
    record = {
        "source_id": source_id,
        "source_url": arxiv_url or str(src),
        "raw_path": raw_path,
        "ingest_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checksum_sha256": checksum,
        "source_type": "paper",
        "status": "ingested",
        "title": title,
        "file_size": len(data),
        "entities": entities,
        "concepts": concepts,
        "linked_pages": [],
        "proposed_pages": proposed,
        "confidence": "medium",
        "meta": {
            "pdf_path": f"raw/papers/{source_id}.pdf",
            "authors": meta["authors"][:5],
            "year": year,
            "arxiv": arxiv_id,
            "has_extracted_text": bool(extracted_text),
        },
    }

    registry.append(record)
    return record


# ============================================================
# CLI
# ============================================================

def cmd_file(args):
    result = ingest_file(args.path, source_type=args.type, title=args.title)
    if "error" in result:
        if result["error"] == "duplicate":
            print(f"SKIP: Already ingested as {result['existing']['source_id']}")
            return 1
        if result["error"] == "duplicate_url":
            print(f"SKIP: URL already ingested as {result['existing']['source_id']}")
            return 1
        print(f"ERROR: {result['error']}")
        return 1
    print(f"OK: Ingested {result['source_id']}")
    print(f"  Raw: {result['raw_path']}")
    print(f"  Title: {result['title']}")
    print(f"  Type: {result['source_type']}")
    print(f"  SHA256: {result['checksum_sha256'][:16]}...")
    if result.get("concepts"):
        print(f"  Concepts: {', '.join(result['concepts'][:8])}")
    if result.get("proposed_pages"):
        print(f"  Proposed pages: {', '.join(result['proposed_pages'][:5])}")
    return 0


def cmd_url(args):
    result = ingest_url(args.url, source_type=args.type or "web", title=args.title)
    if "error" in result:
        if result["error"] in ("duplicate", "duplicate_url"):
            print(f"SKIP: Already ingested as {result['existing']['source_id']}")
            return 1
        print(f"ERROR: {result['error']}")
        return 1
    if result.get("status") == "failed":
        print(f"FAIL: Could not fetch URL — {result['meta'].get('error', 'unknown')}")
        return 1
    print(f"OK: Captured {result['source_id']}")
    print(f"  Raw: {result['raw_path']}")
    print(f"  Title: {result['title']}")
    print(f"  Domain: {result['meta'].get('domain', '?')}")
    print(f"  Size: {result['file_size']} bytes")
    if result.get("concepts"):
        print(f"  Concepts: {', '.join(result['concepts'][:8])}")
    if result.get("proposed_pages"):
        print(f"  Proposed pages: {', '.join(result['proposed_pages'][:5])}")
    return 0


def cmd_repo(args):
    result = ingest_repo(args.repo, title=args.title)
    if "error" in result:
        if result["error"] in ("duplicate", "duplicate_url"):
            print(f"SKIP: Already ingested as {result['existing']['source_id']}")
            return 1
        print(f"ERROR: {result['error']}")
        return 1
    if result.get("status") == "failed":
        print(f"FAIL: Could not clone/analyze — {result['meta'].get('error', 'unknown')}")
        return 1
    print(f"OK: Ingested repo {result['source_id']}")
    print(f"  Raw: {result['raw_path']}")
    print(f"  Title: {result['title']}")
    meta = result.get("meta", {})
    if meta.get("languages"):
        print(f"  Languages: {', '.join(meta['languages'])}")
    print(f"  Files: {meta.get('file_count', '?')} | Dirs: {meta.get('dir_count', '?')}")
    if result.get("proposed_pages"):
        print(f"  Proposed pages: {', '.join(result['proposed_pages'][:5])}")
    return 0


def cmd_paper(args):
    result = ingest_paper(args.path, title=args.title, arxiv_url=args.arxiv_url)
    if "error" in result:
        if result["error"] == "duplicate":
            print(f"SKIP: Already ingested as {result['existing']['source_id']}")
            return 1
        print(f"ERROR: {result['error']}")
        return 1
    print(f"OK: Ingested paper {result['source_id']}")
    print(f"  Raw: {result['raw_path']}")
    print(f"  Title: {result['title']}")
    meta = result.get("meta", {})
    if meta.get("arxiv"):
        print(f"  ArXiv: {meta['arxiv']}")
    print(f"  PDF stored: {meta.get('pdf_path', '?')}")
    print(f"  Text extracted: {meta.get('has_extracted_text', False)}")
    if result.get("proposed_pages"):
        print(f"  Proposed pages: {', '.join(result['proposed_pages'][:5])}")
    return 0


def cmd_compile(args):
    """Delegate to wiki_compile.py for the compile pipeline."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from wiki_compile import compile_one, compile_all_pending
    except ImportError:
        print("ERROR: wiki_compile.py not found in scripts/")
        return 1

    if getattr(args, "source_id", None):
        result = compile_one(args.source_id, dry_run=getattr(args, "dry_run", False))
        prefix = "[DRY RUN] " if getattr(args, "dry_run", False) else ""
        print(f"{prefix}{result['action'].upper()}: {result.get('title', '?')}")
        print(f"  Slug: {result.get('slug', '-')}")
        print(f"  Reason: {result.get('reason', '-')}")
        return 0 if result["action"] != "failed" else 1
    elif getattr(args, "all_pending", False):
        results = compile_all_pending(dry_run=getattr(args, "dry_run", False))
        if not results:
            print("No pending sources to compile.")
            return 0
        for r in results:
            print(f"  {r['action']}: {r.get('source_id', '?')} → {r.get('slug', '-')}")
        return 0
    else:
        print("Specify --source-id <id> or --all-pending")
        return 1


def cmd_registry(args):
    registry = SourceRegistry()
    sub = args.registry_cmd

    if sub == "stats":
        s = registry.stats()
        print(f"Total sources: {s['total']}")
        print(f"Total bytes: {s['total_bytes']:,}")
        if s["by_type"]:
            print("By type:")
            for t, n in sorted(s["by_type"].items()):
                print(f"  {t}: {n}")
        if s["by_status"]:
            print("By status:")
            for st, n in sorted(s["by_status"].items()):
                print(f"  {st}: {n}")
        return 0

    if sub == "list":
        records = registry.list_filtered(status=args.status, limit=args.limit or 50)
        if not records:
            print("No records found.")
            return 0
        for r in records:
            status_icon = {"ingested": "+", "failed": "!", "pending": "?"}.get(r.get("status", ""), " ")
            print(f"  [{status_icon}] {r['source_id']}  {r.get('title', '?')[:60]}")
        print(f"\n({len(records)} records shown)")
        return 0

    if sub == "get":
        rec = registry.find_by_id(args.source_id)
        if not rec:
            print(f"Not found: {args.source_id}")
            return 1
        print(json.dumps(rec, indent=2, ensure_ascii=False))
        return 0

    print(f"Unknown registry subcommand: {sub}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Clarvis wiki ingest pipeline")
    sub = parser.add_subparsers(dest="command")

    # file subcommand
    p_file = sub.add_parser("file", help="Ingest a local file")
    p_file.add_argument("path", help="Path to file")
    p_file.add_argument("--type", choices=SOURCE_TYPES, help="Override source type")
    p_file.add_argument("--title", help="Override title")

    # url subcommand
    p_url = sub.add_parser("url", help="Capture and ingest a web URL")
    p_url.add_argument("url", help="URL to capture")
    p_url.add_argument("--type", choices=SOURCE_TYPES, help="Override source type (default: web)")
    p_url.add_argument("--title", help="Override title")

    # repo subcommand
    p_repo = sub.add_parser("repo", help="Ingest a GitHub repo URL or local repo path")
    p_repo.add_argument("repo", help="GitHub URL (https://github.com/org/repo) or local path")
    p_repo.add_argument("--title", help="Override repo title")

    # paper subcommand
    p_paper = sub.add_parser("paper", help="Ingest a PDF paper")
    p_paper.add_argument("path", help="Path to PDF file")
    p_paper.add_argument("--title", help="Override paper title")
    p_paper.add_argument("--arxiv-url", help="ArXiv or DOI URL for the paper")

    # compile subcommand
    p_compile = sub.add_parser("compile", help="Compile raw sources into wiki pages")
    p_compile.add_argument("--source-id", help="Compile a specific source by ID")
    p_compile.add_argument("--all-pending", action="store_true", help="Compile all unlinked sources")
    p_compile.add_argument("--dry-run", action="store_true", help="Preview without writing")

    # registry subcommand
    p_reg = sub.add_parser("registry", help="Query the source registry")
    reg_sub = p_reg.add_subparsers(dest="registry_cmd")
    reg_sub.add_parser("stats", help="Show registry statistics")
    p_list = reg_sub.add_parser("list", help="List registered sources")
    p_list.add_argument("--status", choices=["ingested", "failed", "pending"])
    p_list.add_argument("--limit", type=int, default=50)
    p_get = reg_sub.add_parser("get", help="Get a single source record")
    p_get.add_argument("source_id", help="Source ID to look up")

    args = parser.parse_args()

    if args.command == "file":
        sys.exit(cmd_file(args))
    elif args.command == "url":
        sys.exit(cmd_url(args))
    elif args.command == "repo":
        sys.exit(cmd_repo(args))
    elif args.command == "paper":
        sys.exit(cmd_paper(args))
    elif args.command == "compile":
        sys.exit(cmd_compile(args))
    elif args.command == "registry":
        if not args.registry_cmd:
            p_reg.print_help()
            sys.exit(1)
        sys.exit(cmd_registry(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
