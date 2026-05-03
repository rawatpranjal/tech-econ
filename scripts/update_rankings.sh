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

echo "=== Rebuilding site ==="
hugo --gc --minify

echo "=== Committing changes ==="
# reports/metrics.csv is produced by the new offline-eval gate inside
# rank_all_content.py (Phase 1, master_recsys_planner.md). Stage it
# alongside the data updates so the time-series stays in git.
git add data/*.json static/data/*.json hugo_stats.json reports/metrics.csv
git commit -m "$(cat <<'EOF'
Update model_score with latest engagement data

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" || echo "No changes to commit"

git push

echo "=== Done ==="
