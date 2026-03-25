#!/usr/bin/env bash
# evaluate.sh — Runs post-iteration checks for an autoresearch task.
#
# Usage:
#   ./autoresearch/evaluate.sh <task_description> <log_prefix> [project_root]
#
# Arguments:
#   task_description  Short string describing the task (used to pick checks)
#   log_prefix        Path prefix for this iteration's log files
#   project_root      Optional project root (defaults to repo root)
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed

set -euo pipefail

TASK_DESC="${1:?Usage: evaluate.sh <task_description> <log_prefix> [project_root]}"
LOG_PREFIX="${2:?Missing log_prefix}"
PROJECT_ROOT="${3:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

CHECKS_DIR="$PROJECT_ROOT/autoresearch/checks"
PASS=0
FAIL=0
CHECK_LOG="${LOG_PREFIX}-eval.txt"

log() {
    echo "$@" | tee -a "$CHECK_LOG"
}

run_check() {
    local check_script="$1"
    local check_name
    check_name="$(basename "$check_script" .py)"
    local out_file="${LOG_PREFIX}-check-${check_name}.txt"

    if [[ ! -f "$check_script" ]]; then
        log "SKIP  $check_name (script not found)"
        return
    fi

    if python3 "$check_script" \
        --project-root "$PROJECT_ROOT" \
        --log-prefix "$LOG_PREFIX" \
        > "$out_file" 2>&1; then
        log "PASS  $check_name"
        PASS=$(( PASS + 1 ))
    else
        log "FAIL  $check_name"
        cat "$out_file" | tee -a "$CHECK_LOG"
        FAIL=$(( FAIL + 1 ))
    fi
}

# ── Task type detection ───────────────────────────────────────────────────────
TASK_TYPE="generic"

case "$TASK_DESC" in
    *homepage* | *row*)                 TASK_TYPE="homepage_rows" ;;
    *telemetry* | *analytics* | *track*) TASK_TYPE="telemetry" ;;
    *rank* | *score*)                   TASK_TYPE="ranking" ;;
    *search* | *embed*)                 TASK_TYPE="search" ;;
    *cluster*)                          TASK_TYPE="clustering" ;;
    *)                                  TASK_TYPE="generic" ;;
esac

log "=== EVALUATE: $TASK_DESC ==="
log "Task type: $TASK_TYPE"
log "Log prefix: $LOG_PREFIX"
log ""

# ── Always run: validate data and build ───────────────────────────────────────
log "--- Core checks ---"

if python3 "$PROJECT_ROOT/scripts/validate_data.py" \
    > "${LOG_PREFIX}-check-validate_data.txt" 2>&1; then
    log "PASS  validate_data"
    PASS=$(( PASS + 1 ))
else
    log "FAIL  validate_data"
    cat "${LOG_PREFIX}-check-validate_data.txt" | tee -a "$CHECK_LOG"
    FAIL=$(( FAIL + 1 ))
fi

# ── Task-specific checks ──────────────────────────────────────────────────────
log ""
log "--- Task-specific checks ($TASK_TYPE) ---"

case "$TASK_TYPE" in
    homepage_rows)
        run_check "$CHECKS_DIR/check_homepage_rows.py"
        ;;
    ranking)
        run_check "$CHECKS_DIR/check_rankings.py"
        ;;
    search)
        run_check "$CHECKS_DIR/check_search.py"
        ;;
    clustering)
        run_check "$CHECKS_DIR/check_clusters.py"
        ;;
    telemetry)
        run_check "$CHECKS_DIR/check_telemetry.py"
        ;;
    *)
        log "SKIP  No task-specific checks for '$TASK_TYPE'"
        ;;
esac

# ── Summary ───────────────────────────────────────────────────────────────────
log ""
log "=== RESULT: $PASS passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
