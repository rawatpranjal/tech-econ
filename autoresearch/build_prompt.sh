#!/usr/bin/env bash
# build_prompt.sh — Assembles the full prompt for an autoresearch iteration.
#
# Usage:
#   ./autoresearch/build_prompt.sh <template_file> <log_prefix> [prev_log_prefix]
#
# Arguments:
#   template_file    Path to the .md template describing the task
#   log_prefix       Path prefix for this iteration's log files
#   prev_log_prefix  Path prefix for the previous iteration's log files (optional)

set -euo pipefail

TEMPLATE_FILE="${1:?Usage: build_prompt.sh <template_file> <log_prefix> [prev_log_prefix]}"
LOG_PREFIX="${2:?Missing log_prefix}"
PREV_LOG_PREFIX="${3:-}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Template ──────────────────────────────────────────────────────────────────
echo "=== TASK TEMPLATE ==="
cat "$TEMPLATE_FILE"
echo ""

# ── Project context ───────────────────────────────────────────────────────────
echo "=== PROJECT ROOT ==="
echo "$PROJECT_ROOT"
echo ""

# ── What previous iterations already changed ─────────────────────────────────
# Critical context: tells Claude what's been done so it picks the NEXT improvement
BRANCH_COMMITS=$(git log --oneline main..HEAD 2>/dev/null || echo "")
if [[ -n "$BRANCH_COMMITS" ]]; then
    echo "=== PREVIOUS ITERATIONS (already committed — do NOT redo these) ==="
    echo "Commits:"
    echo "$BRANCH_COMMITS"
    echo ""
    echo "Files changed so far:"
    git diff --stat main..HEAD 2>/dev/null || true
    echo ""
fi

# ── Previous iteration checks (if any) ───────────────────────────────────────
if [[ -n "$PREV_LOG_PREFIX" ]]; then
    for check_file in "${PREV_LOG_PREFIX}"-check-*.txt; do
        [[ -e "$check_file" ]] || continue
        echo "=== PREVIOUS CHECK: $(basename "$check_file") ==="
        cat "$check_file"
        echo ""
    done
fi

# ── Previous iteration eval (if any) ─────────────────────────────────────────
if [[ -n "$PREV_LOG_PREFIX" ]]; then
    PREV_EVAL="${PREV_LOG_PREFIX}-eval.txt"
    if [[ -f "$PREV_EVAL" ]]; then
        echo "=== PREVIOUS EVAL ==="
        cat "$PREV_EVAL"
        echo ""
    fi
fi

# ── Current iteration log prefix ─────────────────────────────────────────────
echo "=== LOG PREFIX ==="
echo "$LOG_PREFIX"
echo ""
