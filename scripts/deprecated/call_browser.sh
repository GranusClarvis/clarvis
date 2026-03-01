#!/bin/bash
# =============================================================================
# call_browser.sh — Wrapper to invoke browser_agent.py from cron/spawn_claude
#
# Usage:
#   ./call_browser.sh status
#   ./call_browser.sh navigate https://example.com
#   ./call_browser.sh extract https://example.com
#   ./call_browser.sh agent "Find the latest Python release"
#   ./call_browser.sh crawl https://example.com     # Uses Crawl4AI
#   ./call_browser.sh --store browse https://example.com
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source cron env if not already set up
if [ -z "${CLARVIS_WORKSPACE:-}" ]; then
    source "$SCRIPT_DIR/cron_env.sh" 2>/dev/null || true
fi

STORE_IN_BRAIN="false"
ARGS=()

for arg in "$@"; do
    case "$arg" in
        --store) STORE_IN_BRAIN="true" ;;
        *)       ARGS+=("$arg") ;;
    esac
done

if [ ${#ARGS[@]} -eq 0 ]; then
    echo "Usage: call_browser.sh [--store] <command> [args...]"
    echo "Commands: navigate, extract, markdown, screenshot, search, browse, agent, crawl, status"
    echo "  --store   Also store result in ClarvisDB brain"
    exit 1
fi

CMD="${ARGS[0]}"

RESULT=0
if [ "$CMD" = "crawl" ]; then
    URL="${ARGS[1]:-}"
    if [ -z "$URL" ]; then
        echo "Usage: call_browser.sh crawl <url>"
        exit 1
    fi
    python3 -c "
import asyncio, sys, json
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def main():
    browser_config = BrowserConfig(cdp_url='http://127.0.0.1:18800', headless=True)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=sys.argv[1], config=CrawlerRunConfig())
        output = {
            'url': result.url,
            'success': result.success,
            'markdown_length': len(result.markdown) if result.markdown else 0,
        }
        print(json.dumps(output, indent=2))
        if result.markdown:
            print('---MARKDOWN---')
            print(result.markdown[:4000])

asyncio.run(main())
" "$URL" || RESULT=$?
else
    python3 "$SCRIPT_DIR/browser_agent.py" "${ARGS[@]}" || RESULT=$?
fi

if [ "$STORE_IN_BRAIN" = "true" ] && [ $RESULT -eq 0 ]; then
    python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from brain import remember
cmd_str = ' '.join(sys.argv[1:])
remember(f'Browser action: {cmd_str}', importance=0.5)
print('[call_browser] Stored in brain')
" "${ARGS[@]}" 2>/dev/null || echo "[call_browser] WARN: brain store failed"
fi

exit $RESULT
