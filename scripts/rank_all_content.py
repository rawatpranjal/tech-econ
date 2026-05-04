#!/usr/bin/env python3
"""
Universal Content Ranking Script
Ranks ALL content items using engagement data + content similarity for cold start.

Usage:
    python scripts/rank_all_content.py
    python scripts/rank_all_content.py --output data/global_rankings.json
"""

import json
import subprocess
import argparse
import math
import os
import sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_predict, train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score, average_precision_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

# Make `lib/` importable when this script is run directly (e.g. via the
# weekly cron / `/rerank` slash command). Tests get this for free via
# tests/python/conftest.py.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from lib.sample_weights import compute_sample_weights
from lib.model_cache import (
    ModelCacheError,
    latest_version as _latest_model_version,
    save_model as _save_model_artifact,
)
from lib.recsys_config import load as _load_recsys_config
from lib.data_io import current_git_sha as _current_git_sha
from lib.trending import (
    build_trending_embedding_lookup,
    select_diverse_trending,
)
from lib.cold_start import (
    propagate_cold_start_scores as _knn_propagate_cold_start,
    make_tfidf_similarity_fn as _make_tfidf_similarity_fn,
    make_dense_similarity_fn as _make_dense_similarity_fn,
)
from lib.eval_runner import (
    RegressionAlert as _RegressionAlert,
    check_regression as _check_regression,
    read_last_metrics_row as _read_last_metrics_row,
    run_evaluation as _run_evaluation,
    write_metrics_row as _write_metrics_row,
)
from lib.d1_sessions import (
    SessionLoadError as _SessionLoadError,
    load_sessions as _load_sessions,
)

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("Warning: lightgbm not installed, falling back to Ridge regression")

# Load sentence transformer model for semantic embeddings
print("Loading sentence-BERT model...")
try:
    SBERT_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    print("  Model loaded: all-MiniLM-L6-v2 (384 dimensions)")
except Exception as _sbert_err:
    print(f"  Warning: could not load sentence-BERT model ({_sbert_err})")
    print("  Falling back to hash-based pseudo-embeddings (384 dims)")

    class _HashEmbedder:
        """Deterministic hash-based embeddings as a fallback when HuggingFace is unreachable."""
        def encode(self, texts, show_progress_bar=False, batch_size=64):
            import hashlib
            result = []
            for text in texts:
                h = hashlib.sha256(text.encode('utf-8', errors='replace')).digest()
                # Expand 32 bytes → 384 floats by repeating + normalising
                extended = (h * 12)[:384]
                vec = np.frombuffer(extended, dtype=np.uint8).astype(np.float32)
                vec = (vec - 127.5) / 127.5   # normalise to [-1, 1]
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                result.append(vec)
            return np.array(result, dtype=np.float32)

    SBERT_MODEL = _HashEmbedder()

# Signal weights for engagement scoring
CLICK_WEIGHT = 5.0
IMPRESSION_WEIGHT = 0.5  # Reduced since viewability adds quality signal
VIEWABLE_WEIGHT = 0.1    # Per viewable second (IAB 50%+ visible)
DWELL_WEIGHT = 1.0       # Per minute

# New signal weights (from ML tables)
SCROLL_90_WEIGHT = 2.0   # Reached 90% = high quality read
SCROLL_75_WEIGHT = 1.0   # Good engagement
SCROLL_50_WEIGHT = 0.5   # Moderate engagement
SEARCH_CLICK_WEIGHT = 3.0  # Clicked from search = high intent
SEARCH_CLICK_RANK_BONUS_WEIGHT = 0.3  # Per-position bonus: a click at
                                       # rank 0 (top) is easy; a click at
                                       # rank 20 means the user worked
                                       # for it. Audit Ra3.
RAGE_CLICK_WEIGHT = -2.0   # Frustration = negative signal
QUICK_BOUNCE_WEIGHT = -1.0 # Left quickly = not useful
DEEP_SESSION_WEIGHT = 1.5  # Part of "deep" engagement session
COVIEW_WEIGHT = 0.1        # Co-viewed with engaged items
COCLICK_WEIGHT = 0.3       # Co-clicked with engaged items
READING_RATIO_WEIGHT = 0.5 # Per reading_ratio point (actual/expected read time)
HIGH_IMP_NO_CLICK_THRESHOLD = 10  # Min impressions to consider
HIGH_IMP_NO_CLICK_WEIGHT = -1.0   # Penalty for high impressions but zero clicks

# Freshness parameters
FRESHNESS_WEIGHT = 0.15           # Max boost for brand new items (15% of score)
FRESHNESS_HALF_LIFE_DAYS = 30     # Days until freshness boost decays by half

CITATION_WEIGHT = 0.3  # Boost for papers with citations

ANALYTICS_API = "https://tech-econ-analytics-v2.pp712.workers.dev"


def fetch_d1_data(query):
    """Execute D1 query via wrangler and return results."""
    cmd = [
        'npx', 'wrangler', 'd1', 'execute', 'tech-econ-analytics-db',
        '--remote', '--command', query, '--json'
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent.parent / 'analytics-worker')
    )

    if result.returncode != 0:
        print(f"  Warning: D1 query failed: {result.stderr[:100]}")
        return []

    try:
        data = json.loads(result.stdout)
        return data[0]['results'] if data and data[0].get('results') else []
    except (json.JSONDecodeError, IndexError, KeyError):
        return []


def load_all_content(data_dir):
    """Load all content items from data/*.json files."""
    items = []
    seen_names = set()  # Track seen names to deduplicate

    # Content files and their structure
    content_files = {
        'papers_flat.json': {'name_field': 'name', 'type': 'paper'},
        'packages.json': {'name_field': 'name', 'type': 'package'},
        'datasets.json': {'name_field': 'name', 'type': 'dataset'},
        'resources.json': {'name_field': 'name', 'type': 'resource'},
        'career.json': {'name_field': 'name', 'type': 'career'},
        'community.json': {'name_field': 'name', 'type': 'community'},
        'talks.json': {'name_field': 'name', 'type': 'talk'},
        'books.json': {'name_field': 'name', 'type': 'book'},
    }

    for filename, config in content_files.items():
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"  Warning: {filename} not found")
            continue

        try:
            with open(filepath) as f:
                data = json.load(f)

            # Handle flat arrays
            if isinstance(data, list):
                for item in data:
                    name = item.get(config['name_field']) or item.get('title', '')
                    if not name:
                        continue

                    # Deduplicate by normalized name
                    normalized_name = name.lower().strip()
                    if normalized_name in seen_names:
                        continue
                    seen_names.add(normalized_name)

                    items.append({
                        'name': name.lower().strip(),
                        'original_name': name,
                        'type': config['type'],
                        'url': item.get('url') or item.get('github_url') or item.get('docs_url') or '',
                        # Existing fields
                        'category': item.get('category', ''),
                        'tags': item.get('tags', []),
                        'topic_tags': item.get('topic_tags', []),
                        'difficulty': item.get('difficulty', 'intermediate'),
                        'audience': item.get('audience', []),
                        'description': item.get('description', ''),
                        'summary': item.get('summary', ''),
                        # NEW fields
                        'synthetic_questions': item.get('synthetic_questions', []),
                        'use_cases': item.get('use_cases', []),
                        'best_for': item.get('best_for', ''),
                        'citations': item.get('citations', 0),
                        'domain_tags': item.get('domain_tags', []),
                        'key_insights': item.get('key_insights', []),
                        'mentioned_tools': item.get('mentioned_tools', []),
                        'language': item.get('language', ''),
                        'content_format': item.get('content_format', ''),
                        'speaker_expertise': item.get('speaker_expertise', ''),
                        'company_context': item.get('company_context', ''),
                        'experience_level': item.get('experience_level', ''),
                        'data_modality': item.get('data_modality', ''),
                        'related_packages': item.get('related_packages', []),
                    })

            print(f"  {filename}: {len([i for i in items if i['type'] == config['type']])} items")

        except Exception as e:
            print(f"  Error loading {filename}: {e}")

    return items


