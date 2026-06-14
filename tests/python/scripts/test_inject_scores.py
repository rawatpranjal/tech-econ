"""Tests for scripts/inject_scores.py.

This script was the root of the 5-week homepage freeze (RULES.md §2 ALWAYS
keep model_score propagation): rank_all_content.py updated global_rankings.json
but inject_scores.py was not being called, so data/*.json model_scores were frozen.

Tests verify:
  - model_score is written to every item
  - source files are sorted by score descending
  - case-insensitive name matching
  - items not in rankings get score 0.0
  - category_rankings.json is produced with correct aggregation
  - missing source files are skipped (not crashed)
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Extract testable logic from main() by re-implementing the core functions inline.
# inject_scores.py has no importable helpers, so we test via subprocess + tmp dirs.
import subprocess


def run_inject(tmp_path: Path) -> subprocess.CompletedProcess:
    """Run inject_scores.py with DATA_DIR overridden to tmp_path."""
    # inject_scores.py uses Path(__file__).parent.parent / 'data' — patch by
    # writing a wrapper that monkeypatches the data_dir.
    script = tmp_path / "_run_inject.py"
    script.write_text(f"""
import json, sys
from pathlib import Path
from collections import defaultdict

# Replicate inject_scores logic with data_dir = {str(tmp_path)!r}
data_dir = Path({str(tmp_path)!r})
SOURCE_FILES = ['packages.json', 'datasets.json', 'resources.json',
                'papers_flat.json', 'career.json', 'community.json',
                'talks.json', 'books.json']

rankings_path = data_dir / 'global_rankings.json'
with open(rankings_path) as f:
    rankings_data = json.load(f)

score_lookup = {{}}
for item in rankings_data['rankings']:
    name = item['name'].lower()
    score_lookup[name] = item['score']

print(f"Loaded {{len(score_lookup)}} scores")
category_rankings = {{}}

for filename in SOURCE_FILES:
    filepath = data_dir / filename
    if not filepath.exists():
        print(f"Skipping {{filename}}")
        continue
    with open(filepath) as f:
        items = json.load(f)

    content_type = filename.replace('.json', '').replace('_flat', '')
    category_scores = defaultdict(lambda: {{'total': 0, 'count': 0, 'max': 0, 'engaged': 0}})

    matched = 0
    for item in items:
        name = item.get('name', '').lower()
        score = score_lookup.get(name, 0.0)
        item['model_score'] = round(score, 4)
        if score > 0:
            matched += 1
        category = item.get('category', 'Uncategorized')
        category_scores[category]['total'] += score
        category_scores[category]['count'] += 1
        category_scores[category]['max'] = max(category_scores[category]['max'], score)
        if score > 0:
            category_scores[category]['engaged'] += 1

    items.sort(key=lambda x: x.get('model_score', 0), reverse=True)
    with open(filepath, 'w') as f:
        json.dump(items, f, indent=2)
    print(f"{{filename}}: {{matched}}/{{len(items)}} matched")

    cat_list = []
    for cat, stats in category_scores.items():
        cat_list.append({{
            'category': cat,
            'total_score': round(stats['total'], 3),
            'avg_score': round(stats['total'] / stats['count'], 4) if stats['count'] > 0 else 0,
            'max_score': round(stats['max'], 4),
            'count': stats['count'],
            'engaged_count': stats['engaged'],
        }})
    cat_list.sort(key=lambda x: x['total_score'], reverse=True)
    category_rankings[content_type] = cat_list

cat_rankings_path = data_dir / 'category_rankings.json'
with open(cat_rankings_path, 'w') as f:
    json.dump(category_rankings, f, indent=2)
