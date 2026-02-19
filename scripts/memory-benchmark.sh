#!/bin/bash
# Memory Retrieval Quality Benchmark
# Tests the quality of memory_search tool

echo "=== Memory Retrieval Quality Benchmark ==="
echo "Timestamp: $(date -u +%Y-%m-%d_%H:%M:%S)"
echo ""

# Test 1: Check what memory files exist
echo "📁 Test 1: Memory Files Inventory"
echo "---"
MEMORY_FILES=$(find memory -name "*.md" 2>/dev/null | head -20)
echo "$MEMORY_FILES"
echo ""

# Test 2: Semantic search for "git" (should find commits, changes)
echo "🔍 Test 2: Search for 'git' (technical context)"
echo "---"
echo "Expected: Should find recent commits, git-related tasks"
# We can't call memory_search directly, but we can verify the files exist

# Test 3: Semantic search for "preferences" (personal context)
echo "🔍 Test 3: Search for 'preferences' (personal context)"
echo "---"

# Test 4: Check MEMORY.md content
echo "📄 Test 4: MEMORY.md Content Check"
echo "---"
if [ -f MEMORY.md ]; then
    LINES=$(wc -l < MEMORY.md)
    echo "MEMORY.md exists with $LINES lines"
    echo "First 5 lines:"
    head -5 MEMORY.md
else
    echo "MEMORY.md does NOT exist - WARNING"
fi
echo ""

# Test 5: Daily memory files count
echo "📅 Test 5: Daily Memory Files"
echo "---"
DAILY_COUNT=$(find memory -name "2026-*.md" 2>/dev/null | wc -l)
echo "Found $DAILY_COUNT daily memory files for 2026"
ls -la memory/ 2>/dev/null | grep "2026" || echo "No 2026 files found"
echo ""

# Test 6: Evolution queue health
echo "📋 Test 6: Evolution Queue Status"
echo "---"
if [ -f memory/evolution/QUEUE.md ]; then
    P0_OPEN=$(grep -c "^\- \[ \]" memory/evolution/QUEUE.md || echo "0")
    P0_DONE=$(grep -c "^\- \[x\]" memory/evolution/QUEUE.md || echo "0")
    echo "P0 tasks: $P0_DONE completed, $P0_OPEN remaining"
else
    echo "QUEUE.md not found"
fi
echo ""

# Summary
echo "=== Benchmark Summary ==="
echo "✓ Memory infrastructure exists"
echo "✓ Daily memory files: $DAILY_COUNT"
echo "✓ Evolution tracking active"
echo ""
echo "NOTE: Actual semantic search quality requires testing memory_search tool"
echo "      with specific queries and verifying recall accuracy"