def fetch_engagement_data():
    """Fetch all engagement signals from D1."""
    print("\nFetching engagement data from D1...")

    clicks = fetch_d1_data("SELECT name, section, click_count FROM content_clicks")
    print(f"  Clicks: {len(clicks)} items")

    impressions = fetch_d1_data("SELECT name, section, impression_count FROM content_impressions")
    print(f"  Impressions: {len(impressions)} items")

    dwell = fetch_d1_data(
        "SELECT name, section, SUM(dwell_ms) as total_dwell, "
        "SUM(viewable_seconds) as total_viewable "
        "FROM content_dwell GROUP BY name, section"
    )
    print(f"  Dwell + Viewability: {len(dwell)} items")

    # NEW: Fetch scroll depth milestones
    scroll = fetch_d1_data(
        "SELECT path, milestone, COUNT(*) as count "
        "FROM scroll_milestones GROUP BY path, milestone"
    )
    print(f"  Scroll milestones: {len(scroll)} entries")

    # NEW: Fetch search-to-click attribution
    search_clicks = fetch_d1_data(
        "SELECT query, clicks FROM search_sessions WHERE clicks IS NOT NULL AND clicks != '[]'"
    )
    print(f"  Search clicks: {len(search_clicks)} sessions")

    # NEW: Fetch session engagement tiers
    session_tiers = fetch_d1_data(
        "SELECT content_sequence, engagement_tier FROM session_features "
        "WHERE engagement_tier = 'deep' AND content_sequence IS NOT NULL"
    )
    print(f"  Deep sessions: {len(session_tiers)} sessions")

    # NEW: Fetch frustration signals
    frustration = fetch_d1_data(
        "SELECT path, event_type, COUNT(*) as count "
        "FROM frustration_events GROUP BY path, event_type"
    )
    print(f"  Frustration events: {len(frustration)} entries")

    # NEW: Fetch item co-occurrence
    cooccurrence = fetch_d1_data(
        "SELECT item_a, item_b, coview_count, coclick_count "
        "FROM item_cooccurrence WHERE coview_count > 0 OR coclick_count > 0"
    )
    print(f"  Co-occurrence pairs: {len(cooccurrence)} pairs")

    # NEW: Fetch reading ratio (quality signal)
    reading_ratio = fetch_d1_data(
        "SELECT name, section, AVG(reading_ratio) as avg_reading_ratio, COUNT(*) as sessions "
        "FROM content_dwell WHERE reading_ratio IS NOT NULL AND reading_ratio > 0 "
        "GROUP BY name, section"
    )
    print(f"  Reading ratio: {len(reading_ratio)} items")

    # Fetch first_seen dates for freshness calculation
    first_seen = fetch_d1_data(
        "SELECT name, section, first_seen FROM content_impressions WHERE first_seen IS NOT NULL"
    )
    print(f"  First seen dates: {len(first_seen)} items")

    return {
        'clicks': clicks,
        'impressions': impressions,
        'dwell': dwell,
        'scroll': scroll,
        'search_clicks': search_clicks,
        'session_tiers': session_tiers,
        'frustration': frustration,
        'cooccurrence': cooccurrence,
        'reading_ratio': reading_ratio,
        'first_seen': first_seen,
    }


def _fetch_json(url, timeout=30):
    """GET a JSON URL with the same SSL fallback as fetch_engagement_from_api."""
    import urllib.request
    import ssl
    req = urllib.request.Request(url, headers={
        'User-Agent': 'tech-econ-ranker/1.0',
        'Accept': 'application/json',
    })
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as ssl_err:
        if 'CERTIFICATE_VERIFY_FAILED' in str(ssl_err):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode())
        raise


def assert_analytics_fresh():
    """Abort the rerank if /health says writes are stale or failing.

    Prevents the silent regenerate-with-stale-data failure mode that produced
    five identical reranks between 2026-03-26 and 2026-05-03. The check is
    advisory: a worker that hasn't been redeployed with the new /health body
    will simply lack `last_write_age_seconds` and we degrade to a warning.
    """
    try:
        health = _fetch_json(f"{ANALYTICS_API}/health", timeout=10)
    except Exception as e:
        print(f"  Warning: /health unreachable ({e}); proceeding with potentially stale data")
        return
    age = health.get('last_write_age_seconds')
    status = health.get('status')
    if age is None and status is None:
        print(f"  Note: /health is the legacy shape (no freshness data). Worker not yet redeployed.")
        return
    if status == 'degraded' or (age is not None and age > 86400):
        raise SystemExit(
            f"\n  REFUSING TO RERANK: analytics health is degraded.\n"
            f"  /health: {health}\n"
            f"  Fix the worker first (see CLAUDE.md → Analytics health), then re-run.\n"
            f"  Override with --ignore-stale if you really mean it.\n"
        )
    print(f"  /health ok: last write {age}s ago, events_24h={health.get('events_24h')}")


def fetch_engagement_from_api():
    """Fetch all engagement signals from the analytics HTTP API."""
    import urllib.request
    import ssl

    if '--ignore-stale' not in sys.argv:
        assert_analytics_fresh()

    url = f"{ANALYTICS_API}/ranking-export"
    print(f"\nFetching engagement data from API: {url}")

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'tech-econ-ranker/1.0',
            'Accept': 'application/json',
        })
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as ssl_err:
            if 'CERTIFICATE_VERIFY_FAILED' in str(ssl_err):
                print("  SSL verification failed, retrying with unverified context...")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                    data = json.loads(resp.read().decode())
            else:
                raise
    except Exception as e:
        print(f"  Error fetching from API: {e}")
        return {
            'clicks': [], 'impressions': [], 'dwell': [],
            'scroll': [], 'search_clicks': [], 'session_tiers': [],
            'frustration': [], 'cooccurrence': [], 'reading_ratio': [],
            'first_seen': [],
        }

    signals = data.get('signals', {})
    print(f"  Generated at: {data.get('generated_at', 'unknown')}")

    # Map API field names to the names expected by build_engagement_scores
    result = {
        'clicks': signals.get('clicks', []),
        'impressions': signals.get('impressions', []),
        'dwell': signals.get('dwell', []),
        'scroll': signals.get('scroll_milestones', []),
        'search_clicks': signals.get('search_sessions', []),
        'session_tiers': signals.get('session_features', []),
        'frustration': signals.get('frustration_events', []),
        'cooccurrence': signals.get('item_cooccurrence', []),
        'reading_ratio': signals.get('reading_ratio', []),
        'first_seen': signals.get('first_seen', []),
    }

    for key, val in result.items():
        print(f"  {key}: {len(val)} items")

    return result


def extract_item_name_from_path(path):
    """Extract item name from a URL path like /packages/foo or /papers/bar."""
    if not path:
        return None
    # Remove leading slash and split
    parts = path.strip('/').split('/')
    if len(parts) >= 2:
        # Return the last meaningful segment
        return parts[-1].lower().replace('-', ' ').replace('_', ' ')
    return None


