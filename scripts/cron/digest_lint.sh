#!/usr/bin/env bash
# digest_lint.sh — regression guard for the digest writer pathway.
#
# Scans a target file for the failure modes observed during the
# 2026-04-25 [DIGEST_GARBLE_FIX] incident:
#   (a) literal \n-as-n chains: regex ',n  [a-z_]+:'
#   (b) unbalanced JSON-like braces (open != close, ignoring fenced code blocks)
#   (c) mid-word truncation at file end (last non-empty line not ending with
#       sentence/markdown punctuation: . ! ? ) * _ > : ] } ~ | = - ` " ' /)
#
# Usage:
#   digest_lint.sh <file>
#   cat sample.md | digest_lint.sh -
#
# Exit codes:
#   0 — clean
#   1 — failure detected (one-line reason on stdout)
#   2 — bad invocation

set -uo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: digest_lint.sh <file|->" >&2
    exit 2
fi

target="$1"
cleanup_tmp=""
if [[ "$target" == "-" ]]; then
    cleanup_tmp="$(mktemp)"
    cat - > "$cleanup_tmp"
    target="$cleanup_tmp"
fi
trap '[[ -n "$cleanup_tmp" ]] && rm -f "$cleanup_tmp"' EXIT

if [[ ! -f "$target" ]]; then
    echo "lint: target file not found: $target" >&2
    exit 2
fi

# (a) + (b) — both checks ignore content inside ``` fenced code blocks
#     (a) Literal \n-as-n chains — diagnostic signature of the 2026-04-25 garble
#     (b) Brace balance — open/close-curly counts must match
report=$(awk '
    BEGIN { open = 0; close_ = 0; in_fence = 0; gn_match = ""; gn_lineno = 0 }
    /^```/ { in_fence = 1 - in_fence; next }
    in_fence == 1 { next }
    {
        if (gn_match == "") {
            if (match($0, /,n  [a-z_]+:/)) {
                gn_match = substr($0, RSTART, RLENGTH)
                gn_lineno = NR
            }
        }
        n = length($0)
        for (i = 1; i <= n; i++) {
            c = substr($0, i, 1)
            if (c == "{") open++
            else if (c == "}") close_++
        }
    }
    END { print open " " close_ " " gn_lineno " " gn_match }
' "$target")
open_count=$(awk '{print $1}' <<<"$report")
close_count=$(awk '{print $2}' <<<"$report")
gn_lineno=$(awk '{print $3}' <<<"$report")
gn_match=$(awk '{$1=$2=$3=""; sub(/^   /,""); print}' <<<"$report")

if [[ "$gn_lineno" != "0" && -n "$gn_match" ]]; then
    echo "lint: literal-newline-as-n chain detected (pattern '${gn_match}' at line ${gn_lineno})"
    exit 1
fi
if [[ "$open_count" != "$close_count" ]]; then
    echo "lint: unbalanced JSON-like braces (open=$open_count close=$close_count)"
    exit 1
fi

# (c) Mid-word truncation at file end
last_line=$(awk 'NF { last = $0 } END { print last }' "$target")
if [[ -z "$last_line" ]]; then
    exit 0
fi
last_char="${last_line: -1}"
case "$last_char" in
    '.'|'!'|'?'|')'|'*'|'_'|'>'|':'|']'|'}'|'~'|'|'|'='|'-'|'`'|'"'|"'"|'/')
        ;;
    *)
        echo "lint: mid-word truncation at EOF (last line ends with '$last_char')"
        exit 1
        ;;
esac

exit 0
