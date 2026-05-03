#!/bin/bash
set -e
cd /Users/pranjal/Code/tech-econ

# Load CLOUDFLARE_API_TOKEN so wrangler can auth non-interactively. Without
# this the rerank silently falls back to cold-start scoring (the failure
# mode that hid the 2026-03-26 → 05-03 analytics blackout).
if [ -f .claude/secrets.env ]; then
  set -a
  # shellcheck source=/dev/null
  . .claude/secrets.env
  set +a
fi

echo "=== Fetching analytics & running ranking model ==="
python3 scripts/rank_all_content.py --source api

echo "=== Injecting scores into source data files ==="
# Reads data/global_rankings.json and writes model_score back into
# data/{papers_flat,packages,datasets,resources,career,community,
# talks,books}.json + data/category_rankings.json. Hugo templates
# read model_score from the source files (not global_rankings),
# so this step is required for any UI ordering change to land.
# Last manual run was 2026-03-30; before this fix the weekly cron
# would update global_rankings but leave the source files frozen.
python3 scripts/inject_scores.py

echo "=== Rebuilding site ==="
hugo --gc --minify

echo "=== Committing changes ==="
# reports/metrics.csv is produced by the new offline-eval gate inside
# rank_all_content.py (Phase 1, master_recsys_planner.md). Stage it
# alongside the data updates when present -- if the eval gate skipped
# (eg. D1 unreachable), the file may not exist yet and we shouldn't
# fail the whole rerank.
git add data/*.json static/data/*.json hugo_stats.json
[ -f reports/metrics.csv ] && git add reports/metrics.csv
git commit -m "$(cat <<'EOF'
Update model_score with latest engagement data

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" || echo "No changes to commit"

git push

echo "=== Done ==="