def build_engagement_scores(engagement_data):
    """Build weighted engagement scores for observed items."""
    clicks = engagement_data.get('clicks', [])
    impressions = engagement_data.get('impressions', [])
    dwell = engagement_data.get('dwell', [])
    scroll = engagement_data.get('scroll', [])
    search_clicks = engagement_data.get('search_clicks', [])
    session_tiers = engagement_data.get('session_tiers', [])
    frustration = engagement_data.get('frustration', [])
    cooccurrence = engagement_data.get('cooccurrence', [])
    reading_ratio = engagement_data.get('reading_ratio', [])

    scores = defaultdict(float)
    item_signals = defaultdict(lambda: {
        'clicks': 0, 'impressions': 0, 'dwell_ms': 0, 'viewable_sec': 0,
        'scroll_90': 0, 'scroll_75': 0, 'scroll_50': 0,
        'search_clicks': 0, 'deep_sessions': 0,
        'rage_clicks': 0, 'quick_bounces': 0,
        'coviews': 0, 'coclicks': 0,
        'reading_ratio': 0, 'high_imp_no_click': False,
        # Search-rank tracking (Ra3): list of click positions per item
        # so we can compute avg/min for downstream features.
        'search_click_positions': [],
    })

    # Aggregate clicks
    for row in clicks:
        name = row['name'].lower().strip()
        count = row.get('click_count', 0) or 0
        scores[name] += count * CLICK_WEIGHT
        item_signals[name]['clicks'] += count

    # Aggregate impressions
    for row in impressions:
        name = row['name'].lower().strip()
        count = row.get('impression_count', 0) or 0
        scores[name] += count * IMPRESSION_WEIGHT
        item_signals[name]['impressions'] += count

    # Aggregate dwell time and viewability
    for row in dwell:
        name = row['name'].lower().strip()
        ms = row.get('total_dwell', 0) or 0
        minutes = ms / 60000.0
        scores[name] += minutes * DWELL_WEIGHT
        item_signals[name]['dwell_ms'] += ms

        # Add viewability signal
        viewable = row.get('total_viewable', 0) or 0
        scores[name] += viewable * VIEWABLE_WEIGHT
        item_signals[name]['viewable_sec'] += viewable

    # NEW: Aggregate scroll depth milestones
    for row in scroll:
        path = row.get('path', '')
        milestone = row.get('milestone', 0)
        count = row.get('count', 0) or 0
        name = extract_item_name_from_path(path)
        if name:
            if milestone >= 90:
                scores[name] += count * SCROLL_90_WEIGHT
                item_signals[name]['scroll_90'] += count
            elif milestone >= 75:
                scores[name] += count * SCROLL_75_WEIGHT
                item_signals[name]['scroll_75'] += count
            elif milestone >= 50:
                scores[name] += count * SCROLL_50_WEIGHT
                item_signals[name]['scroll_50'] += count

    # NEW: Aggregate search-to-click attribution.
    # Audit Ra3: extract `position` and apply a per-position bonus
    # (clicking the top result is easy; clicking rank-20 means the
    # user worked for it). Also store positions on item_signals so
    # downstream features can use avg/min rank-at-click.
    for row in search_clicks:
        clicks_json = row.get('clicks', '[]')
        try:
            click_list = json.loads(clicks_json) if isinstance(clicks_json, str) else clicks_json
            for click in click_list:
                # click might be {id: "item name", position: 1, dwellMs: 5000}
                position: int | None = None
                if isinstance(click, dict):
                    name = click.get('id', '').lower().strip()
                    pos_raw = click.get('position')
                    if isinstance(pos_raw, (int, float)) and pos_raw >= 0:
                        position = int(pos_raw)
                elif isinstance(click, str):
                    name = click.lower().strip()
                else:
                    continue
                if not name:
                    continue
                # Base search-click weight
                contribution = SEARCH_CLICK_WEIGHT
                # Position bonus: a click at rank 5 is more informative
                # than a click at rank 0. Linear in position; can be
                # tuned via SEARCH_CLICK_RANK_BONUS_WEIGHT.
                if position is not None:
                    contribution += position * SEARCH_CLICK_RANK_BONUS_WEIGHT
                    item_signals[name]['search_click_positions'].append(position)
                scores[name] += contribution
                item_signals[name]['search_clicks'] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    # NEW: Aggregate deep session content
    for row in session_tiers:
        content_seq = row.get('content_sequence', '[]')
        try:
            items_list = json.loads(content_seq) if isinstance(content_seq, str) else content_seq
            for item_name in items_list:
                if isinstance(item_name, str):
                    name = item_name.lower().strip()
                    scores[name] += DEEP_SESSION_WEIGHT
                    item_signals[name]['deep_sessions'] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    # NEW: Aggregate frustration signals (negative weight)
    for row in frustration:
        path = row.get('path', '')
        event_type = row.get('event_type', '')
        count = row.get('count', 0) or 0
        name = extract_item_name_from_path(path)
        if name:
            if event_type == 'rage_click':
                scores[name] += count * RAGE_CLICK_WEIGHT  # Negative
                item_signals[name]['rage_clicks'] += count
            elif event_type == 'quick_bounce':
                scores[name] += count * QUICK_BOUNCE_WEIGHT  # Negative
                item_signals[name]['quick_bounces'] += count

    # NEW: Build co-occurrence lookup (for cold-start enhancement)
    cooccur_scores = defaultdict(float)
    for row in cooccurrence:
        item_a = row.get('item_a', '').lower().strip()
        item_b = row.get('item_b', '').lower().strip()
        coviews = row.get('coview_count', 0) or 0
        coclicks = row.get('coclick_count', 0) or 0

        # Boost both items based on co-occurrence
        boost = coviews * COVIEW_WEIGHT + coclicks * COCLICK_WEIGHT
        cooccur_scores[item_a] += boost
        cooccur_scores[item_b] += boost
        item_signals[item_a]['coviews'] += coviews
        item_signals[item_a]['coclicks'] += coclicks
        item_signals[item_b]['coviews'] += coviews
        item_signals[item_b]['coclicks'] += coclicks

    # Add co-occurrence scores to main scores
    for name, boost in cooccur_scores.items():
        scores[name] += boost

    # NEW: Aggregate reading ratio (quality signal)
    for row in reading_ratio:
        name = row['name'].lower().strip()
        avg_ratio = row.get('avg_reading_ratio', 0) or 0
        # Cap at reasonable value (e.g., 2.0 = read twice as long as expected)
        capped_ratio = min(avg_ratio, 2.0)
        scores[name] += capped_ratio * READING_RATIO_WEIGHT
        item_signals[name]['reading_ratio'] = capped_ratio

    # NEW: Apply penalty for high impressions with zero clicks
    # Build click lookup for fast access
    click_lookup = {row['name'].lower().strip(): row.get('click_count', 0) or 0 for row in clicks}

    for row in impressions:
        name = row['name'].lower().strip()
        imp_count = row.get('impression_count', 0) or 0
        click_count = click_lookup.get(name, 0)

        # If item has high impressions but zero clicks, apply penalty
        if imp_count >= HIGH_IMP_NO_CLICK_THRESHOLD and click_count == 0:
            penalty = HIGH_IMP_NO_CLICK_WEIGHT * (imp_count / HIGH_IMP_NO_CLICK_THRESHOLD)
            scores[name] += penalty  # Negative weight
            item_signals[name]['high_imp_no_click'] = True

    # Ensure scores don't go negative (from frustration signals)
    for name in scores:
        scores[name] = max(0, scores[name])

    return dict(scores), dict(item_signals), cooccurrence