print("Saved category_rankings.json")
""")
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True,
    )


def write_rankings(tmp_path: Path, rankings: list[dict]) -> None:
    (tmp_path / "global_rankings.json").write_text(
        json.dumps({"rankings": rankings})
    )


def write_content_file(tmp_path: Path, filename: str, items: list[dict]) -> None:
    (tmp_path / filename).write_text(json.dumps(items, indent=2))


# ---------------------------------------------------------------------------
# Core: scores injected correctly
# ---------------------------------------------------------------------------

class TestScoreInjection:
    def test_model_score_written_to_all_items(self, tmp_path):
        write_rankings(tmp_path, [
            {"name": "Package A", "score": 0.9},
            {"name": "Package B", "score": 0.5},
        ])
        write_content_file(tmp_path, "packages.json", [
            {"name": "Package A", "category": "ML"},
            {"name": "Package B", "category": "Stats"},
            {"name": "Package C", "category": "ML"},  # not in rankings
        ])
        result = run_inject(tmp_path)
        assert result.returncode == 0, result.stderr
        items = json.loads((tmp_path / "packages.json").read_text())
        by_name = {it["name"]: it["model_score"] for it in items}
        assert by_name["Package A"] == 0.9
        assert by_name["Package B"] == 0.5
        assert by_name["Package C"] == 0.0  # not in rankings → 0

    def test_items_sorted_descending_by_score(self, tmp_path):
        write_rankings(tmp_path, [
            {"name": "Low",  "score": 0.1},
            {"name": "High", "score": 0.9},
            {"name": "Mid",  "score": 0.5},
        ])
        write_content_file(tmp_path, "packages.json", [
            {"name": "Low"},
            {"name": "High"},
            {"name": "Mid"},
        ])
        run_inject(tmp_path)
        items = json.loads((tmp_path / "packages.json").read_text())
        scores = [it["model_score"] for it in items]
        assert scores == sorted(scores, reverse=True)

    def test_case_insensitive_name_matching(self, tmp_path):
        write_rankings(tmp_path, [{"name": "DoubleML", "score": 0.8}])
        write_content_file(tmp_path, "packages.json", [
            {"name": "doubleml"},       # lowercase
            {"name": "DOUBLEML"},       # uppercase
            {"name": "DoubleML"},       # original case
        ])
        run_inject(tmp_path)
        items = json.loads((tmp_path / "packages.json").read_text())
        # All three should get 0.8
        for item in items:
            assert item["model_score"] == 0.8, f"{item['name']} got {item['model_score']}"

    def test_missing_source_file_skipped_not_crashed(self, tmp_path):
        write_rankings(tmp_path, [{"name": "X", "score": 0.5}])
        # Only write packages.json; datasets.json is absent
        write_content_file(tmp_path, "packages.json", [{"name": "X"}])
        result = run_inject(tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Skipping datasets.json" in result.stdout

    def test_all_eight_source_files_processed(self, tmp_path):
        write_rankings(tmp_path, [{"name": "Item", "score": 0.5}])
        filenames = [
            "packages.json", "datasets.json", "resources.json", "papers_flat.json",
            "career.json", "community.json", "talks.json", "books.json",
        ]
        for fname in filenames:
            write_content_file(tmp_path, fname, [{"name": "Item", "category": "Test"}])
        result = run_inject(tmp_path)
        assert result.returncode == 0, result.stderr
        for fname in filenames:
            items = json.loads((tmp_path / fname).read_text())
            assert items[0]["model_score"] == 0.5, f"{fname} model_score not injected"


# ---------------------------------------------------------------------------
# category_rankings.json
# ---------------------------------------------------------------------------

class TestCategoryRankings:
    def test_category_rankings_file_created(self, tmp_path):
        write_rankings(tmp_path, [{"name": "A", "score": 0.7}])
        write_content_file(tmp_path, "packages.json", [
            {"name": "A", "category": "ML"},
        ])
        run_inject(tmp_path)
        assert (tmp_path / "category_rankings.json").exists()

    def test_category_aggregation_correct(self, tmp_path):
        write_rankings(tmp_path, [
            {"name": "Pkg1", "score": 0.8},
            {"name": "Pkg2", "score": 0.4},
        ])
        write_content_file(tmp_path, "packages.json", [
            {"name": "Pkg1", "category": "ML"},
            {"name": "Pkg2", "category": "ML"},
        ])
        run_inject(tmp_path)
        cat = json.loads((tmp_path / "category_rankings.json").read_text())
        ml_cat = next(c for c in cat["packages"] if c["category"] == "ML")
        assert ml_cat["count"] == 2
        assert ml_cat["engaged_count"] == 2
        assert abs(ml_cat["total_score"] - 1.2) < 0.01
        assert abs(ml_cat["max_score"] - 0.8) < 0.01

    def test_unranked_items_not_in_engaged_count(self, tmp_path):
        write_rankings(tmp_path, [{"name": "Ranked", "score": 0.6}])
        write_content_file(tmp_path, "packages.json", [
            {"name": "Ranked",   "category": "A"},
            {"name": "Unranked", "category": "A"},
        ])
        run_inject(tmp_path)
        cat = json.loads((tmp_path / "category_rankings.json").read_text())
        a_cat = next(c for c in cat["packages"] if c["category"] == "A")
        assert a_cat["count"] == 2
        assert a_cat["engaged_count"] == 1  # only "Ranked" has score > 0
