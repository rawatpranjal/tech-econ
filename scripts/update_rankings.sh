#!/bin/bash
set -e
cd /Users/pranjal/metrics-packages

echo "=== Fetching analytics & running ranking model ==="
python3 scripts/rank_all_content.py

echo "=== Rebuilding site ==="
hugo --gc --minify

echo "=== Committing changes ==="
git add data/*.json static/data/*.json hugo_stats.json
git commit -m "$(cat <<'EOF'
Update model_score with latest engagement data

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)" || echo "No changes to commit"

git push

echo "=== Done ==="