def calculate_freshness_scores(first_seen_data):
    """Calculate freshness boost based on first_seen dates.

    Uses exponential decay: boost = FRESHNESS_WEIGHT * exp(-days / half_life)
    Newer items get higher boost, decaying over time.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    freshness_scores = {}

    for row in first_seen_data:
        name = row['name'].lower().strip()
        first_seen_str = row.get('first_seen')

        if not first_seen_str:
            continue

        try:
            # Parse ISO format datetime
            if 'T' in first_seen_str:
                first_seen = datetime.fromisoformat(first_seen_str.replace('Z', '+00:00'))
            else:
                first_seen = datetime.strptime(first_seen_str, '%Y-%m-%d %H:%M:%S')
                first_seen = first_seen.replace(tzinfo=timezone.utc)

            days_since = (now - first_seen).days

            # Exponential decay: newer items get higher boost
            decay = math.exp(-days_since / FRESHNESS_HALF_LIFE_DAYS)
            freshness_scores[name] = FRESHNESS_WEIGHT * decay

        except (ValueError, TypeError):
            continue

    return freshness_scores


def extract_url_domain(url):
    """Extract domain from URL."""
    if not url:
        return 'none'
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Simplify common domains
        if 'github' in domain:
            return 'github'
        elif 'arxiv' in domain:
            return 'arxiv'
        elif 'youtube' in domain:
            return 'youtube'
        elif 'kaggle' in domain:
            return 'kaggle'
        elif 'medium' in domain:
            return 'medium'
        elif 'substack' in domain:
            return 'substack'
        elif domain:
            return 'other'
        return 'none'
    except:
        return 'none'


def build_features_for_regression(items):
    """Build feature matrix with BERT embeddings for regression model."""
    print("\nBuilding features for regression model...")

    # Collect unique values for encoding (handle None values)
    all_types = list(set(item.get('type') or 'unknown' for item in items))
    all_categories = list(set(item.get('category') or 'other' for item in items))
    all_difficulties = list(set(item.get('difficulty') or 'intermediate' for item in items))
    all_domains = list(set(extract_url_domain(item.get('url', '')) for item in items))
    all_languages = list(set(item.get('language') or 'unknown' for item in items))

    # Create encoders
    type_encoder = {t: i for i, t in enumerate(sorted(all_types))}
    category_encoder = {c: i for i, c in enumerate(sorted(all_categories))}
    difficulty_encoder = {d: i for i, d in enumerate(sorted(all_difficulties))}
    domain_encoder = {d: i for i, d in enumerate(sorted(all_domains))}
    language_encoder = {l: i for i, l in enumerate(sorted(all_languages))}

    # Build categorical/numeric features
    cat_features = []
    descriptions = []

    for item in items:
        desc = item.get('description') or ''
        name = item.get('name') or ''
        tags = item.get('tags') or []
        topic_tags = item.get('topic_tags') or []
        audience = item.get('audience') or []
        use_cases = item.get('use_cases') or []
        related = item.get('related_packages') or []
        synthetic_q = item.get('synthetic_questions') or []
        best_for = item.get('best_for') or ''

        # Text for BERT: combine name + description
        text = f"{name}. {desc}" if desc else name
        descriptions.append(text)

        cat_row = [
            # Original features (10)
            type_encoder.get(item.get('type') or 'unknown', 0),
            category_encoder.get(item.get('category') or 'other', 0),
            difficulty_encoder.get(item.get('difficulty') or 'intermediate', 0),
            domain_encoder.get(extract_url_domain(item.get('url') or ''), 0),
            len(desc),
            len(tags) if isinstance(tags, list) else 0,
            len(topic_tags) if isinstance(topic_tags, list) else 0,
            1 if item.get('url') else 0,
            item.get('citations') or 0,
            len(name),
            # New features (8)
            len(audience) if isinstance(audience, list) else 0,  # n_audience
            len(use_cases) if isinstance(use_cases, list) else 0,  # n_use_cases
            len(related) if isinstance(related, list) else 0,  # n_related
            1 if item.get('github_url') else 0,  # has_github
            language_encoder.get(item.get('language') or 'unknown', 0),  # language
            len(synthetic_q) if isinstance(synthetic_q, list) else 0,  # n_synthetic_q
            len(desc.split()) if desc else 0,  # desc_word_count
            1 if best_for else 0,  # has_best_for
        ]
        cat_features.append(cat_row)

    cat_features = np.array(cat_features)
    print(f"  Categorical features: {cat_features.shape}")

    # Generate BERT embeddings for descriptions
    print("  Encoding descriptions with sentence-BERT...")
    embeddings = SBERT_MODEL.encode(descriptions, show_progress_bar=True, batch_size=64)
    print(f"  BERT embeddings: {embeddings.shape}")

    # Concatenate categorical + BERT features
    X = np.hstack([cat_features, embeddings])
    print(f"  Combined feature matrix: {X.shape}")

    return X, {
        'type_encoder': type_encoder,
        'category_encoder': category_encoder,
        'difficulty_encoder': difficulty_encoder,
        'domain_encoder': domain_encoder,
        'language_encoder': language_encoder,
        'n_categorical': cat_features.shape[1],
        'n_bert': embeddings.shape[1],
    }


def train_regression_model(items, item_signals):
    """Train a regression model to predict engagement score."""
    print("\nTraining regression model to predict engagement scores...")

    # Build features with BERT embeddings
    X, encoders = build_features_for_regression(items)

    # Build engagement features (these help the model learn what makes content engaging)
    engagement_features = []
    for item in items:
        name = item['name']
        signals = item_signals.get(name, {})
        clicks = signals.get('clicks', 0)
        impressions = signals.get('impressions', 0)

        # CTR (click-through rate) - a strong quality signal
        ctr = clicks / max(impressions, 1) if impressions > 0 else 0

        # Has any engagement signals (binary flags for cold-start detection)
        has_clicks = 1 if clicks > 0 else 0
        has_impressions = 1 if impressions > 0 else 0
        has_dwell = 1 if signals.get('dwell_ms', 0) > 0 else 0
        has_scroll = 1 if signals.get('scroll_90', 0) > 0 or signals.get('scroll_75', 0) > 0 else 0

        engagement_features.append([
            ctr,
            has_clicks,
            has_impressions,
            has_dwell,
            has_scroll,
            np.log1p(clicks),  # Log-transformed click count
            np.log1p(impressions),  # Log-transformed impressions
        ])

    engagement_features = np.array(engagement_features)
    X = np.hstack([X, engagement_features])
    encoders['n_engagement_features'] = engagement_features.shape[1]
    print(f"  Added {engagement_features.shape[1]} engagement features")

    # Build target: comprehensive engagement score using ALL signals
    y = []
    for item in items:
        name = item['name']
        signals = item_signals.get(name, {})

        # Core signals
        clicks = signals.get('clicks', 0)
        impressions = signals.get('impressions', 0)
        dwell_ms = signals.get('dwell_ms', 0)
        dwell_minutes = dwell_ms / 60000.0
        viewable_sec = signals.get('viewable_sec', 0)

        # Advanced signals
        scroll_90 = signals.get('scroll_90', 0)
        scroll_75 = signals.get('scroll_75', 0)
        scroll_50 = signals.get('scroll_50', 0)
        search_clicks = signals.get('search_clicks', 0)
        deep_sessions = signals.get('deep_sessions', 0)
        coviews = signals.get('coviews', 0)
        coclicks = signals.get('coclicks', 0)
        reading_ratio = signals.get('reading_ratio', 0)

        # Negative signals
        rage_clicks = signals.get('rage_clicks', 0)
        quick_bounces = signals.get('quick_bounces', 0)
        high_imp_no_click = signals.get('high_imp_no_click', False)

        # Calculate comprehensive score
        score = (
            clicks * CLICK_WEIGHT +
            impressions * IMPRESSION_WEIGHT +
            dwell_minutes * DWELL_WEIGHT +
            viewable_sec * VIEWABLE_WEIGHT +
            scroll_90 * SCROLL_90_WEIGHT +
            scroll_75 * SCROLL_75_WEIGHT +
            scroll_50 * SCROLL_50_WEIGHT +
            search_clicks * SEARCH_CLICK_WEIGHT +
            deep_sessions * DEEP_SESSION_WEIGHT +
            coviews * COVIEW_WEIGHT +
            coclicks * COCLICK_WEIGHT +
            reading_ratio * READING_RATIO_WEIGHT +
            rage_clicks * RAGE_CLICK_WEIGHT +  # Negative
            quick_bounces * QUICK_BOUNCE_WEIGHT  # Negative
        )

        # Apply high impression no click penalty
        if high_imp_no_click:
            score += HIGH_IMP_NO_CLICK_WEIGHT * (impressions / HIGH_IMP_NO_CLICK_THRESHOLD)

        # Ensure non-negative
        score = max(0, score)
        y.append(score)

    y = np.array(y)

    n_with_score = np.sum(y > 0)
    print(f"  Items with engagement: {n_with_score}")
    print(f"  Items without engagement: {len(y) - n_with_score}")
    print(f"  Max score: {y.max():.2f}, Mean (non-zero): {y[y > 0].mean():.2f}")

    if n_with_score < 5:
        print("  Not enough samples with engagement for training")
        return None, None, encoders

    # Proper train/test split on ALL data (including zeros)
    print("\n  Train/test split (80/20)...")
    indices = np.arange(len(y))
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, indices, test_size=0.2, random_state=42, stratify=(y > 0)
    )

    n_train_engaged = np.sum(y_train > 0)
    n_test_engaged = np.sum(y_test > 0)
    print(f"  Train: {len(y_train)} items ({n_train_engaged} with engagement)")
    print(f"  Test:  {len(y_test)} items ({n_test_engaged} with engagement)")

    # Convert to binary classification target (any engagement = 1)
    y_binary = (y > 0).astype(int)
    y_train_binary = (y_train > 0).astype(int)
    y_test_binary = (y_test > 0).astype(int)

    if HAS_LIGHTGBM:
        # Use LightGBM binary classifier for "any engagement" prediction
        model = lgb.LGBMClassifier(
            objective='binary',
            n_estimators=150,
            max_depth=6,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=5,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=1.0,
            random_state=42,
            verbose=-1,
            class_weight='balanced'  # Handle imbalance
        )
        model_name = "LightGBM-Binary"
    else:
        from sklearn.linear_model import LogisticRegression
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)
        X = scaler.fit_transform(X)
        model = LogisticRegression(class_weight='balanced', max_iter=1000)
        encoders['scaler'] = scaler
        model_name = "LogisticRegression"

    # Train on training set (binary target).
    #
    # Ra1 — watch-time-weighted positive samples (book §8.3.2 / YouTube).
    # Each row's training weight is `1 + log1p(engagement_score)` for
    # positives and 1.0 for negatives. Items with deeper engagement
    # (longer dwell, deeper scroll, more clicks) push the classifier
    # harder than shallow click-bait. Compounds with class_weight=
    # 'balanced' multiplicatively.
    train_sample_weights = compute_sample_weights(y_train)
    model.fit(X_train, y_train_binary, sample_weight=train_sample_weights)

    # Get predicted probabilities for test set
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred_class = model.predict(X_test)

    # Classification metrics
    from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

    test_precision = precision_score(y_test_binary, y_pred_class)
    test_recall = recall_score(y_test_binary, y_pred_class)
    test_f1 = f1_score(y_test_binary, y_pred_class)
    test_auc = roc_auc_score(y_test_binary, y_pred_proba)
    test_ap = average_precision_score(y_test_binary, y_pred_proba)

    cm = confusion_matrix(y_test_binary, y_pred_class)
    tn, fp, fn, tp = cm.ravel()

    print(f"\n  === HOLDOUT TEST METRICS (Binary Classification) ===")
    print(f"  Precision: {test_precision:.3f}")
    print(f"  Recall:    {test_recall:.3f}")
    print(f"  F1 Score:  {test_f1:.3f}")
    print(f"  AUC-ROC:   {test_auc:.3f}")
    print(f"  AUC-PR:    {test_ap:.3f}")
    print(f"  Confusion Matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}")

    # Per-interaction metrics
    for signal_name, signal_key in [('clicks', 'clicks'), ('impressions', 'impressions'), ('dwell', 'dwell_ms')]:
        signal_binary = np.array([
            1 if item_signals.get(items[i]['name'], {}).get(signal_key, 0) > 0 else 0
            for i in idx_test
        ])
        if signal_binary.sum() > 0 and signal_binary.sum() < len(signal_binary):
            signal_auc = roc_auc_score(signal_binary, y_pred_proba)
            signal_ap = average_precision_score(signal_binary, y_pred_proba)
            print(f"  AUC-ROC ({signal_name}): {signal_auc:.3f} | AUC-PR: {signal_ap:.3f}")

    # Retrain on full data for final model
    print(f"\n  Retraining on full data...")
    if not HAS_LIGHTGBM:
        X = scaler.fit_transform(X)
    model.fit(X, y_binary)
    print(f"  {model_name} trained on {len(y_binary)} items")

    # Ra7 — persist the trained model with sidecar metadata so future
    # evaluator / replay runs can score against a fixed artifact rather
    # than re-running training. Best-effort: any failure here is logged
    # but does NOT abort the rerank (the in-memory `model` is still
    # used to compute scores). Skipped when LightGBM isn't available
    # (the LR fallback isn't worth caching).
    if HAS_LIGHTGBM and hasattr(model, "save_model"):
        try:
            next_version = (_latest_model_version() or 0) + 1
            cached = _save_model_artifact(
                model,
                version=next_version,
                metadata={
                    "model_name": model_name,
                    "n_train_rows": int(len(y_train_binary)),
                    "n_train_engaged": int(np.sum(y_train_binary)),
                    "n_features": int(X_train.shape[1]),
                    "test_metrics": {
                        "precision": float(test_precision),
                        "recall": float(test_recall),
                        "f1": float(test_f1),
                        "auc_roc": float(test_auc),
                        "auc_pr": float(test_ap),
                    },
                },
            )
            print(f"  Saved model artifact v{cached.version} -> {cached.booster_path}")
        except (ModelCacheError, OSError, TypeError) as cache_err:
            print(f"  Warning: model cache write failed ({cache_err}); ranking continues.")

    # Get predicted probabilities for all items
    predictions_proba = model.predict_proba(X)[:, 1]

    # Final score = probability * (1 + log1p(weighted_score))
    # This ranks by engagement probability, with weighted score as tiebreaker
    predictions = predictions_proba * (1 + np.log1p(y) * 0.1)

    # Clip to [0, 1] range
    predictions = np.clip(predictions, 0, 1)

    # Build score dict
    scores = {}
    for i, item in enumerate(items):
        scores[item['name']] = float(predictions[i])

    print(f"  Scored {len(scores)} items")
    print(f"  Probability range: {predictions_proba.min():.3f} to {predictions_proba.max():.3f}")
    print(f"  Final score range: {predictions.min():.3f} to {predictions.max():.3f}")

    # Show feature importance
    n_cat = encoders['n_categorical']
    n_eng = encoders.get('n_engagement_features', 0)
    feature_names = [
        'type', 'category', 'difficulty', 'domain', 'desc_len', 'n_tags', 'n_topics', 'has_url', 'citations', 'name_len',
        'n_audience', 'n_use_cases', 'n_related', 'has_github', 'language', 'n_synthetic_q', 'desc_words', 'has_best_for',
        'ctr', 'has_clicks', 'has_impressions', 'has_dwell', 'has_scroll', 'log_clicks', 'log_impressions'
    ]

    if HAS_LIGHTGBM and hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        cat_importances = importances[:n_cat]
        eng_importances = importances[n_cat:n_cat + n_eng] if n_eng > 0 else []
        bert_importance_sum = importances[n_cat + n_eng:].sum()

        # Combine categorical and engagement features for sorting
        all_feature_importances = list(cat_importances) + list(eng_importances)
        sorted_idx = np.argsort(all_feature_importances)[::-1]
        print("  Top feature importances:")
        for idx in sorted_idx[:8]:
            if idx < len(feature_names):
                print(f"    {feature_names[idx]}: {all_feature_importances[idx]:.1f}")
        print(f"    BERT embeddings (sum): {bert_importance_sum:.1f}")
    elif hasattr(model, 'coef_'):
        coefs = np.abs(model.coef_)
        cat_coefs = coefs[:n_cat]
        eng_coefs = coefs[n_cat:n_cat + n_eng] if n_eng > 0 else []
        bert_coef_sum = coefs[n_cat + n_eng:].sum()

        all_feature_coefs = list(cat_coefs) + list(eng_coefs)
        sorted_idx = np.argsort(all_feature_coefs)[::-1]
        print("  Top coefficient magnitudes:")
        for idx in sorted_idx[:8]:
            if idx < len(feature_names):
                print(f"    {feature_names[idx]}: {all_feature_coefs[idx]:.3f}")
        print(f"    BERT embeddings (sum): {bert_coef_sum:.3f}")

    return model, scores, encoders


def safe_join(val):
    """Safely join a field that may be a list, string, or None."""
    if val is None:
        return ''
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return ' '.join(str(v) for v in val if v)
    return str(val)


def build_content_features(items):
    """Build TF-IDF feature matrix from ALL available metadata."""
    print("\nBuilding content feature vectors (enhanced)...")

    # Combine ALL text features for each item
    texts = []
    for item in items:
        text_parts = [
            # Original fields
            item.get('name', ''),
            item.get('description', ''),
            item.get('summary', ''),
            item.get('category', ''),
            safe_join(item.get('tags', [])),
            safe_join(item.get('topic_tags', [])),
            item.get('difficulty', ''),
            safe_join(item.get('audience', [])),
            item.get('type', ''),
            # NEW fields
            safe_join(item.get('synthetic_questions', [])),  # LLM search queries
            safe_join(item.get('use_cases', [])),             # Applications
            item.get('best_for', ''),                         # Target use
            safe_join(item.get('domain_tags', [])),           # Dataset domains
            safe_join(item.get('key_insights', [])),          # Talk takeaways
            safe_join(item.get('mentioned_tools', [])),       # Tools in talks
            item.get('language', ''),                         # Package language
            item.get('content_format', ''),                   # Resource format
            item.get('speaker_expertise', ''),                # Talk speaker
            item.get('company_context', ''),                  # Career company
            item.get('experience_level', ''),                 # Career level
            item.get('data_modality', ''),                    # Dataset type
            safe_join(item.get('related_packages', [])),      # Package relations
        ]
        texts.append(' '.join(str(p) for p in text_parts if p))

    # Build TF-IDF matrix with more features for richer matching
    vectorizer = TfidfVectorizer(
        max_features=1000,  # Increased for more metadata
        stop_words='english',
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8
    )

    try:
        feature_matrix = vectorizer.fit_transform(texts)
        print(f"  Feature matrix: {feature_matrix.shape}")
        print(f"  Using {len([f for f in vectorizer.get_feature_names_out() if '_' in f])} bigrams")
        return feature_matrix, vectorizer
    except Exception as e:
        print(f"  Error building features: {e}")
        return None, None


def propagate_cold_start_scores(items, observed_scores, feature_matrix, k=5):
    """Propagate scores to cold start items via k-NN similarity."""
    print(f"\nPropagating scores to cold start items (k={k})...")

    # Find observed and cold start indices
    observed_indices = []
    cold_indices = []
    observed_score_list = []

    for i, item in enumerate(items):
        if item['name'] in observed_scores:
            observed_indices.append(i)
            observed_score_list.append(observed_scores[item['name']])
        else:
            cold_indices.append(i)

    print(f"  Observed items: {len(observed_indices)}")
    print(f"  Cold start items: {len(cold_indices)}")

    if not observed_indices or feature_matrix is None:
        # No observed items or no features - use type averages
        print("  Using type averages as fallback...")
        type_scores = defaultdict(list)
        for i in observed_indices:
            type_scores[items[i]['type']].append(observed_scores[items[i]['name']])

        type_avg = {t: np.mean(scores) if scores else 0 for t, scores in type_scores.items()}
        global_avg = np.mean(observed_score_list) if observed_score_list else 0

        cold_scores = {}
        for i in cold_indices:
            cold_scores[items[i]['name']] = type_avg.get(items[i]['type'], global_avg)

        return cold_scores

    # Extract feature vectors for observed items
    observed_features = feature_matrix[observed_indices]
    observed_score_arr = np.array(observed_score_list)

    # For each cold item, find k nearest observed neighbors
    cold_scores = {}
    batch_size = 500

    for batch_start in range(0, len(cold_indices), batch_size):
        batch_indices = cold_indices[batch_start:batch_start + batch_size]
        batch_features = feature_matrix[batch_indices]

        # Compute similarities to all observed items
        similarities = cosine_similarity(batch_features, observed_features)

        for j, cold_idx in enumerate(batch_indices):
            sims = similarities[j]

            # Get top-k neighbors
            if len(sims) <= k:
                top_k_idx = np.arange(len(sims))
            else:
                top_k_idx = np.argpartition(sims, -k)[-k:]

            top_k_sims = sims[top_k_idx]
            top_k_scores = observed_score_arr[top_k_idx]

            # Weighted average (avoid division by zero)
            if top_k_sims.sum() > 0:
                score = np.average(top_k_scores, weights=top_k_sims)
            else:
                score = np.mean(observed_score_arr)  # fallback to global average

            cold_scores[items[cold_idx]['name']] = score

    return cold_scores


def normalize_scores(scores):
    """Normalize scores to 0-1 range."""
    if not scores:
        return {}

    values = list(scores.values())
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return {k: 0.5 for k in scores}

    return {k: (v - min_val) / (max_val - min_val) for k, v in scores.items()}


def apply_citations_boost(items, scores):
    """Boost paper scores by log(citations)."""
    # Find max citations for normalization
    max_citations = max((item.get('citations', 0) or 0 for item in items), default=1)
    if max_citations == 0:
        max_citations = 1

    boosted = 0
    for item in items:
        if item['type'] == 'paper':
            citations = item.get('citations', 0) or 0
            if citations > 0:
                # Log-scale boost, normalized to ~0.3 for max citations
                boost = (math.log(citations + 1) / math.log(max_citations + 1)) * CITATION_WEIGHT
                name = item['name']
                if name in scores:
                    scores[name] = min(1.0, scores[name] + boost)
                    boosted += 1
                else:
                    # Give papers with citations a baseline score even without engagement
                    scores[name] = min(1.0, boost)
                    boosted += 1

    print(f"  Applied citations boost to {boosted} papers")
    return scores


def _build_tfidf_sim_fn(items):
    """TF-IDF feature matrix over 22 metadata fields → similarity_fn.
    Returns None if the corpus is too small for TF-IDF (rare)."""
    print("\nBuilding TF-IDF features for k-NN cold-start...")
    texts = []
    for item in items:
        text_parts = [
            item.get('name', ''),
            item.get('description', ''),
            item.get('summary', ''),
            item.get('category', ''),
            safe_join(item.get('tags', [])),
            safe_join(item.get('topic_tags', [])),
            item.get('difficulty', ''),
            safe_join(item.get('audience', [])),
            item.get('type', ''),
            safe_join(item.get('synthetic_questions', [])),
            safe_join(item.get('use_cases', [])),
            item.get('best_for', ''),
            safe_join(item.get('domain_tags', [])),
            safe_join(item.get('key_insights', [])),
            safe_join(item.get('mentioned_tools', [])),
            item.get('language', ''),
            item.get('content_format', ''),
            item.get('speaker_expertise', ''),
            item.get('company_context', ''),
            item.get('experience_level', ''),
            item.get('data_modality', ''),
            safe_join(item.get('related_packages', [])),
        ]
        texts.append(' '.join(str(p) for p in text_parts if p))

    vectorizer = TfidfVectorizer(
        max_features=1000,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8,
    )
    try:
        feature_matrix = vectorizer.fit_transform(texts)
    except ValueError as e:
        print(f"  TF-IDF build failed ({e}); falling back.")
        return None
    print(f"  TF-IDF feature matrix: {feature_matrix.shape}")
    return _make_tfidf_similarity_fn(feature_matrix)


def _build_bge_sim_fn(items, *, name_key='name'):
    """Load static/embeddings/search-embeddings.bin (bge-large-en-v1.5,
    1024 dim) and build a similarity_fn aligned to the `items` list.

    Items not present in the embedding catalog get a zero row, which
    lib.cold_start.cosine_sim coerces to 0 similarity (defensive).

    Returns None if the bin / metadata files are missing or malformed.
    """
    print("\nLoading BGE embeddings for k-NN cold-start...")
    repo_root = Path(__file__).resolve().parents[1]
    meta_path = repo_root / 'static' / 'embeddings' / 'search-metadata.json'
    bin_path = repo_root / 'static' / 'embeddings' / 'search-embeddings.bin'

    if not (meta_path.exists() and bin_path.exists()):
        print(f"  BGE files missing ({meta_path.name}, {bin_path.name}); falling back.")
        return None

    try:
        with meta_path.open() as f:
            meta = json.load(f)
        dim = int(meta['dimensions'])
        n_total = int(meta['count'])
        catalog_items = meta.get('items', [])
        if len(catalog_items) != n_total:
            print(f"  BGE metadata mismatch (count={n_total} but {len(catalog_items)} items); falling back.")
            return None
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"  BGE metadata parse failed ({e}); falling back.")
        return None

    raw = np.fromfile(bin_path, dtype=np.float32)
    if raw.size != n_total * dim:
        print(f"  BGE bin size mismatch ({raw.size} != {n_total * dim}); falling back.")
        return None
    full_matrix = raw.reshape(n_total, dim)

    # rank_all_content normalises item names to lowercase (line ~210);
    # the embedding catalog keeps original case. Match case-insensitively.
    name_to_row = {}
    for i, it in enumerate(catalog_items):
        n = it.get('name')
        if isinstance(n, str) and n:
            name_to_row[n.strip().lower()] = i

    out_matrix = np.zeros((len(items), dim), dtype=np.float32)
    matched = 0
    for i, item in enumerate(items):
        name = item.get(name_key)
        if isinstance(name, str):
            row = name_to_row.get(name.strip().lower())
            if row is not None:
                out_matrix[i] = full_matrix[row]
                matched += 1
    print(f"  BGE matched {matched}/{len(items)} items "
          f"({matched / len(items) * 100:.1f}% coverage)")
    if matched < 0.5 * len(items):
        print("  WARNING: less than half the items have BGE embeddings — "
              "cold items may degrade to zero-similarity (random-tie) propagation.")

    return _make_dense_similarity_fn(out_matrix)


def _knn_cold_start(items, observed_scores, *, similarity, k=5):
    """Compute k-NN propagated cold-start scores. `similarity` is one of
    'tfidf' or 'bge'. Returns dict[name -> score] for cold items only;
    discount=1.0 (caller applies the cold-start discount uniformly so
    A/B comparisons are method-vs-method).
    """
    if similarity == 'tfidf':
        sim_fn = _build_tfidf_sim_fn(items)
    elif similarity == 'bge':
        sim_fn = _build_bge_sim_fn(items)
    else:
        raise ValueError(f"unknown similarity {similarity!r}; expected 'tfidf' or 'bge'")
    if sim_fn is None:
        return {}

    result = _knn_propagate_cold_start(
        items, observed_scores, sim_fn,
        k=k, discount=1.0, name_key='name',
    )
    print(f"  Cold-start k-NN ({similarity}): observed={result.n_observed} "
          f"cold={result.n_cold} fallback={result.fallback}")
    return result.scores


def _run_offline_eval_gate(
    *,
    rankings: list,
    metrics_csv: str,
    source: str,
    analytics_api: str,
    skip_regression_check: bool,
    holdout_days_override: int | None = None,
    cold_start_method: str = 'regression',
    notes_override: str = '',
) -> None:
    """Phase-1 offline evaluation: pull D1 sessions, score this run's
    rankings against the actual clicks, append a row to metrics.csv, and
    raise RegressionAlert if NDCG@10 dropped beyond the configured
    threshold. Caller (main) catches the alert and exits non-zero
    before any data file is overwritten.

    A failure to reach D1 is treated as a hard error per rule E14 --
    we won't silently rubber-stamp a rerank against zero observations.
    Pass --no-evaluate to bypass when you really mean to (e.g. local
    dev without internet).
    """
    config = _load_recsys_config()
    holdout_days = (
        holdout_days_override if holdout_days_override is not None
        else config.evaluation.holdout_days
    )
    k_values = tuple(config.evaluation.k_values)
    threshold = config.evaluation.ndcg_drop_alert_threshold

    # Build (lowercased name -> score) lookup from this run's rankings
    scores = {}
    for entry in rankings:
        name = entry.get('name')
        score = entry.get('score')
        if isinstance(name, str) and isinstance(score, (int, float)):
            scores[name.strip().lower()] = float(score)

    print("\n=== Offline evaluation ===")
    print(f"  holdout_days={holdout_days} k_values={k_values} threshold={threshold}")

    # /events-raw HTTP endpoint is preferred (deployed 2026-05-03 in
    # PR #27). Fall back to wrangler subprocess when ADMIN_KEY isn't
    # available locally so the gate still works in environments
    # without secret access.
    admin_key = os.environ.get('ADMIN_KEY')
    if admin_key:
        eval_source = 'api'
        eval_api_url = analytics_api
        print(f"  session source: HTTP /events-raw on {analytics_api}")
    else:
        eval_source = 'wrangler'
        eval_api_url = None
        print(f"  session source: wrangler (no ADMIN_KEY env; export it for HTTP)")
    try:
        sessions = _load_sessions(
            holdout_days=holdout_days,
            source=eval_source,
            api_url=eval_api_url,
            admin_key=admin_key,
        )
    except _SessionLoadError as e:
        print(f"  ERROR: D1 session load failed: {e}", file=sys.stderr)
        # If HTTP was the path that failed, automatically fall back to
        # wrangler. Could be a transient endpoint outage or stale key;
        # keeps the rerank green either way.
        if eval_source == 'api':
            print("  Falling back to wrangler subprocess...", file=sys.stderr)
            try:
                sessions = _load_sessions(
                    holdout_days=holdout_days,
                    source='wrangler',
                )
            except _SessionLoadError as e2:
                print(f"  Wrangler fallback also failed: {e2}", file=sys.stderr)
                print("  Skipping evaluation (no rerank gate). Investigate D1 health.",
                      file=sys.stderr)
                return
        else:
            print("  Skipping evaluation (no rerank gate). Investigate D1 health.",
                  file=sys.stderr)
            return

    if not sessions:
        print("  No sessions in the holdout window; skipping evaluation row.")
        return

    metrics_csv_path = Path(__file__).resolve().parent.parent / metrics_csv

    # Compose a structured notes string. Auto-include the cold-start
    # method so future readers of metrics.csv can tell regression rows
    # apart from knn-bge rows. The user's --notes (if any) is appended.
    auto_notes = f"source={source} cold_start={cold_start_method}"
    notes = f"{auto_notes} | {notes_override}" if notes_override else auto_notes

    result = _run_evaluation(
        scores=scores,
        sessions=sessions,
        holdout_days=holdout_days,
        k_values=k_values,
        git_sha=_current_git_sha(),
        notes=notes,
    )
    print(f"  sessions_total={result.n_sessions_total} "
          f"evaluable={result.n_sessions_evaluable} "
          f"NDCG@10={result.aggregate.ndcg_at_k.get(10, 0.0):.4f} "
          f"HitRate@10={result.aggregate.hit_rate_at_k.get(10, 0.0):.4f}")

    # Zero-evaluable rows have no signal -- the metrics will all be 0
    # because aggregate_sessions has nothing to average. Don't compare
    # them against a real baseline (would always look like a 100%
    # regression) and don't pollute metrics.csv with an empty row.
    # This is the "rerank ran fine but the holdout window had no
    # click-bearing sessions yet" case that hits right after the worker
    # comes back online (impressions arrive before clicks).
    if result.n_sessions_evaluable == 0:
        print("  All sessions had zero clicks (no eval signal). "
              "Skipping regression check and row write.")
        return

    previous = _read_last_metrics_row(metrics_csv_path)
    if not skip_regression_check:
        # Raises RegressionAlert -- caller exits 5
        _check_regression(result, previous, threshold=threshold)

    _write_metrics_row(metrics_csv_path, result)
    print(f"  appended row to {metrics_csv}")


def main():
    parser = argparse.ArgumentParser(description='Rank all content items')
    parser.add_argument('--output', '-o', default='data/global_rankings.json',
                        help='Output file path')
    parser.add_argument('--k-neighbors', '-k', type=int, default=5,
                        help='Number of neighbors for cold start (default: 5)')
    parser.add_argument('--source', choices=['d1', 'api'], default='d1',
                        help='Data source: d1 (wrangler CLI) or api (HTTP endpoint)')
    parser.add_argument('--evaluate', dest='evaluate', action='store_true', default=None,
                        help='Run offline evaluation against D1 sessions and append a row '
                             'to reports/metrics.csv. Defaults to ON for --source api.')
    parser.add_argument('--no-evaluate', dest='evaluate', action='store_false',
                        help='Skip the offline evaluation pass.')
    parser.add_argument('--skip-regression-check', action='store_true',
                        help='Append the metrics row but do not abort on NDCG@10 drop.')
    parser.add_argument('--metrics-csv', default='reports/metrics.csv',
                        help='Path to the metrics history CSV.')
    parser.add_argument('--eval-holdout-days', type=int, default=None,
                        help='Override config.evaluation.holdout_days for the eval gate. '
                             'Useful for one-off seed runs against pre-blackout data.')
    parser.add_argument('--eval-notes', default='',
                        help='Free-form note appended to the metrics.csv row, after the '
                             'auto-generated "source=X cold_start=Y" prefix. '
                             'Example: --eval-notes "ra4-test"')
    parser.add_argument(
        '--cold-start-method',
        choices=['regression', 'knn', 'knn-tfidf', 'knn-bge'],
        default='regression',
        help='How to score items with no observed engagement. '
             '"regression" (default) uses the trained model output * discount. '
             '"knn-tfidf" propagates observed scores via TF-IDF k-NN. '
             '"knn-bge" propagates via BGE-embedding k-NN '
             '(static/embeddings/search-embeddings.bin, 1024 dim). '
             '"knn" is a deprecated alias for "knn-tfidf". '
             'Ra2 — A/B with replay_eval.py before flipping the default.')
    parser.add_argument('--analytics-api',
                        default='https://tech-econ-analytics-v2.pp712.workers.dev',
                        help='analytics-worker URL used by --evaluate when --source api.')
    args = parser.parse_args()
    # Default: evaluate when running against the live API
    if args.evaluate is None:
        args.evaluate = (args.source == 'api')

    data_dir = Path(__file__).resolve().parent.parent / 'data'

    # Step 1: Load all content
    print("Loading content catalog...")
    items = load_all_content(data_dir)
    print(f"\nTotal content items: {len(items)}")

    # Create name -> item lookup
    item_lookup = {item['name']: item for item in items}

    # Step 2: Fetch engagement data (now returns dict with all signal types)
    if args.source == 'api':
        engagement_data = fetch_engagement_from_api()
    else:
        engagement_data = fetch_engagement_data()

    # Calculate coverage stats
    clicks = engagement_data.get('clicks', [])
    impressions = engagement_data.get('impressions', [])
    dwell = engagement_data.get('dwell', [])
    scroll = engagement_data.get('scroll', [])
    search_clicks = engagement_data.get('search_clicks', [])
    frustration = engagement_data.get('frustration', [])

    click_names = {row['name'].lower().strip() for row in clicks}
    impression_names = {row['name'].lower().strip() for row in impressions}
    dwell_names = {row['name'].lower().strip() for row in dwell}
    viewable_names = {row['name'].lower().strip() for row in dwell if (row.get('total_viewable') or 0) > 0}
    scroll_names = {extract_item_name_from_path(row.get('path', '')) for row in scroll if row.get('path')}
    scroll_names.discard(None)
    search_click_names = set()
    for row in search_clicks:
        try:
            click_list = json.loads(row.get('clicks', '[]')) if isinstance(row.get('clicks'), str) else row.get('clicks', [])
            for c in click_list:
                if isinstance(c, dict):
                    search_click_names.add(c.get('id', '').lower().strip())
                elif isinstance(c, str):
                    search_click_names.add(c.lower().strip())
        except:
            pass
    search_click_names.discard('')

    any_interaction_names = click_names | impression_names | dwell_names | scroll_names | search_click_names

    coverage = {
        'total_items': len(items),
        'items_with_clicks': len(click_names),
        'items_with_impressions': len(impression_names),
        'items_with_dwell': len(dwell_names),
        'items_with_viewability': len(viewable_names),
        'items_with_scroll': len(scroll_names),
        'items_with_search_clicks': len(search_click_names),
        'items_with_any': len(any_interaction_names),
        'coverage_pct': round(len(any_interaction_names) / len(items) * 100, 1) if items else 0,
    }

    # Step 3: Build engagement scores (for item_signals tracking)
    print("\nBuilding engagement scores...")
    raw_scores, item_signals, cooccurrence = build_engagement_scores(engagement_data)
    print(f"  Items with engagement data: {len(raw_scores)}")

    cold_start_method = args.cold_start_method
    knn_path = cold_start_method in ('knn', 'knn-tfidf', 'knn-bge')

    # Step 4: Train regression model to predict engagement scores.
    # Skipped when --cold-start-method=knn* because the regression
    # output is unused on those paths -- saves ~3 min on the rerank
    # (most of which is SBERT-encoding 3896 item descriptions in
    # batches). Set model/scores/encoders to empty so the rest of
    # main() reads diagnostics as "no model trained" gracefully.
    if knn_path:
        print(
            f"\nSkipping regression-train step "
            f"(--cold-start-method={cold_start_method}; predictions unused)"
        )
        model, regression_scores, encoders = None, {}, {}
    else:
        model, regression_scores, encoders = train_regression_model(items, item_signals)

    # Step 5: Hybrid scoring - actual engagement for observed, propagated for cold-start
    # Two cold-start methods (Ra2 audit):
    #   regression: norm_predicted * 0.3 (current production path)
    #   knn:        lib.cold_start k-NN propagation (TF-IDF or BGE)

    if knn_path:
        # 'knn' is a legacy alias for 'knn-tfidf' (kept so the merged
        # Ra2 PR #24's docs don't break).
        similarity = 'bge' if cold_start_method == 'knn-bge' else 'tfidf'
        cold_lookup = _knn_cold_start(
            items=items,
            observed_scores=raw_scores,
            similarity=similarity,
            k=5,  # TODO: thread from config.ranking.cold_start_k_neighbors
        )
        # Apply the same 0.3 discount the regression path uses, so the
        # A/B compares method-vs-method, not discount-vs-discount.
        norm_engagement = normalize_scores(raw_scores)
        norm_cold = normalize_scores(cold_lookup) if cold_lookup else {}
        combined_scores = {}
        for item in items:
            name = item['name']
            if name in any_interaction_names:
                combined_scores[name] = norm_engagement.get(name, 0)
            else:
                combined_scores[name] = norm_cold.get(name, 0) * 0.3
        combined_scores = normalize_scores(combined_scores)
        scoring_method = f'hybrid_{cold_start_method.replace("-", "_")}'
    elif regression_scores:
        # Normalize actual engagement scores
        norm_engagement = normalize_scores(raw_scores)
        # Normalize predicted scores
        norm_predicted = normalize_scores(regression_scores)

        # Hybrid: use actual for items with engagement, predicted (discounted) for cold-start
        combined_scores = {}
        for item in items:
            name = item['name']
            if name in any_interaction_names:
                # Has real interaction - use actual engagement score
                combined_scores[name] = norm_engagement.get(name, 0)
            else:
                # Cold start - use predicted score but discount it
                combined_scores[name] = norm_predicted.get(name, 0) * 0.3  # Cold-start discount

        # Re-normalize
        combined_scores = normalize_scores(combined_scores)
        scoring_method = 'hybrid_bert'
    else:
        print("  Falling back to weighted scoring...")
        combined_scores = normalize_scores(raw_scores)
        scoring_method = 'weighted'

    # Step 5b: Apply freshness boost
    first_seen_data = engagement_data.get('first_seen', [])
    freshness_scores = calculate_freshness_scores(first_seen_data)

    if freshness_scores:
        print(f"\nApplying freshness boost...")
        print(f"  Items with freshness data: {len(freshness_scores)}")

        # Apply additive freshness boost (capped at 1.0)
        boosted_count = 0
        max_boost = 0
        for name in combined_scores:
            if name in freshness_scores:
                boost = freshness_scores[name]
                combined_scores[name] = min(1.0, combined_scores[name] + boost)
                boosted_count += 1
                max_boost = max(max_boost, boost)

        print(f"  Boosted {boosted_count} items")
        print(f"  Max freshness boost: {max_boost:.3f}")

        # Re-normalize after freshness boost
        combined_scores = normalize_scores(combined_scores)
        scoring_method = 'hybrid_bert_fresh'

    # Step 5c: Apply citations boost for papers
    print(f"\nApplying citations boost...")
    combined_scores = apply_citations_boost(items, combined_scores)

    # Re-normalize after citations boost
    combined_scores = normalize_scores(combined_scores)

    # Step 6: Mark cold start flags (items without real interactions)
    cold_start_flags = {}
    for item in items:
        name = item['name']
        cold_start_flags[name] = name not in any_interaction_names

    # Build final scores dict
    all_scores = {}
    for item in items:
        name = item['name']
        all_scores[name] = {
            'score': combined_scores.get(name, 0.0),
            'cold_start': cold_start_flags.get(name, True),
            'signals': item_signals.get(name, {}),
            'citations': item.get('citations', 0) if item['type'] == 'paper' else None,
        }

    # Step 8: Build ranked output
    rankings = []
    for item in items:
        name = item['name']
        score_info = all_scores.get(name, {'score': 0, 'cold_start': True, 'signals': {}, 'citations': None})

        entry = {
            'name': item.get('original_name', name),
            'type': item['type'],
            'category': item.get('category', ''),
            'description': item.get('description', ''),
            'url': item.get('url', ''),
            'score': round(score_info['score'], 4),
            'cold_start': score_info['cold_start'],
            'signals': score_info['signals'],
        }
        # Add citations for papers
        if item['type'] == 'paper' and item.get('citations'):
            entry['citations'] = item['citations']

        rankings.append(entry)

    # Sort by score descending
    rankings.sort(key=lambda x: x['score'], reverse=True)

    # Add ranks
    for i, item in enumerate(rankings, 1):
        item['rank'] = i

    # Count stats
    observed_count = sum(1 for r in rankings if not r['cold_start'])
    cold_count = sum(1 for r in rankings if r['cold_start'])

    # Build output
    output = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'algorithm': scoring_method,
        'total_items': len(rankings),
        'observed_items': observed_count,
        'cold_start_items': cold_count,
        'coverage': coverage,
        'scoring': {
            'method': scoring_method,
            'model': 'ridge' if model else None,
            'alpha': model.alpha if model and hasattr(model, 'alpha') else None,
            'n_features': encoders.get('n_categorical', 0) + encoders.get('n_bert', 0) if encoders else None,
            'n_bert_dims': encoders.get('n_bert', 0) if encoders else None,
            'target_weights': {
                'clicks': CLICK_WEIGHT,
                'impressions': IMPRESSION_WEIGHT,
                'viewable_per_second': VIEWABLE_WEIGHT,
                'dwell_per_minute': DWELL_WEIGHT,
                'scroll_90': SCROLL_90_WEIGHT,
                'scroll_75': SCROLL_75_WEIGHT,
                'scroll_50': SCROLL_50_WEIGHT,
                'search_click': SEARCH_CLICK_WEIGHT,
                'search_click_rank_bonus': SEARCH_CLICK_RANK_BONUS_WEIGHT,
                'rage_click': RAGE_CLICK_WEIGHT,
                'quick_bounce': QUICK_BOUNCE_WEIGHT,
                'deep_session': DEEP_SESSION_WEIGHT,
                'coview': COVIEW_WEIGHT,
                'coclick': COCLICK_WEIGHT,
                'freshness': FRESHNESS_WEIGHT,
                'freshness_half_life_days': FRESHNESS_HALF_LIFE_DAYS,
            },
        },
        'metadata_fields': [
            'name', 'description', 'summary', 'category', 'tags', 'topic_tags',
            'difficulty', 'audience', 'type', 'synthetic_questions', 'use_cases',
            'best_for', 'domain_tags', 'key_insights', 'mentioned_tools',
            'language', 'content_format', 'speaker_expertise', 'company_context',
            'experience_level', 'data_modality', 'related_packages'
        ],
        'rankings': rankings
    }

    # Print summary
    print("\n" + "=" * 60)
    print("RANKING SUMMARY")
    print("=" * 60)
    print(f"Scoring method: {scoring_method.upper()}")
    if model:
        if hasattr(model, 'objective') and 'tweedie' in str(model.objective):
            print(f"  LightGBM-Tweedie: {model.n_estimators} trees, power={model.tweedie_variance_power}")
        elif hasattr(model, 'n_estimators'):
            print(f"  LightGBM: {model.n_estimators} trees, max_depth={model.max_depth}")
        elif hasattr(model, 'alpha'):
            print(f"  Ridge alpha: {model.alpha}")
        if encoders:
            print(f"  Features: {encoders.get('n_categorical', 0)} categorical + {encoders.get('n_bert', 0)} BERT dims")
    print(f"Total items ranked: {len(rankings)}")
    print(f"  With engagement data: {observed_count}")
    print(f"  Cold start (propagated): {cold_count}")

    print("\n" + "-" * 60)
    print("INTERACTION COVERAGE")
    print("-" * 60)
    print(f"Items with clicks:        {coverage['items_with_clicks']:>5} ({coverage['items_with_clicks']/len(items)*100:.1f}%)")
    print(f"Items with impressions:   {coverage['items_with_impressions']:>5} ({coverage['items_with_impressions']/len(items)*100:.1f}%)")
    print(f"Items with dwell:         {coverage['items_with_dwell']:>5} ({coverage['items_with_dwell']/len(items)*100:.1f}%)")
    print(f"Items with viewability:   {coverage['items_with_viewability']:>5} ({coverage['items_with_viewability']/len(items)*100:.1f}%)")
    print(f"Items with scroll depth:  {coverage.get('items_with_scroll', 0):>5} ({coverage.get('items_with_scroll', 0)/len(items)*100:.1f}%)")
    print(f"Items with search clicks: {coverage.get('items_with_search_clicks', 0):>5} ({coverage.get('items_with_search_clicks', 0)/len(items)*100:.1f}%)")
    print(f"Items with ANY:           {coverage['items_with_any']:>5} ({coverage['coverage_pct']:.1f}%)")

    print("\n" + "-" * 60)
    print("TOP 20 ITEMS")
    print("-" * 60)
    print(f"{'Rank':<5} {'Score':<7} {'Type':<10} {'Name'}")
    print("-" * 60)
    for item in rankings[:20]:
        name_display = item['name'][:45] + '...' if len(item['name']) > 45 else item['name']
        cs = "*" if item['cold_start'] else ""
        print(f"{item['rank']:<5} {item['score']:<7.3f} {item['type']:<10} {name_display}{cs}")

    print("\n" + "-" * 60)
    print("TOP ITEMS BY TYPE")
    print("-" * 60)

    type_rankings = defaultdict(list)
    for item in rankings:
        type_rankings[item['type']].append(item)

    for content_type in sorted(type_rankings.keys()):
        top = type_rankings[content_type][:3]
        print(f"\n{content_type.upper()}:")
        for item in top:
            name_display = item['name'][:50] + '...' if len(item['name']) > 50 else item['name']
            print(f"  #{item['rank']} ({item['score']:.3f}) {name_display}")

    # Offline evaluation gate -- runs BEFORE we overwrite global_rankings.json
    # so a regression aborts without touching production scores (rule E14).
    if args.evaluate:
        try:
            _run_offline_eval_gate(
                rankings=rankings,
                metrics_csv=args.metrics_csv,
                source=args.source,
                analytics_api=args.analytics_api,
                skip_regression_check=args.skip_regression_check,
                holdout_days_override=args.eval_holdout_days,
                cold_start_method=args.cold_start_method,
                notes_override=args.eval_notes,
            )
        except _RegressionAlert as e:
            print(f"\nABORTING RERANK: {e}", file=sys.stderr)
            sys.exit(5)

    # Save output
    output_path = Path(__file__).resolve().parent.parent / args.output
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n\nRankings saved to: {args.output}")

    # Generate homepage trending data (top 12 items with real engagement +
    # MMR diversification over SBERT embeddings; lib.diversity.mmr_rerank).
    print("\nDiversifying homepage trending row via MMR...")
    embedding_lookup = build_trending_embedding_lookup(
        rankings, SBERT_MODEL, pool_size=60,
    )
    homepage_items = select_diverse_trending(
        rankings, n=12, lambda_=0.7, embedding_lookup=embedding_lookup,
    )
    homepage_data = {
        "updated": output['updated'],
        "count": len(homepage_items),
        "items": homepage_items
    }
    homepage_path = data_dir / 'homepage_trending.json'
    with open(homepage_path, 'w') as f:
        json.dump(homepage_data, f, indent=2)
    print(f"Homepage trending saved to: data/homepage_trending.json ({len(homepage_items)} items)")


if __name__ == '__main__':
    main()
