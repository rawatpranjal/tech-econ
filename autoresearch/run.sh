#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# autoresearch/run.sh - Autonomous research loop
# ============================================================
# Runs Claude in a loop: prompt → implement → evaluate → commit/revert
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/config.sh"

# Parse arguments
PROGRAM=""
TASK_NAME=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --program)      PROGRAM="$2"; shift 2 ;;
        --max-iter)     AR_MAX_ITERATIONS="$2"; shift 2 ;;
        --budget)       AR_BUDGET_TOTAL="$2"; shift 2 ;;
        --model)        AR_MODEL="$2"; shift 2 ;;
        --timeout)      AR_TIMEOUT="$2"; shift 2 ;;
        --task)         TASK_NAME="$2"; shift 2 ;;
        *)              echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$PROGRAM" ]]; then
    echo "Usage: ./autoresearch/run.sh --program <template.md> [--max-iter N] [--budget N] [--model MODEL]"
    exit 1
fi

# Resolve program path
if [[ ! -f "$PROGRAM" ]] && [[ -f "$SCRIPT_DIR/templates/$PROGRAM" ]]; then
    PROGRAM="$SCRIPT_DIR/templates/$PROGRAM"
elif [[ ! -f "$PROGRAM" ]] && [[ -f "$SCRIPT_DIR/$PROGRAM" ]]; then
    PROGRAM="$SCRIPT_DIR/$PROGRAM"
fi

if [[ ! -f "$PROGRAM" ]]; then
    echo "Error: Program file not found: $PROGRAM"
    exit 1
fi

# Derive task name from program filename
if [[ -z "$TASK_NAME" ]]; then
    TASK_NAME=$(basename "$PROGRAM" .md | sed 's/[^a-zA-Z0-9]/-/g')
fi

BRANCH="autoresearch/$TASK_NAME"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_DIR="$SCRIPT_DIR/log/${TASK_NAME}-${TIMESTAMP}"
STATE_FILE="$SCRIPT_DIR/state.json"

mkdir -p "$LOG_DIR"

echo "============================================"
echo "AUTORESEARCH SESSION"
echo "============================================"
echo "Task:       $TASK_NAME"
echo "Program:    $PROGRAM"
echo "Model:      $AR_MODEL"
echo "Max iter:   $AR_MAX_ITERATIONS"
echo "Budget:     \$$AR_BUDGET_TOTAL total, \$$AR_BUDGET_PER_ITER/iter"
echo "Timeout:    ${AR_TIMEOUT}s per iteration"
echo "Log dir:    $LOG_DIR"
echo "============================================"

cd "$PROJECT_ROOT"

# Create or switch to branch
if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    git checkout "$BRANCH"
    echo "Already on branch: $BRANCH"
else
    git checkout -b "$BRANCH"
    echo "Creating branch: $BRANCH"
fi

# Initialize state
TOTAL_COST=0
CONSECUTIVE_NO_CHANGES=0

# Save initial state
cat > "$STATE_FILE" <<EOJSON
{
  "task_name": "$TASK_NAME",
  "branch": "$BRANCH",
  "iteration": 0,
  "status": "running",
  "total_cost_usd": 0,
  "iterations": []
}
EOJSON

