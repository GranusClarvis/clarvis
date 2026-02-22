#!/bin/bash
# daily-summary.sh - Compress memory/*.md into a summary
# Usage: ./scripts/daily-summary.sh [days]

DAYS=${1:-3}
OUTPUT_DIR="memory/summaries"
mkdir -p "$OUTPUT_DIR"

# Get dates to process
TODAY=$(date +%Y-%m-%d)
SUMMARY_FILE="$OUTPUT_DIR/${TODAY}.md"

echo "# Daily Summary — $TODAY" > "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Process each day's memory file
for i in $(seq 0 $((DAYS - 1))); do
    DATE=$(date -d "$i days ago" +%Y-%m-%d)
    FILE="memory/${DATE}.md"
    
    if [ -f "$FILE" ]; then
        echo "## $DATE" >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
        
        # Extract first non-empty line as "title" or summary
        # Then count entries
        ENTRIES=$(grep -c "^- " "$FILE" 2>/dev/null || echo "0")
        LINES=$(wc -l < "$FILE")
        
        echo "- **Source:** memory/$DATE.md" >> "$SUMMARY_FILE"
        echo "- **Lines:** $LINES" >> "$SUMMARY_FILE"
        echo "- **Entries:** $ENTRIES" >> "$SUMMARY_FILE"
        
        # Extract key events (lines with timestamp pattern or bullet points)
        echo "" >> "$SUMMARY_FILE"
        echo "### Highlights" >> "$SUMMARY_FILE"
        grep -E "^##|^\*\*[A-Z]|^\- \[x\]" "$FILE" | head -10 >> "$SUMMARY_FILE" 2>/dev/null || echo "(no highlights found)" >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
        echo "---" >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
    fi
done

echo "✅ Summary created: $SUMMARY_FILE"
cat "$SUMMARY_FILE"