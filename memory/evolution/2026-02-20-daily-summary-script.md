# 2026-02-20 — Daily Summary Script

**Task:** Build a "daily summary" script that compresses memory/*.md
**Status:** ✅ Complete

## What was built
- `scripts/daily-summary.sh` — Creates summarized daily memory reports

## Features
- Takes optional `[days]` argument (default: 3)
- Outputs to `memory/summaries/YYYY-MM-DD.md`
- Shows line count, entry count, and key highlights
- Creates summaries directory if missing

## Usage
```bash
./scripts/daily-summary.sh      # Last 3 days
./scripts/daily-summary.sh 7    # Last 7 days
```

## Testing
- ✅ Script created and made executable
- ✅ Ran successfully with 3 days parameter
- ✅ Generated `memory/summaries/2026-02-20.md`

## Notes
- Highlights extraction is basic (extracts section headers)
- Could be enhanced later with semantic extraction
- Useful for weekly reviews and memory maintenance