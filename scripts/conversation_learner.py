#!/usr/bin/env python3
"""
Conversation Learner — Extract patterns from session transcripts

Reads memory/*.md session logs, extracts:
  1. Recurring questions / themes
  2. Approaches that worked (successes)
  3. Approaches that failed (failures)
  4. Bug patterns
  5. Workflow patterns

Stores structured insights in brain with collection='autonomous-learning'.

Usage:
    python3 conversation_learner.py             # Full analysis + store
    python3 conversation_learner.py --dry-run   # Analyze without storing
    python3 conversation_learner.py --report    # Print report only
"""

import sys
import os
import re
import json
import gzip
import logging
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain, AUTONOMOUS_LEARNING

logger = logging.getLogger(__name__)

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
TRANSCRIPTS_DIR = WORKSPACE / "data" / "session_transcripts"


# === Pattern extraction regexes ===

# Success indicators in session logs
SUCCESS_PATTERNS = [
    re.compile(r'[-✅✓]\s*\[?x\]?\s*(.+)', re.IGNORECASE),          # - [x] task or ✅ task
    re.compile(r'(?:fixed|resolved|completed|built|created|wired|tested)\s*[:\-—]\s*(.+)', re.IGNORECASE),
    re.compile(r'(.+?)\s*—\s*(?:working|done|complete|fixed|tested)', re.IGNORECASE),
]

# Failure / problem indicators
FAILURE_PATTERNS = [
    re.compile(r'(?:bug|error|fail|broke|broken|issue|problem|crash)\w*\s*[:\-—]\s*(.+)', re.IGNORECASE),
    re.compile(r'root\s*cause\s*[:\-—]\s*(.+)', re.IGNORECASE),
    re.compile(r'(?:wrong|incorrect|invalid|missing)\s+(.+)', re.IGNORECASE),
]

# Recurring question / investigation indicators
QUESTION_PATTERNS = [
    re.compile(r'(?:investigate|why|how|what)\s+(.{15,})', re.IGNORECASE),
    re.compile(r'(?:problem investigated|root cause found)\s*[:\-—]?\s*(.+)', re.IGNORECASE),
]

# Key insight / lesson indicators
INSIGHT_PATTERNS = [
    re.compile(r'key\s*(?:insight|learning|lesson)\s*[:\-—]\s*(.+)', re.IGNORECASE),
    re.compile(r'(?:important|critical|insight)\s*[:\-—]\s*(.+)', re.IGNORECASE),
    re.compile(r'(?:stop|never|always|remember)\s+(.{15,})', re.IGNORECASE),
]

# Tool / approach patterns
APPROACH_PATTERNS = [
    re.compile(r'(?:approach|strategy|method|technique|pattern|solution)\s*[:\-—]\s*(.+)', re.IGNORECASE),
    re.compile(r'(?:replaced|switched|migrated|refactored)\s+(.+?)\s+(?:with|to|into)\s+(.+)', re.IGNORECASE),
]

# Bug type patterns for classification
BUG_TYPE_PATTERNS = {
    'wrong_param': re.compile(r'wrong\s+param|param\s+name|silently\s+fail', re.IGNORECASE),
    'unused_code': re.compile(r'never\s+used|unused|dead\s+code', re.IGNORECASE),
    'missing_wiring': re.compile(r'never\s+runs|not\s+wired|not\s+called|never\s+called', re.IGNORECASE),
    'data_format': re.compile(r'wrong\s+format|parse\s+error|json|format\s+mismatch', re.IGNORECASE),
    'timeout': re.compile(r'timeout|too\s+short|too\s+long|hung|hanging', re.IGNORECASE),
    'threshold': re.compile(r'threshold|ceiling|floor|too\s+strict|too\s+lax', re.IGNORECASE),
}


def load_transcripts() -> list:
    """Load all memory/*.md files as session transcripts, including subdirs."""
    memory_dir = '/home/agent/.openclaw/workspace/memory'
    transcripts = []

    # Walk memory/ recursively for all .md files
    for root, dirs, files in os.walk(memory_dir):
        for fname in sorted(files):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(root, fname)

            with open(fpath, 'r') as f:
                content = f.read()

            # Extract date from filename if possible
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', fname)
            date = date_match.group(1) if date_match else fname.replace('.md', '')

            rel_path = os.path.relpath(fpath, memory_dir)
            transcripts.append({
                'file': rel_path,
                'date': date,
                'content': content,
                'lines': content.split('\n'),
            })

    return transcripts


