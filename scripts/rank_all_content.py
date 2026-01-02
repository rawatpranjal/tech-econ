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
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_predict, train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score
from sentence_transformers import SentenceTransformer

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("Warning: lightgbm not installed, falling back to Ridge regression")

# Load sentence transformer model for semantic embeddings
print("Loading sentence-BERT model...")
SBERT_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
print("  Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

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
RAGE_CLICK_WEIGHT = -2.0   # Frustration = negative signal
QUICK_BOUNCE_WEIGHT = -1.0 # Left quickly = not useful
DEEP_SESSION_WEIGHT = 1.5  # Part of "deep" engagement session
COVIEW_WEIGHT = 0.1        # Co-viewed with engaged items
COCLICK_WEIGHT = 0.3       # Co-clicked with engaged items


def fetch_d1_data(query):
    """Execute D1 query via wrangler and return results."""
    cmd = [
        'npx', 'wrangler', 'd1', 'execute', 'tech-econ-analytics-db',
        '--remote', '--command', query, '--json'
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd='/Users/pranjal/metrics-packages/analytics-worker'
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

    return {
        'clicks': clicks,
        'impressions': impressions,
        'dwell': dwell,
        'scroll': scroll,
        'search_clicks': search_clicks,
        'session_tiers': session_tiers,
        'frustration': frustration,
        'cooccurrence': cooccurrence,
    }


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

    scores = defaultdict(float)
    item_signals = defaultdict(lambda: {
        'clicks': 0, 'impressions': 0, 'dwell_ms': 0, 'viewable_sec': 0,
        'scroll_90': 0, 'scroll_75': 0, 'scroll_50': 0,
        'search_clicks': 0, 'deep_sessions': 0,
        'rage_clicks': 0, 'quick_bounces': 0,
        'coviews': 0, 'coclicks': 0
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

    # NEW: Aggregate search-to-click attribution
    for row in search_clicks:
        clicks_json = row.get('clicks', '[]')
        try:
            click_list = json.loads(clicks_json) if isinstance(clicks_json, str) else clicks_json
            for click in click_list:
                # click might be {id: "item name", position: 1, dwellMs: 5000}
                if isinstance(click, dict):
                    name = click.get('id', '').lower().strip()
                elif isinstance(click, str):
                    name = click.lower().strip()
                else:
                    continue
                if name:
                    scores[name] += SEARCH_CLICK_WEIGHT
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

    # Ensure scores don't go negative (from frustration signals)
    for name in scores:
        scores[name] = max(0, scores[name])

    return dict(scores), dict(item_signals), cooccurrence


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

    # Build target: engagement score = clicks*5 + impressions*1 + dwell_minutes
    y = []
    for item in items:
        name = item['name']
        signals = item_signals.get(name, {})
        clicks = signals.get('clicks', 0)
        impressions = signals.get('impressions', 0)
        dwell_ms = signals.get('dwell_ms', 0)
        dwell_minutes = dwell_ms / 60000.0

        score = clicks * CLICK_WEIGHT + impressions * IMPRESSION_WEIGHT + dwell_minutes * DWELL_WEIGHT
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

    if HAS_LIGHTGBM:
        # Use LightGBM with Tweedie loss for zero-inflated data
        model = lgb.LGBMRegressor(
            objective='tweedie',
            tweedie_variance_power=1.5,  # Between Poisson(1) and Gamma(2)
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=5,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=1.0,
            random_state=42,
            verbose=-1
        )
        model_name = "LightGBM-Tweedie"
    else:
        from sklearn.linear_model import Ridge
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)
        X = scaler.fit_transform(X)
        model = Ridge(alpha=10.0)
        encoders['scaler'] = scaler
        model_name = "Ridge"

    # Train on training set
    model.fit(X_train, y_train)

    # Evaluate on holdout test set
    y_pred_test = model.predict(X_test)
    y_pred_test = np.maximum(y_pred_test, 0)  # Clip negatives

    # Regression metrics on test set
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    test_mae = mean_absolute_error(y_test, y_pred_test)
    test_r2 = r2_score(y_test, y_pred_test)

    # Baseline comparison (predicting mean)
    baseline_pred = np.full_like(y_test, y_train.mean())
    baseline_rmse = np.sqrt(mean_squared_error(y_test, baseline_pred))

    # Classification metric: can model rank engaged vs non-engaged?
    test_binary = (y_test > 0).astype(int)
    if len(np.unique(test_binary)) > 1:
        test_auc = roc_auc_score(test_binary, y_pred_test)
    else:
        test_auc = 0.5

    print(f"\n  === HOLDOUT TEST METRICS ===")
    print(f"  Test RMSE: {test_rmse:.3f}")
    print(f"  Test MAE:  {test_mae:.3f}")
    print(f"  Test R²:   {test_r2:.3f}")
    print(f"  Baseline RMSE (train mean): {baseline_rmse:.3f}")
    if baseline_rmse > 0:
        print(f"  RMSE vs baseline: {(test_rmse/baseline_rmse)*100:.1f}%")
    print(f"  AUC (any engagement): {test_auc:.3f}")

    # Per-interaction AUC
    for signal_name, signal_key in [('clicks', 'clicks'), ('impressions', 'impressions'), ('dwell', 'dwell_ms')]:
        signal_binary = np.array([
            1 if item_signals.get(items[i]['name'], {}).get(signal_key, 0) > 0 else 0
            for i in idx_test
        ])
        if signal_binary.sum() > 0 and signal_binary.sum() < len(signal_binary):
            signal_auc = roc_auc_score(signal_binary, y_pred_test)
            print(f"  AUC ({signal_name}): {signal_auc:.3f}")

    # Retrain on full data for final model
    print(f"\n  Retraining on full data...")
    if not HAS_LIGHTGBM:
        X = scaler.fit_transform(X)
    model.fit(X, y)
    print(f"  {model_name} trained on {len(y)} items")

    # Get predicted scores for all items
    predictions = model.predict(X)

    # Clip negative predictions to 0
    predictions = np.maximum(predictions, 0)

    # Build score dict
    scores = {}
    for i, item in enumerate(items):
        scores[item['name']] = float(predictions[i])

    print(f"  Scored {len(scores)} items")
    print(f"  Predicted range: {predictions.min():.2f} to {predictions.max():.2f}")

    # Show feature importance
    n_cat = encoders['n_categorical']
    feature_names = [
        'type', 'category', 'difficulty', 'domain', 'desc_len', 'n_tags', 'n_topics', 'has_url', 'citations', 'name_len',
        'n_audience', 'n_use_cases', 'n_related', 'has_github', 'language', 'n_synthetic_q', 'desc_words', 'has_best_for'
    ]

    if HAS_LIGHTGBM and hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        cat_importances = importances[:n_cat]
        bert_importance_sum = importances[n_cat:].sum()

        sorted_idx = np.argsort(cat_importances)[::-1]
        print("  Top feature importances:")
        for idx in sorted_idx[:5]:
            print(f"    {feature_names[idx]}: {cat_importances[idx]:.1f}")
        print(f"    BERT embeddings (sum): {bert_importance_sum:.1f}")
    elif hasattr(model, 'coef_'):
        coefs = np.abs(model.coef_)
        cat_coefs = coefs[:n_cat]
        bert_coef_sum = coefs[n_cat:].sum()

        sorted_idx = np.argsort(cat_coefs)[::-1]
        print("  Top coefficient magnitudes:")
        for idx in sorted_idx[:5]:
            print(f"    {feature_names[idx]}: {cat_coefs[idx]:.3f}")
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

    print(f"  Applied citations boost to {boosted} papers")
    return scores


def main():
    parser = argparse.ArgumentParser(description='Rank all content items')
    parser.add_argument('--output', '-o', default='data/global_rankings.json',
                        help='Output file path')
    parser.add_argument('--k-neighbors', '-k', type=int, default=5,
                        help='Number of neighbors for cold start (default: 5)')
    args = parser.parse_args()

    data_dir = Path('/Users/pranjal/metrics-packages/data')

    # Step 1: Load all content
    print("Loading content catalog...")
    items = load_all_content(data_dir)
    print(f"\nTotal content items: {len(items)}")

    # Create name -> item lookup
    item_lookup = {item['name']: item for item in items}

    # Step 2: Fetch engagement data (now returns dict with all signal types)
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

    # Step 4: Train regression model to predict engagement scores
    model, regression_scores, encoders = train_regression_model(items, item_signals)

    # Step 5: Hybrid scoring - actual engagement for observed, predicted for cold-start
    if regression_scores:
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
                'rage_click': RAGE_CLICK_WEIGHT,
                'quick_bounce': QUICK_BOUNCE_WEIGHT,
                'deep_session': DEEP_SESSION_WEIGHT,
                'coview': COVIEW_WEIGHT,
                'coclick': COCLICK_WEIGHT,
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

    # Save output
    output_path = data_dir.parent / args.output
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n\nRankings saved to: {args.output}")

    # Generate homepage trending data (top 12 items with real engagement)
    homepage_items = [r for r in rankings if not r['cold_start']][:12]
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
