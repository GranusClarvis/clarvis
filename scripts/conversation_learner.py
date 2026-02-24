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
from collections import Counter

sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain import brain, AUTONOMOUS_LEARNING


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

    # Check for existing autonomous-learning entries to avoid duplicates
    existing = brain.get(AUTONOMOUS_LEARNING, n=200)
    existing_texts = set()
    for e in existing:
        doc = e.get('document', '')
        # Strip examples suffix before dedup
        doc_core = doc.split(' | Examples:')[0]
        norm = re.sub(r'\s+', ' ', doc_core.lower().strip())[:80]
        existing_texts.add(norm)

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


def run(dry_run=False, report_only=False):
    """Main entry point: analyze transcripts and store learnings."""
    print("=== Conversation Learner ===\n")

    # Load
    transcripts = load_transcripts()
    print(f"Loaded {len(transcripts)} transcripts from memory/")
    if not transcripts:
        print("No transcripts found. Nothing to learn.")
        return {'stored': 0, 'insights': 0}

    # Extract
    patterns = extract_patterns(transcripts)

    # Synthesize
    insights = synthesize_insights(patterns)
    print(f"Synthesized {len(insights)} insights\n")

    # Report
    if report_only:
        print_report(patterns, insights)
        return {'stored': 0, 'insights': len(insights)}

    # Store
    print_report(patterns, insights)
    stored = store_insights(insights, dry_run=dry_run)
    print(f"\n{'[DRY RUN] Would store' if dry_run else 'Stored'} {stored} new insights to brain (collection=autonomous-learning)")

    return {'stored': stored, 'insights': len(insights)}


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    report_only = '--report' in sys.argv
    result = run(dry_run=dry_run, report_only=report_only)
    print(f"\nDone. Insights: {result['insights']}, Stored: {result['stored']}")