# Main loop
for ((ITER=1; ITER<=AR_MAX_ITERATIONS; ITER++)); do
    echo ""
    echo "========== ITERATION $ITER / $AR_MAX_ITERATIONS =========="

    ITER_LOG_PREFIX="$LOG_DIR/iter-$(printf '%03d' $ITER)"
    ITER_START=$(date +%s)

    # Step 1: Build prompt
    PROMPT_FILE="${ITER_LOG_PREFIX}-prompt.txt"
    # build_prompt.sh takes positional args: template_file log_prefix [prev_log_prefix]
    PREV_LOG_PREFIX=""
    if [[ $ITER -gt 1 ]]; then
        PREV_LOG_PREFIX="$LOG_DIR/iter-$(printf '%03d' $((ITER-1)))"
    fi
    bash "$SCRIPT_DIR/build_prompt.sh" \
        "$PROGRAM" \
        "$ITER_LOG_PREFIX" \
        "$PREV_LOG_PREFIX" \
        > "$PROMPT_FILE" 2>/dev/null
    PROMPT_SIZE=$(wc -c < "$PROMPT_FILE" | tr -d ' ')
    echo "  Prompt built ($PROMPT_SIZE bytes)"

    # Snapshot repo state BEFORE Claude runs (so we only revert what this iteration changed)
    DIRTY_BEFORE="${ITER_LOG_PREFIX}-dirty-before.txt"
    { git diff --name-only; git diff --name-only --cached; git ls-files --others --exclude-standard; } | sort -u > "$DIRTY_BEFORE"

    # Step 2: Invoke Claude
    echo "  Invoking Claude ($AR_MODEL)..."
    CLAUDE_STDERR="${ITER_LOG_PREFIX}-claude-stderr.txt"

    COST=0
    CLAUDE_STATUS="CONTINUE"

    # Run Claude with the prompt (no timeout on macOS, use --max-turns to limit)
    if claude --model "$AR_MODEL" \
        --max-turns 25 \
        --verbose \
        -p "$(cat "$PROMPT_FILE")" \
        > /dev/null 2>"$CLAUDE_STDERR"; then
        CLAUDE_STATUS="CONTINUE"
    else
        echo "  Claude failed (exit $?)"
        CLAUDE_STATUS="ERROR"
    fi

    TOTAL_COST=$(python3 -c "print(round($TOTAL_COST + $COST, 4))")
    echo "  Iteration cost: \$$COST (total: \$$TOTAL_COST)"

    # Step 3: Check for changes
    CHANGES=$(git diff --stat 2>/dev/null || echo "")
    NEW_FILES=$(git ls-files --others --exclude-standard 2>/dev/null || echo "")

    if [[ -z "$CHANGES" && -z "$NEW_FILES" ]]; then
        echo "  No changes detected"
        CONSECUTIVE_NO_CHANGES=$((CONSECUTIVE_NO_CHANGES + 1))
        if [[ $CONSECUTIVE_NO_CHANGES -ge 3 ]]; then
            echo "  3 consecutive no-op iterations — stopping"
            break
        fi
        continue
    fi

    CONSECUTIVE_NO_CHANGES=0
    echo "  Changes detected:"
    echo "$CHANGES" | sed 's/^/     /'
    if [[ -n "$NEW_FILES" ]]; then
        echo "  New files:"
        echo "$NEW_FILES" | sed 's/^/    /'
    fi
    echo "  Claude status: $CLAUDE_STATUS"

    # Step 4: Evaluate
    echo "  Running evaluation..."
    EVAL_FILE="${ITER_LOG_PREFIX}-eval.txt"
    EVAL_PASSED=false

    if bash "$SCRIPT_DIR/evaluate.sh" \
        --task "$TASK_NAME" \
        --project-root "$PROJECT_ROOT" \
        --log-prefix "$ITER_LOG_PREFIX" \
        > "$EVAL_FILE" 2>&1; then
        EVAL_PASSED=true
    fi

    EVAL_RESULT=$(tail -1 "$EVAL_FILE" 2>/dev/null || echo "UNKNOWN")
    echo "  Eval result: $EVAL_RESULT"

    # Step 5: Commit or revert
    if $EVAL_PASSED; then
        echo "  Eval PASSED -- committing"
        git add -A
        git commit -m "autoresearch($TASK_NAME): iteration $ITER

$EVAL_RESULT
Cost: \$$COST" --no-verify 2>/dev/null || true
    else
        echo "  Eval FAILED -- reverting changes from this iteration only"
        DIRTY_AFTER="${ITER_LOG_PREFIX}-dirty-after.txt"
        { git diff --name-only; git diff --name-only --cached; git ls-files --others --exclude-standard; } | sort -u > "$DIRTY_AFTER"

        # Only revert files that became dirty DURING this iteration
        ITER_CHANGES=$(comm -13 "$DIRTY_BEFORE" "$DIRTY_AFTER")
        if [[ -n "$ITER_CHANGES" ]]; then
            echo "$ITER_CHANGES" | while read -r f; do
                if git ls-files --error-unmatch "$f" &>/dev/null; then
                    git checkout -- "$f" 2>/dev/null || true
                else
                    rm -f "$f" 2>/dev/null || true
                fi
            done
        fi
    fi

    ITER_END=$(date +%s)
    DURATION=$((ITER_END - ITER_START))

    # Update state
    python3 -c "
import json
try:
    state = json.load(open('$STATE_FILE'))
except:
    state = {'iterations': []}
state['iteration'] = $ITER
state['total_cost_usd'] = $TOTAL_COST
state['iterations'].append({
    'number': $ITER,
    'eval_passed': $( $EVAL_PASSED && echo 'true' || echo 'false' ),
    'cost_usd': $COST,
    'duration_seconds': $DURATION,
    'claude_status': '$CLAUDE_STATUS',
    'eval_result': '$EVAL_RESULT'
})
json.dump(state, open('$STATE_FILE', 'w'), indent=2)
" 2>/dev/null || true

    # Budget check
    OVER_BUDGET=$(python3 -c "print('yes' if $TOTAL_COST >= $AR_BUDGET_TOTAL else 'no')")
    if [[ "$OVER_BUDGET" == "yes" ]]; then
        echo "  Budget limit reached (\$$TOTAL_COST >= \$$AR_BUDGET_TOTAL)"
        break
    fi
done

echo ""
echo "============================================"
echo "SESSION COMPLETE"
echo "============================================"
echo "Iterations: $ITER"
echo "Total cost: \$$TOTAL_COST"
echo "Branch:     $BRANCH"
echo "Log dir:    $LOG_DIR"
echo "============================================"

# Update final state
python3 -c "
import json
try:
    state = json.load(open('$STATE_FILE'))
    state['status'] = 'completed'
    json.dump(state, open('$STATE_FILE', 'w'), indent=2)
except:
    pass
" 2>/dev/null || true

# Switch back to main
git checkout main 2>/dev/null || true