def load_session_transcripts() -> list:
    """Load structured session transcripts from data/session_transcripts/.

    Returns list of dicts with keys: task, status, exit_code, duration_s,
    output (full text from raw file or inline tail), date, error_type, worker_type.
    """
    if not TRANSCRIPTS_DIR.exists():
        return []

    records = []
    # Read both plain .jsonl and compressed .jsonl.gz (recent history)
    jsonl_files = sorted(TRANSCRIPTS_DIR.glob("????-??-??.jsonl"))
    gz_files = sorted(TRANSCRIPTS_DIR.glob("????-??-??.jsonl.gz"))

    for jf in list(gz_files) + list(jsonl_files):
        try:
            opener = gzip.open if jf.suffix == ".gz" else open
            with opener(jf, "rt", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Resolve full output: prefer raw file, fall back to inline tail
                    output = rec.get("output_tail", "")
                    raw_name = rec.get("raw_file")
                    if raw_name:
                        raw_path = TRANSCRIPTS_DIR / "raw" / raw_name
                        if raw_path.exists():
                            try:
                                output = raw_path.read_text(encoding="utf-8", errors="replace")
                            except OSError:
                                pass

                    records.append({
                        "task": rec.get("task", ""),
                        "status": rec.get("status", "unknown"),
                        "exit_code": rec.get("exit_code", -1),
                        "duration_s": rec.get("duration_s", 0),
                        "output": output,
                        "date": rec.get("ts", "")[:10],
                        "error_type": rec.get("error_type"),
                        "worker_type": rec.get("worker_type", "general"),
                        "section": rec.get("section", "P1"),
                    })
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to read transcript %s: %s", jf.name, e)

    return records


def extract_session_patterns(session_records: list) -> dict:
    """Extract structured patterns from session transcript records.

    Complements the regex-based extract_patterns() with structured data:
    task-outcome correlations, error-type distributions, duration outliers,
    and richer output-based pattern extraction.
    """
    patterns = {
        "successes": [],
        "failures": [],
        "questions": [],
        "insights": [],
        "approaches": [],
        "bug_types": Counter(),
        "recurring_themes": Counter(),
        "tools_used": Counter(),
        "systems_touched": Counter(),
    }

    error_types = Counter()
    durations_by_status = {"success": [], "failure": [], "timeout": [], "crash": []}
    worker_outcomes = Counter()

    for rec in session_records:
        task = rec["task"]
        status = rec["status"]
        output = rec["output"]
        date = rec["date"]

        # Track error type distribution
        if rec["error_type"]:
            error_types[rec["error_type"]] += 1
            patterns["bug_types"][rec["error_type"]] += 1

        # Track worker type outcomes
        worker_outcomes[f"{rec['worker_type']}:{status}"] += 1

        # Track duration by status
        if status in durations_by_status and rec["duration_s"] > 0:
            durations_by_status[status].append(rec["duration_s"])

        # Extract richer patterns from full output
        combined = f"{task}\n{output}"

        # Successes with full context
        if status == "success":
            patterns["successes"].append({
                "text": task[:300],
                "date": date,
                "source": "session_transcript",
            })

        # Failures with full error context
        if status in ("failure", "crash", "timeout"):
            error_snippet = output[-500:] if output else task
            patterns["failures"].append({
                "text": f"{task[:150]} — {error_snippet[:150]}",
                "date": date,
                "source": "session_transcript",
            })

        # Extract patterns from full output text using existing regexes
        for pat in INSIGHT_PATTERNS:
            for match in pat.finditer(combined):
                text = match.group(1).strip()
                if 10 < len(text) < 300:
                    patterns["insights"].append({
                        "text": text,
                        "date": date,
                        "source": "session_transcript",
                    })

        # Extract tool/system mentions from full output
        tool_names = re.findall(
            r'\b(brain\.py|attention\.py|working_memory\.py|phi_metric\.py|'
            r'procedural_memory\.py|reasoning_chain|knowledge_synthesis|'
            r'self_model\.py|clarvis_confidence|evolution_loop|'
            r'task_selector|cron_\w+\.sh|claude\s+code|chromadb)\b',
            combined, re.IGNORECASE
        )
        for tool in tool_names:
            patterns["tools_used"][tool.lower()] += 1

        system_names = re.findall(
            r'\b(brain|attention|working.memory|phi|procedural|reasoning|'
            r'synthesis|self.model|confidence|evolution|dashboard|'
            r'consolidation|retrieval)\b',
            combined, re.IGNORECASE
        )
        for sys_name in system_names:
            patterns["systems_touched"][sys_name.lower()] += 1

    # Synthesize structural insights from session metadata
    total = len(session_records)
    if total > 0:
        n_success = sum(1 for r in session_records if r["status"] == "success")
        n_fail = sum(1 for r in session_records if r["status"] in ("failure", "crash"))
        n_timeout = sum(1 for r in session_records if r["status"] == "timeout")

        if total >= 3:
            patterns["insights"].append({
                "text": f"Session transcript stats: {n_success}/{total} success, "
                        f"{n_fail} failures, {n_timeout} timeouts",
                "date": session_records[-1]["date"] if session_records else "",
                "source": "session_transcript_meta",
            })

        # Flag error types that recur
        for etype, count in error_types.most_common(3):
            if count >= 2:
                patterns["insights"].append({
                    "text": f"Recurring error type '{etype}' seen {count} times in session transcripts",
                    "date": session_records[-1]["date"],
                    "source": "session_transcript_meta",
                })

        # Flag duration outliers
        for status_key, durations in durations_by_status.items():
            if len(durations) >= 3:
                avg = sum(durations) / len(durations)
                if avg > 900 and status_key == "success":
                    patterns["insights"].append({
                        "text": f"Successful tasks averaging {avg:.0f}s — consider splitting complex tasks",
                        "date": session_records[-1]["date"],
                        "source": "session_transcript_meta",
                    })

    return patterns


def _merge_patterns(base: dict, extra: dict) -> dict:
    """Merge two pattern dicts, combining lists and Counters."""
    merged = {}
    for key in base:
        if isinstance(base[key], list):
            merged[key] = base[key] + extra.get(key, [])
        elif isinstance(base[key], Counter):
            merged[key] = base[key] + extra.get(key, Counter())
        else:
            merged[key] = base[key]
    return merged


def extract_patterns(transcripts: list) -> dict:
    """Extract all pattern types from transcripts."""
    patterns = {
        'successes': [],
        'failures': [],
        'questions': [],
        'insights': [],
        'approaches': [],
        'bug_types': Counter(),
        'recurring_themes': Counter(),
        'tools_used': Counter(),
        'systems_touched': Counter(),
    }

    for tx in transcripts:
        content = tx['content']
        date = tx['date']

        # Extract successes
        for pat in SUCCESS_PATTERNS:
            for match in pat.finditer(content):
                text = match.group(1).strip()
                if len(text) > 10 and len(text) < 300:
                    patterns['successes'].append({
                        'text': text,
                        'date': date,
                        'source': tx['file'],
                    })

        # Extract failures
        for pat in FAILURE_PATTERNS:
            for match in pat.finditer(content):
                text = match.group(1).strip()
                if len(text) > 10 and len(text) < 300:
                    patterns['failures'].append({
                        'text': text,
                        'date': date,
                        'source': tx['file'],
                    })

        # Classify bug types
        for bug_type, bug_pat in BUG_TYPE_PATTERNS.items():
            if bug_pat.search(content):
                patterns['bug_types'][bug_type] += 1

        # Extract questions / investigations
        for pat in QUESTION_PATTERNS:
            for match in pat.finditer(content):
                text = match.group(1).strip()
                if len(text) > 15 and len(text) < 300:
                    patterns['questions'].append({
                        'text': text,
                        'date': date,
                        'source': tx['file'],
                    })

        # Extract insights
        for pat in INSIGHT_PATTERNS:
            for match in pat.finditer(content):
                text = match.group(1).strip()
                if len(text) > 10 and len(text) < 300:
                    patterns['insights'].append({
                        'text': text,
                        'date': date,
                        'source': tx['file'],
                    })

        # Extract approaches
        for pat in APPROACH_PATTERNS:
            for match in pat.finditer(content):
                groups = match.groups()
                text = ' → '.join(g.strip() for g in groups if g)
                if len(text) > 10:
                    patterns['approaches'].append({
                        'text': text,
                        'date': date,
                        'source': tx['file'],
                    })

        # Count recurring themes (section headers)
        for line in tx['lines']:
            header = re.match(r'^#{1,3}\s+(.+)', line)
            if header:
                theme = header.group(1).strip().lower()
                # Normalize common themes
                theme = re.sub(r'\(.*?\)', '', theme).strip()
                if len(theme) > 3:
                    patterns['recurring_themes'][theme] += 1

        # Count tools/systems mentioned
        tool_names = re.findall(
            r'\b(brain\.py|attention\.py|working_memory\.py|phi_metric\.py|'
            r'procedural_memory\.py|reasoning_chain|knowledge_synthesis|'
            r'self_model\.py|clarvis_confidence|evolution_loop|'
            r'task_selector|cron_\w+\.sh|claude\s+code|chromadb)\b',
            content, re.IGNORECASE
        )
        for tool in tool_names:
            patterns['tools_used'][tool.lower()] += 1

        # Count systems touched
        system_names = re.findall(
            r'\b(brain|attention|working.memory|phi|procedural|reasoning|'
            r'synthesis|self.model|confidence|evolution|dashboard|'
            r'consolidation|retrieval)\b',
            content, re.IGNORECASE
        )
        for sys_name in system_names:
            patterns['systems_touched'][sys_name.lower()] += 1

    return patterns


def find_recurring_questions(patterns: dict) -> list:
    """Find questions/themes that recur across multiple sessions."""
    # Group questions by semantic similarity (simple keyword overlap)
    questions = patterns['questions']
    clusters = []
    used = set()

    for i, q in enumerate(questions):
        if i in used:
            continue
        cluster = [q]
        used.add(i)
        q_words = set(q['text'].lower().split())

        for j, q2 in enumerate(questions):
            if j in used:
                continue
            q2_words = set(q2['text'].lower().split())
            overlap = len(q_words & q2_words)
            if overlap >= 3 and q['source'] != q2['source']:
                cluster.append(q2)
                used.add(j)

        if len(cluster) > 1:
            clusters.append({
                'question': cluster[0]['text'],
                'occurrences': len(cluster),
                'dates': sorted(set(c['date'] for c in cluster)),
                'sources': sorted(set(c['source'] for c in cluster)),
            })

    clusters.sort(key=lambda x: x['occurrences'], reverse=True)
    return clusters


def find_what_works(patterns: dict) -> list:
    """Identify approaches that consistently lead to success."""
    # Look for success patterns that repeat
    success_texts = [s['text'].lower() for s in patterns['successes']]

    # Find common action verbs in successes
    action_counter = Counter()
    for text in success_texts:
        actions = re.findall(
            r'(wired|built|created|fixed|added|replaced|tested|integrated|'
            r'removed|cleaned|migrated|refactored|redesigned)',
            text
        )
        for a in actions:
            action_counter[a] += 1

    # Top successful approaches
    approach_insights = []
    for action, count in action_counter.most_common(10):
        examples = [s for s in patterns['successes'] if action in s['text'].lower()][:3]
        approach_insights.append({
            'pattern': f"'{action}' is a common successful action ({count} times)",
            'examples': [e['text'][:100] for e in examples],
            'count': count,
        })

    return approach_insights


def find_what_fails(patterns: dict) -> list:
    """Identify recurring failure patterns."""
    failure_insights = []

    # Bug type distribution
    if patterns['bug_types']:
        for bug_type, count in patterns['bug_types'].most_common():
            failure_insights.append({
                'pattern': f"Bug type '{bug_type}' occurred {count} time(s)",
                'type': 'bug_classification',
                'count': count,
            })

    # Common failure words
    fail_words = Counter()
    for f in patterns['failures']:
        words = set(f['text'].lower().split())
        for w in words:
            if len(w) > 4:
                fail_words[w] += 1

    for word, count in fail_words.most_common(5):
        if count >= 2:
            examples = [f for f in patterns['failures'] if word in f['text'].lower()][:2]
            failure_insights.append({
                'pattern': f"Recurring failure theme: '{word}' ({count} times)",
                'examples': [e['text'][:100] for e in examples],
                'count': count,
            })

    return failure_insights


def synthesize_insights(patterns: dict) -> list:
    """Create high-level structured insights from all patterns."""
    insights = []

    # 1. Success rate / velocity
    n_success = len(patterns['successes'])
    n_failure = len(patterns['failures'])
    if n_success + n_failure > 0:
        rate = n_success / (n_success + n_failure)
        insights.append({
            'type': 'meta_pattern',
            'insight': f"Success rate across sessions: {rate:.0%} ({n_success} successes, {n_failure} failures)",
            'importance': 0.7,
        })

    # 2. Most worked-on systems
    top_systems = patterns['systems_touched'].most_common(5)
    if top_systems:
        sys_list = ', '.join(f"{s}({c})" for s, c in top_systems)
        insights.append({
            'type': 'focus_pattern',
            'insight': f"Most-touched systems: {sys_list}",
            'importance': 0.6,
        })

    # 3. Recurring themes
    top_themes = patterns['recurring_themes'].most_common(5)
    if top_themes:
        theme_list = ', '.join(f"'{t}'({c})" for t, c in top_themes)
        insights.append({
            'type': 'theme_pattern',
            'insight': f"Recurring session themes: {theme_list}",
            'importance': 0.6,
        })

    # 4. Approaches that work
    what_works = find_what_works(patterns)
    for w in what_works[:3]:
        insights.append({
            'type': 'success_pattern',
            'insight': w['pattern'],
            'importance': 0.75,
            'examples': w.get('examples', []),
        })

    # 5. Failure patterns
    what_fails = find_what_fails(patterns)
    for f in what_fails[:3]:
        insights.append({
            'type': 'failure_pattern',
            'insight': f['pattern'],
            'importance': 0.8,  # Failures are more important to learn from
            'examples': f.get('examples', []),
        })

    # 6. Recurring questions
    recurring = find_recurring_questions(patterns)
    for r in recurring[:3]:
        insights.append({
            'type': 'recurring_question',
            'insight': f"Recurring question ({r['occurrences']}x across {len(r['dates'])} sessions): {r['question'][:150]}",
            'importance': 0.7,
        })

    # 7. Key insights from transcripts (direct extraction)
    for i in patterns['insights'][:5]:
        insights.append({
            'type': 'direct_insight',
            'insight': i['text'][:200],
            'importance': 0.8,
            'date': i['date'],
        })

    return insights


def store_insights(insights: list, dry_run: bool = False) -> int:
    """Store structured insights in brain with collection='autonomous-learning'."""
    stored = 0
    failed = 0

    # Check for existing autonomous-learning entries to avoid duplicates
    existing_texts = set()
    try:
        existing = brain.get(AUTONOMOUS_LEARNING, n=200)
        for e in existing:
            doc = e.get('document', '')
            # Strip examples suffix before dedup
            doc_core = doc.split(' | Examples:')[0]
            norm = re.sub(r'\s+', ' ', doc_core.lower().strip())[:80]
            existing_texts.add(norm)
    except Exception as e:
        logger.error("Failed to load existing learnings for dedup: %s", e)
        # Continue without dedup — better to store duplicates than lose insights

    for insight in insights:
        text = f"[{insight['type']}] {insight['insight']}"

        # Skip if similar entry already exists (ignore examples suffix)
        text_core = text.split(' | Examples:')[0]
        normalized = re.sub(r'\s+', ' ', text_core.lower().strip())[:80]
        if normalized in existing_texts:
            continue

        importance = insight.get('importance', 0.6)
        tags = ['autonomous-learning', insight['type']]

        if insight.get('examples'):
            text += f" | Examples: {'; '.join(insight['examples'][:2])}"

        if dry_run:
            print(f"  [DRY RUN] Would store (imp={importance:.1f}): {text[:120]}...")
            stored += 1
        else:
            try:
                mem_id = brain.store(
                    text,
                    collection=AUTONOMOUS_LEARNING,
                    importance=importance,
                    tags=tags,
                    source='conversation_learner',
                )
                print(f"  Stored ({mem_id}): {text[:100]}...")
                stored += 1
                existing_texts.add(normalized)
            except Exception as e:
                logger.error("Failed to store insight: %s — %s", text[:80], e)
                failed += 1

    if failed:
        logger.warning("Learning pipeline: %d/%d insights failed to store", failed, failed + stored)
    return stored


def print_report(patterns: dict, insights: list):
    """Print a human-readable analysis report."""
    print("=" * 60)
    print("  CONVERSATION LEARNING REPORT")
    print("=" * 60)

    print("\n--- Transcript Stats ---")
    print(f"  Successes extracted: {len(patterns['successes'])}")
    print(f"  Failures extracted:  {len(patterns['failures'])}")
    print(f"  Questions found:     {len(patterns['questions'])}")
    print(f"  Insights found:      {len(patterns['insights'])}")
    print(f"  Approaches found:    {len(patterns['approaches'])}")

    print("\n--- Bug Type Distribution ---")
    for bt, count in patterns['bug_types'].most_common():
        print(f"  {bt}: {count}")

    print("\n--- Top Systems Touched ---")
    for sys_name, count in patterns['systems_touched'].most_common(8):
        print(f"  {sys_name}: {count}")

    print("\n--- Recurring Themes ---")
    for theme, count in patterns['recurring_themes'].most_common(8):
        print(f"  '{theme}': {count}")

    print("\n--- What Works ---")
    for w in find_what_works(patterns)[:5]:
        print(f"  {w['pattern']}")

    print("\n--- What Fails ---")
    for f in find_what_fails(patterns)[:5]:
        print(f"  {f['pattern']}")

    recurring = find_recurring_questions(patterns)
    if recurring:
        print("\n--- Recurring Questions ---")
        for r in recurring[:3]:
            print(f"  ({r['occurrences']}x) {r['question'][:100]}")

    print(f"\n--- Synthesized Insights ({len(insights)}) ---")
    for i, ins in enumerate(insights, 1):
        print(f"  {i}. [{ins['type']}] {ins['insight'][:120]}")

    print()


# Tool-use patterns in Claude Code output for procedure extraction
_TOOL_RE = re.compile(
    r'\b(Read|Edit|Write|Grep|Glob|Bash|Agent|TodoWrite)\s+tool\b',
    re.IGNORECASE,
)


def distill_procedures(session_records: list, dry_run: bool = False) -> int:
    """Distill reusable procedures from successful session transcripts.

    Groups successful sessions by task keywords, extracts common tool-use
    sequences, and stores as procedures in clarvis-procedures. Rule-based
    (no LLM cost).

    Returns count of procedures stored.
    """
    from brain import PROCEDURES

    # Group successful sessions by task type keywords
    type_groups: dict[str, list] = {}
    for rec in session_records:
        if rec["status"] != "success":
            continue
        # Extract primary task keyword (first bracket tag or first 2 significant words)
        task = rec["task"]
        tag_match = re.search(r'\[(\w+)', task)
        if tag_match:
            key = tag_match.group(1).upper()
        else:
            words = [w for w in re.findall(r'[a-z]+', task.lower())
                     if w not in ("the", "a", "an", "in", "to", "for", "of", "and", "or", "with")]
            key = "_".join(words[:2]).upper() if len(words) >= 2 else "GENERAL"
        type_groups.setdefault(key, []).append(rec)

    stored = 0
    # Only distill groups with ≥3 successes (enough data for a pattern)
    for task_type, sessions in type_groups.items():
        if len(sessions) < 3:
            continue

        # Extract tool-use sequences from each session's output
        sequences = []
        for rec in sessions:
            output = rec.get("output", "")
            tools_found = _TOOL_RE.findall(output)
            if tools_found:
                # Normalize: deduplicate consecutive same-tool uses
                deduped = [tools_found[0]]
                for t in tools_found[1:]:
                    if t.lower() != deduped[-1].lower():
                        deduped.append(t)
                sequences.append(deduped)

        if len(sequences) < 2:
            continue

        # Find the most common tool sequence (longest common prefix across sequences)
        common_tools = Counter()
        for seq in sequences:
            for tool in seq:
                common_tools[tool.capitalize()] += 1

        # Build procedure: tools used in >50% of sessions, ordered by frequency
        threshold = len(sequences) * 0.5
        core_tools = [t for t, c in common_tools.most_common() if c >= threshold]
        if not core_tools:
            continue

        # Compute success rate for this task type
        total_for_type = sum(1 for r in session_records
                             if re.search(rf'\b{re.escape(task_type)}\b', r["task"], re.IGNORECASE))
        success_rate = len(sessions) / max(total_for_type, len(sessions))

        # Format procedure text
        last_date = sessions[-1].get("date", "unknown")
        proc_text = (
            f"[PROCEDURE:{task_type}] For tasks matching '{task_type}': "
            f"common tool sequence is {' → '.join(core_tools)}. "
            f"Success rate: {success_rate:.0%} across {len(sessions)} sessions. "
            f"Last seen: {last_date}."
        )

        # Dedup against existing procedures
        try:
            existing = brain.recall(proc_text[:200], n=3, collections=[PROCEDURES])
            if any(e.get("distance", 1.0) < 0.15 for e in existing):
                continue  # already have a very similar procedure
        except Exception:
            pass

        if dry_run:
            print(f"  [DRY RUN] Would store procedure: {proc_text[:120]}...")
            stored += 1
        else:
            try:
                brain.store(
                    proc_text,
                    collection=PROCEDURES,
                    importance=0.7,
                    tags=["procedure", "auto-distilled", task_type.lower(),
                          f"usage:{len(sessions)}", f"last:{last_date}"],
                    source="conversation_learner_distill",
                )
                print(f"  Stored procedure: {proc_text[:100]}...")
                stored += 1
            except Exception as e:
                logger.error("Failed to store procedure: %s — %s", task_type, e)

    if stored:
        print(f"\n  Distilled {stored} procedures from {len(type_groups)} task groups")
    return stored


def run(dry_run=False, report_only=False):
    """Main entry point: analyze transcripts and store learnings."""
    print("=== Conversation Learner ===\n")

    # Load memory/*.md transcripts (legacy source)
    transcripts = load_transcripts()
    print(f"Loaded {len(transcripts)} memory transcripts from memory/")

    # Load structured session transcripts (richer source)
    session_records = load_session_transcripts()
    print(f"Loaded {len(session_records)} session transcript records from data/session_transcripts/")

    if not transcripts and not session_records:
        print("No transcripts found. Nothing to learn.")
        return {'stored': 0, 'insights': 0}

    # Extract patterns from both sources and merge
    patterns = extract_patterns(transcripts) if transcripts else {
        'successes': [], 'failures': [], 'questions': [], 'insights': [],
        'approaches': [], 'bug_types': Counter(), 'recurring_themes': Counter(),
        'tools_used': Counter(), 'systems_touched': Counter(),
    }
    if session_records:
        session_patterns = extract_session_patterns(session_records)
        patterns = _merge_patterns(patterns, session_patterns)

    # Synthesize
    insights = synthesize_insights(patterns)
    print(f"Synthesized {len(insights)} insights\n")

    # Report
    if report_only:
        print_report(patterns, insights)
        return {'stored': 0, 'insights': len(insights)}

    # Store
    print_report(patterns, insights)
    try:
        stored = store_insights(insights, dry_run=dry_run)
    except Exception as e:
        logger.error("store_insights crashed: %s", e)
        stored = 0
    print(f"\n{'[DRY RUN] Would store' if dry_run else 'Stored'} {stored} new insights to brain (collection=autonomous-learning)")

    # Distill reusable procedures from successful sessions
    proc_stored = 0
    if session_records:
        try:
            proc_stored = distill_procedures(session_records, dry_run=dry_run)
        except Exception as e:
            logger.error("distill_procedures crashed: %s", e)

    return {'stored': stored + proc_stored, 'insights': len(insights), 'procedures': proc_stored}


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    report_only = '--report' in sys.argv
    result = run(dry_run=dry_run, report_only=report_only)
    print(f"\nDone. Insights: {result['insights']}, Stored: {result['stored']}")
