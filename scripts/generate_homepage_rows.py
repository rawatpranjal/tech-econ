#!/usr/bin/env python3
"""
Homepage Row Generator
Generates Netflix-style content rows for the homepage from ranked data sources.

Usage:
    python3 scripts/generate_homepage_rows.py
    python3 scripts/generate_homepage_rows.py --output data/homepage_rows.json
    python3 scripts/generate_homepage_rows.py --max-rows 15 --critique-iterations 3
"""

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict


DATA_DIR = Path(__file__).parent.parent / "data"

# Row templates
TEMPLATE_HERO = "hero"
TEMPLATE_STANDARD = "standard"
TEMPLATE_NARRATIVE = "narrative"
TEMPLATE_COMPACT = "compact"

# Content types across the site
ALL_TYPES = {"package", "dataset", "resource", "paper", "talk", "career", "community", "book"}

# Max items same type per row (unless type-specific rows like datasets/talks)
MAX_SAME_TYPE_PER_ROW = 3

# Row item count bounds
ROW_MIN_ITEMS = 5
ROW_MAX_ITEMS = 12


def load_json(path: Path) -> dict | list | None:
    """Load a JSON file, return None if missing or invalid."""
    if not path.exists():
        print(f"  Warning: {path.name} not found, skipping")
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Warning: Failed to load {path.name}: {e}")
        return None


def load_content_lookup(data_dir: Path) -> dict[str, dict]:
    """Build a name -> item metadata lookup from all content files."""
    lookup: dict[str, dict] = {}

    content_files = {
        "packages.json": "package",
        "datasets.json": "dataset",
        "resources.json": "resource",
        "papers_flat.json": "paper",
        "talks.json": "talk",
        "career.json": "career",
        "community.json": "community",
        "books.json": "book",
    }

    for filename, content_type in content_files.items():
        data = load_json(data_dir / filename)
        if data is None:
            continue
        items = data if isinstance(data, list) else []
        for item in items:
            name = item.get("name") or item.get("title", "")
            if not name:
                continue
            url = (
                item.get("url")
                or item.get("github_url")
                or item.get("docs_url")
                or ""
            )
            # Generate image_url for types that lack them
            image_url = item.get("image_url", "")
            if not image_url:
                if content_type == "package":
                    github_url = item.get("github_url") or ""
                    if "github.com/" in github_url:
                        owner = github_url.split("github.com/")[1].split("/")[0]
                        image_url = f"https://github.com/{owner}.png?size=128"
                elif content_type == "book":
                    isbn = item.get("isbn") or ""
                    if isbn:
                        image_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"

            key = name.lower().strip()
            lookup[key] = {
                "name": name,
                "type": content_type,
                "category": item.get("category", ""),
                "description": item.get("description") or item.get("summary", ""),
                "url": url,
                "image_url": image_url,
                "tags": item.get("tags", []),
            }

    return lookup


def build_score_lookup(rankings: list[dict]) -> dict[str, float]:
    """Build name -> score lookup from global_rankings."""
    return {r["name"].lower().strip(): r.get("score", 0.0) for r in rankings}


def make_item(ranking_entry: dict, content_lookup: dict) -> dict:
    """Build a normalized item dict from a ranking entry."""
    name = ranking_entry.get("name", "")
    key = name.lower().strip()
    meta = content_lookup.get(key, {})

    return {
        "name": name,
        "type": ranking_entry.get("type", meta.get("type", "unknown")),
        "category": ranking_entry.get("category", meta.get("category", "")),
        "description": ranking_entry.get("description", meta.get("description", "")),
        "url": ranking_entry.get("url", meta.get("url", "")),
        "image_url": ranking_entry.get("image_url", meta.get("image_url", "")),
        "score": ranking_entry.get("score", 0.0),
        "cold_start": ranking_entry.get("cold_start", True),
        "signals": ranking_entry.get("signals", {}),
    }


def make_item_from_meta(meta: dict, score_lookup: dict) -> dict:
    """Build a normalized item dict from content metadata."""
    name = meta.get("name", "")
    key = name.lower().strip()
    return {
        "name": name,
        "type": meta.get("type", "unknown"),
        "category": meta.get("category", ""),
        "description": meta.get("description", ""),
        "url": meta.get("url", ""),
        "image_url": meta.get("image_url", ""),
        "score": score_lookup.get(key, 0.0),
        "cold_start": score_lookup.get(key, -1.0) == -1.0,
        "signals": {},
    }


def apply_type_cap(items: list[dict], max_same_type: int) -> list[dict]:
    """Cap items to max_same_type per content type."""
    type_counts: dict[str, int] = defaultdict(int)
    result = []
    for item in items:
        t = item.get("type", "unknown")
        if type_counts[t] < max_same_type:
            type_counts[t] += 1
            result.append(item)
    return result


def dedup_against_used(items: list[dict], used: set[str]) -> list[dict]:
    """Remove items whose names are already in used set."""
    return [i for i in items if i["name"].lower().strip() not in used]


def mark_used(items: list[dict], used: set[str]) -> None:
    """Add item names to the used set."""
    for item in items:
        used.add(item["name"].lower().strip())


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def build_trending_now(
    rankings: list[dict],
    staff_pick_names: set[str],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 0: Trending Now — top engaged non-cold-start items."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if not r.get("cold_start", True)
        and r["name"].lower().strip() not in staff_pick_names
    ]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    items = candidates[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "trending-now",
        "row_type": "trending",
        "title": "Trending Now",
        "description": "What the community is reading and clicking most",
        "template": TEMPLATE_HERO,
        "items": items,
    }


def build_staff_picks(
    staff_picks_data: dict,
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 1: Staff Picks — hand-curated essentials."""
    items = []
    for pick in staff_picks_data.get("items", []):
        name = pick.get("name", "")
        key = name.lower().strip()
        meta = content_lookup.get(key)
        if meta:
            item = make_item_from_meta(meta, score_lookup)
        else:
            item = {
                "name": name,
                "type": pick.get("type", "unknown"),
                "category": "",
                "description": "",
                "url": "",
                "score": 0.0,
                "cold_start": True,
                "signals": {},
            }
        items.append(item)

    items = dedup_against_used(items, used)
    mark_used(items, used)
    return {
        "id": "staff-picks",
        "row_type": "staff_picks",
        "title": "Staff Picks",
        "description": staff_picks_data.get(
            "description", "Hand-picked essentials across the tech-econ landscape"
        ),
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def build_new_this_month(
    rankings: list[dict],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 2: New This Month — items with impressions but few deep sessions."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("signals", {}).get("impressions", 0) > 0
        and r.get("signals", {}).get("deep_sessions", 0) < 5
    ]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    # Sort by impressions desc (newest/active items)
    candidates.sort(
        key=lambda x: x.get("signals", {}).get("impressions", 0), reverse=True
    )
    items = candidates[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "new-this-month",
        "row_type": "new_this_month",
        "title": "New This Month",
        "description": "Recently surfaced — getting noticed but not yet deep-dived",
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def build_most_clicked(
    rankings: list[dict],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 3: Most Clicked This Week — by raw click count."""
    candidates = sorted(
        rankings,
        key=lambda r: r.get("signals", {}).get("clicks", 0),
        reverse=True,
    )
    candidates = [make_item(r, content_lookup) for r in candidates if r.get("signals", {}).get("clicks", 0) > 0]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    items = candidates[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "most-clicked",
        "row_type": "most_clicked",
        "title": "Most Clicked This Week",
        "description": "The links people are actually following right now",
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def _score_narrative_carousel(carousel: dict, score_lookup: dict) -> float:
    """Average model_score of items in a narrative carousel."""
    scores = []
    hero = carousel.get("hero", {})
    hero_title = hero.get("title", "")
    if hero_title:
        scores.append(score_lookup.get(hero_title.lower().strip(), 0.0))
    for item in carousel.get("items", []):
        title = item.get("title", "")
        if title:
            scores.append(score_lookup.get(title.lower().strip(), 0.0))
    return sum(scores) / max(len(scores), 1)


def _narrative_carousel_to_items(
    carousel: dict, content_lookup: dict, score_lookup: dict, used: set[str]
) -> list[dict]:
    """Convert a narrative carousel into normalized item dicts."""
    items = []
    # Hero first
    hero = carousel.get("hero", {})
    hero_title = hero.get("title", "")
    if hero_title:
        key = hero_title.lower().strip()
        meta = content_lookup.get(key, {})
        items.append({
            "name": hero_title,
            "type": hero.get("type", meta.get("type", "unknown")),
            "category": meta.get("category", ""),
            "description": meta.get("description", ""),
            "url": hero.get("url", meta.get("url", "")),
            "score": score_lookup.get(key, 0.0),
            "cold_start": score_lookup.get(key, -1) < 0,
            "signals": {},
            "is_hero": True,
        })
    for c_item in carousel.get("items", []):
        title = c_item.get("title", "")
        if not title:
            continue
        key = title.lower().strip()
        meta = content_lookup.get(key, {})
        items.append({
            "name": title,
            "type": c_item.get("type", meta.get("type", "unknown")),
            "category": meta.get("category", ""),
            "description": meta.get("description", ""),
            "url": c_item.get("url", meta.get("url", "")),
            "score": score_lookup.get(key, 0.0),
            "cold_start": score_lookup.get(key, -1) < 0,
            "signals": {},
        })
    return dedup_against_used(items, used)


def build_deep_dive(
    narrative_carousels: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 4: Deep Dive — best problem/tool carousel with type diversity."""
    candidates = [
        c for c in narrative_carousels
        if c.get("template") in ("problem", "tool")
    ]
    # Score each carousel
    candidates.sort(
        key=lambda c: _score_narrative_carousel(c, score_lookup), reverse=True
    )
    # Pick first carousel whose items give type diversity (3+ types)
    chosen = None
    items: list[dict] = []
    for carousel in candidates:
        candidate_items = _narrative_carousel_to_items(carousel, content_lookup, score_lookup, used)
        types_present = {i["type"] for i in candidate_items}
        if len(types_present) >= 2:
            chosen = carousel
            items = candidate_items
            break
    if chosen is None and candidates:
        chosen = candidates[0]
        items = _narrative_carousel_to_items(chosen, content_lookup, score_lookup, used)

    if not items:
        return None

    # Apply type cap so one type doesn't dominate
    items = apply_type_cap(items, MAX_SAME_TYPE_PER_ROW)
    name = chosen.get("name", "Deep Dive")
    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": f"deep-dive-{chosen.get('id', 'unknown')}",
        "row_type": "deep_dive",
        "title": f"Deep Dive: {name}",
        "description": chosen.get("description", ""),
        "template": TEMPLATE_NARRATIVE,
        "source_carousel_id": chosen.get("id"),
        "items": items,
    }


def build_persons_universe(
    narrative_carousels: list[dict],
    rankings: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 5: Person's Universe — best person carousel."""
    candidates = [c for c in narrative_carousels if c.get("template") == "person"]
    candidates.sort(
        key=lambda c: _score_narrative_carousel(c, score_lookup), reverse=True
    )
    chosen = None
    items: list[dict] = []
    for carousel in candidates:
        candidate_items = _narrative_carousel_to_items(carousel, content_lookup, score_lookup, used)
        if len(candidate_items) >= 3:
            chosen = carousel
            items = candidate_items
            break
    if chosen is None and candidates:
        chosen = candidates[0]
        items = _narrative_carousel_to_items(chosen, content_lookup, score_lookup, used)

    if not items:
        return None

    # Pad short carousels with additional items from rankings if needed
    if len(items) < ROW_MIN_ITEMS:
        seed_types = {i["type"] for i in items}
        for r in rankings:
            if len(items) >= ROW_MIN_ITEMS:
                break
            key = r["name"].lower().strip()
            if key in used or r.get("type") not in seed_types:
                continue
            if not any(i["name"].lower().strip() == key for i in items):
                items.append(make_item(r, content_lookup))

    name = chosen.get("name", "Person's Universe")
    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": f"persons-universe-{chosen.get('id', 'unknown')}",
        "row_type": "persons_universe",
        "title": name,
        "description": chosen.get("description", ""),
        "template": TEMPLATE_NARRATIVE,
        "source_carousel_id": chosen.get("id"),
        "items": items,
    }


def build_essential_toolkit(
    package_clusters: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 6: Essential Toolkit — best package cluster."""
    best_cluster = None
    best_score = -1.0
    for cluster in package_clusters:
        carousel_items = cluster.get("carousel_items") or cluster.get("items", [])
        if not carousel_items:
            continue
        scores = [score_lookup.get(n.lower().strip(), 0.0) for n in carousel_items if n]
        avg = sum(scores) / max(len(scores), 1)
        if avg > best_score:
            # Check if enough items are available after dedup
            available = [n for n in carousel_items if n and n.lower().strip() not in used]
            if len(available) >= ROW_MIN_ITEMS:
                best_score = avg
                best_cluster = cluster

    if best_cluster is None:
        # Fallback: any cluster with enough items
        for cluster in package_clusters:
            carousel_items = cluster.get("carousel_items") or cluster.get("items", [])
            available = [n for n in carousel_items if n and n.lower().strip() not in used]
            if len(available) >= 3:
                best_cluster = cluster
                break

    if best_cluster is None:
        return None

    carousel_items = best_cluster.get("carousel_items") or best_cluster.get("items", [])
    items = []
    for name in carousel_items:
        if not name:
            continue
        key = name.lower().strip()
        if key in used:
            continue
        meta = content_lookup.get(key, {})
        items.append({
            "name": name,
            "type": "package",
            "category": best_cluster.get("macro_category", meta.get("category", "")),
            "description": meta.get("description", ""),
            "url": meta.get("url", ""),
            "score": score_lookup.get(key, 0.0),
            "cold_start": score_lookup.get(key, -1) < 0,
            "signals": {},
        })

    items.sort(key=lambda x: x["score"], reverse=True)
    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)

    label = best_cluster.get("creative_name") or best_cluster.get("label", "Tools")
    return {
        "id": f"toolkit-{best_cluster.get('id', 'unknown')}",
        "row_type": "essential_toolkit",
        "title": f"Essential {label} Toolkit",
        "description": f"Core packages for {best_cluster.get('macro_category', label).lower()} work",
        "template": TEMPLATE_STANDARD,
        "source_cluster_id": best_cluster.get("id"),
        "items": items,
    }


def build_learning_path(
    narrative_carousels: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 7: Learning Path — best journey carousel."""
    candidates = [c for c in narrative_carousels if c.get("template") == "journey"]
    candidates.sort(
        key=lambda c: _score_narrative_carousel(c, score_lookup), reverse=True
    )
    chosen = None
    items: list[dict] = []
    for carousel in candidates:
        candidate_items = _narrative_carousel_to_items(carousel, content_lookup, score_lookup, used)
        if len(candidate_items) >= 3:
            chosen = carousel
            items = candidate_items
            break
    if chosen is None and candidates:
        chosen = candidates[0]
        items = _narrative_carousel_to_items(chosen, content_lookup, score_lookup, used)

    if not items:
        return None

    name = chosen.get("name", "Learning Path")
    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": f"learning-path-{chosen.get('id', 'unknown')}",
        "row_type": "learning_path",
        "title": f"Learning Path: {name}",
        "description": chosen.get("description", ""),
        "template": TEMPLATE_NARRATIVE,
        "source_carousel_id": chosen.get("id"),
        "items": items,
    }


def build_if_you_like(
    rankings: list[dict],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 8: If You Like... — items with highest co-occurrence signals, same category."""
    # Find the item with most co-occurrence partners
    best_item = None
    best_coview = 0
    for r in rankings:
        sigs = r.get("signals", {})
        coview = sigs.get("coviews", 0)
        coclick = sigs.get("coclicks", 0)
        combined = coview * 0.7 + coclick * 0.3
        if combined > best_coview and r["name"].lower().strip() not in used:
            best_coview = combined
            best_item = r

    if best_item is None:
        return None

    seed_category = best_item.get("category", "")
    seed_name = best_item["name"]

    # Find items in same category, sorted by score
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("category", "") == seed_category
        and r["name"] != seed_name
    ]
    candidates = dedup_against_used(candidates, used)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    items = candidates[:ROW_MAX_ITEMS]
    mark_used(items, used)

    return {
        "id": "if-you-like",
        "row_type": "if_you_like",
        "title": f"If You Like {seed_name}...",
        "description": f"More from {seed_category or 'this corner of the field'}",
        "template": TEMPLATE_STANDARD,
        "seed_item": seed_name,
        "items": items,
    }


def build_foundational_papers(
    narrative_carousels: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 9: Foundational Papers — best method carousel."""
    candidates = [c for c in narrative_carousels if c.get("template") == "method"]
    candidates.sort(
        key=lambda c: _score_narrative_carousel(c, score_lookup), reverse=True
    )
    chosen = None
    items: list[dict] = []
    for carousel in candidates:
        candidate_items = _narrative_carousel_to_items(carousel, content_lookup, score_lookup, used)
        if len(candidate_items) >= 3:
            chosen = carousel
            items = candidate_items
            break
    if chosen is None and candidates:
        chosen = candidates[0]
        items = _narrative_carousel_to_items(chosen, content_lookup, score_lookup, used)

    if not items:
        return None

    name = chosen.get("name", "Foundational Papers")
    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": f"foundational-papers-{chosen.get('id', 'unknown')}",
        "row_type": "foundational_papers",
        "title": f"Foundational Papers: {name}",
        "description": chosen.get("description", ""),
        "template": TEMPLATE_NARRATIVE,
        "source_carousel_id": chosen.get("id"),
        "items": items,
    }


def build_hidden_gems(
    rankings: list[dict],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 10: Hidden Gems — cold_start items with score > 0."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("cold_start", True) and r.get("score", 0.0) > 0
    ]
    candidates = dedup_against_used(candidates, used)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    # Max 2 per type for variety
    candidates = apply_type_cap(candidates, 2)
    items = candidates[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "hidden-gems",
        "row_type": "hidden_gems",
        "title": "Hidden Gems",
        "description": "Under-the-radar items worth discovering",
        "template": TEMPLATE_COMPACT,
        "items": items,
    }


def build_datasets_to_explore(
    dataset_clusters: list[dict],
    rankings: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 11: Datasets to Explore — from dataset clusters or rankings fallback."""
    items: list[dict] = []

    # Try to find a good cluster
    best_cluster = None
    best_score = -1.0
    for cluster in dataset_clusters:
        cluster_items = cluster.get("carousel_items") or cluster.get("items", [])
        clean = [n for n in cluster_items if n and n.lower().strip() not in used]
        if len(clean) < 3:
            continue
        scores = [score_lookup.get(n.lower().strip(), 0.0) for n in clean]
        avg = sum(scores) / max(len(scores), 1)
        if avg > best_score:
            best_score = avg
            best_cluster = cluster

    if best_cluster is not None:
        cluster_items = best_cluster.get("carousel_items") or best_cluster.get("items", [])
        for name in cluster_items:
            if not name:
                continue
            key = name.lower().strip()
            if key in used:
                continue
            meta = content_lookup.get(key, {})
            items.append({
                "name": name,
                "type": "dataset",
                "category": best_cluster.get("macro_category", meta.get("category", "")),
                "description": meta.get("description", ""),
                "url": meta.get("url", ""),
                "score": score_lookup.get(key, 0.0),
                "cold_start": score_lookup.get(key, -1) < 0,
                "signals": {},
            })
        items.sort(key=lambda x: x["score"], reverse=True)

    # Fallback: top datasets from rankings
    if len(items) < ROW_MIN_ITEMS:
        fallback = [
            make_item(r, content_lookup)
            for r in rankings
            if r.get("type") == "dataset"
        ]
        fallback = dedup_against_used(fallback, used)
        items.extend(fallback)

    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "datasets-to-explore",
        "row_type": "datasets",
        "title": "Datasets to Explore",
        "description": "Curated datasets for empirical research",
        "template": TEMPLATE_COMPACT,
        "items": items,
    }


def build_talks_worth_watching(
    talk_clusters: list[dict],
    rankings: list[dict],
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Row 12: Talks Worth Watching — from talk clusters or rankings fallback."""
    items: list[dict] = []

    # Try clusters
    best_cluster = None
    best_score = -1.0
    for cluster in talk_clusters:
        cluster_items = cluster.get("carousel_items") or cluster.get("items", [])
        clean = [n for n in cluster_items if n and n.lower().strip() not in used]
        if len(clean) < 3:
            continue
        scores = [score_lookup.get(n.lower().strip(), 0.0) for n in clean]
        avg = sum(scores) / max(len(scores), 1)
        if avg > best_score:
            best_score = avg
            best_cluster = cluster

    if best_cluster is not None:
        cluster_items = best_cluster.get("carousel_items") or best_cluster.get("items", [])
        for name in cluster_items:
            if not name:
                continue
            key = name.lower().strip()
            if key in used:
                continue
            meta = content_lookup.get(key, {})
            items.append({
                "name": name,
                "type": "talk",
                "category": best_cluster.get("macro_category", meta.get("category", "")),
                "description": meta.get("description", ""),
                "url": meta.get("url", ""),
                "score": score_lookup.get(key, 0.0),
                "cold_start": score_lookup.get(key, -1) < 0,
                "signals": {},
            })
        items.sort(key=lambda x: x["score"], reverse=True)

    # Fallback: top talks from rankings
    if len(items) < ROW_MIN_ITEMS:
        fallback = [
            make_item(r, content_lookup)
            for r in rankings
            if r.get("type") == "talk"
        ]
        fallback = dedup_against_used(fallback, used)
        items.extend(fallback)

    items = items[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "talks-worth-watching",
        "row_type": "talks",
        "title": "Talks Worth Watching",
        "description": "The best lectures, interviews, and presentations",
        "template": TEMPLATE_COMPACT,
        "items": items,
    }


def build_community_events(
    rankings: list[dict],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 13: Community & Events — community items, max 2 per category."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("type") == "community"
    ]
    candidates = dedup_against_used(candidates, used)
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Max 2 per category
    category_counts: dict[str, int] = defaultdict(int)
    items = []
    for item in candidates:
        cat = item.get("category", "other")
        if category_counts[cat] < 2:
            category_counts[cat] += 1
            items.append(item)
        if len(items) >= ROW_MAX_ITEMS:
            break

    mark_used(items, used)
    return {
        "id": "community-events",
        "row_type": "community",
        "title": "Community & Events",
        "description": "Research groups, conferences, and meetups",
        "template": TEMPLATE_COMPACT,
        "items": items,
    }


def build_career_corner(
    rankings: list[dict],
    content_lookup: dict,
    used: set[str],
) -> dict:
    """Row 14: Career Corner — career items."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("type") == "career"
    ]
    candidates = dedup_against_used(candidates, used)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    items = candidates[:ROW_MAX_ITEMS]
    mark_used(items, used)
    return {
        "id": "career-corner",
        "row_type": "career",
        "title": "Career Corner",
        "description": "Jobs, companies, and career resources for tech economists",
        "template": TEMPLATE_COMPACT,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Critique loop
# ---------------------------------------------------------------------------

def critique_rows(rows: list[dict]) -> list[str]:
    """Run built-in quality checks. Returns list of issue strings."""
    issues = []
    all_items: list[tuple[str, str]] = []  # (name, row_id)
    type_coverage: set[str] = set()

    for row in rows:
        row_id = row.get("id", "unknown")
        items = row.get("items", [])
        count = len(items)

        if count < ROW_MIN_ITEMS:
            issues.append(
                f"Row '{row_id}' has only {count} items (min {ROW_MIN_ITEMS})"
            )
        if count > ROW_MAX_ITEMS:
            issues.append(
                f"Row '{row_id}' has {count} items (max {ROW_MAX_ITEMS})"
            )

        type_counts: dict[str, int] = defaultdict(int)
        for item in items:
            name = item.get("name", "")
            itype = item.get("type", "unknown")
            all_items.append((name.lower().strip(), row_id))
            type_coverage.add(itype)
            type_counts[itype] += 1

        # Check type diversity for non-type-specific rows
        if row.get("row_type") not in ("datasets", "talks", "community", "career"):
            for t, cnt in type_counts.items():
                if cnt > MAX_SAME_TYPE_PER_ROW:
                    issues.append(
                        f"Row '{row_id}' has {cnt} items of type '{t}' (max {MAX_SAME_TYPE_PER_ROW})"
                    )

    # Check for cross-row duplicates
    seen: dict[str, str] = {}
    for name, row_id in all_items:
        if name in seen:
            issues.append(
                f"Duplicate item '{name}' in rows '{seen[name]}' and '{row_id}'"
            )
        else:
            seen[name] = row_id

    # Check section coverage
    missing_types = ALL_TYPES - type_coverage
    if missing_types:
        issues.append(f"Missing content types across all rows: {missing_types}")

    return issues


def fix_row_item_counts(row: dict, all_candidates: list[dict], used: set[str]) -> None:
    """Attempt to pad rows that are too short using any available candidates."""
    items = row.get("items", [])
    if len(items) >= ROW_MIN_ITEMS:
        return
    needed = ROW_MIN_ITEMS - len(items)
    current_names = {i["name"].lower().strip() for i in items}
    for candidate in all_candidates:
        if needed <= 0:
            break
        key = candidate["name"].lower().strip()
        if key not in current_names and key not in used:
            items.append(candidate)
            current_names.add(key)
            used.add(key)
            needed -= 1
    row["items"] = items


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_rows(data_dir: Path, max_rows: int, critique_iterations: int) -> dict:
    """Generate all homepage rows."""
    print("Loading data files...")

    global_data = load_json(data_dir / "global_rankings.json") or {}
    rankings: list[dict] = global_data.get("rankings", [])
    print(f"  Loaded {len(rankings)} ranked items")

    narrative_data = load_json(data_dir / "narrative_carousels.json") or {}
    narrative_carousels: list[dict] = narrative_data.get("carousels", [])
    print(f"  Loaded {len(narrative_carousels)} narrative carousels")

    package_cluster_data = load_json(data_dir / "package_clusters.json") or {}
    package_clusters: list[dict] = package_cluster_data.get("clusters", [])
    print(f"  Loaded {len(package_clusters)} package clusters")

    dataset_cluster_data = load_json(data_dir / "dataset_clusters.json") or {}
    dataset_clusters: list[dict] = dataset_cluster_data.get("clusters", [])
    print(f"  Loaded {len(dataset_clusters)} dataset clusters")

    talk_cluster_data = load_json(data_dir / "talk_clusters.json") or {}
    talk_clusters: list[dict] = talk_cluster_data.get("clusters", [])
    print(f"  Loaded {len(talk_clusters)} talk clusters")

    staff_picks_data = load_json(data_dir / "staff_picks.json") or {"items": []}
    print(f"  Loaded {len(staff_picks_data.get('items', []))} staff picks")

    content_lookup = load_content_lookup(data_dir)
    print(f"  Built content lookup with {len(content_lookup)} items")

    score_lookup = build_score_lookup(rankings)

    critique_log: list[dict] = []
    best_rows: list[dict] = []

    for iteration in range(max(1, critique_iterations + 1)):
        print(f"\nGenerating rows (iteration {iteration + 1})...")
        used: set[str] = set()

        staff_pick_names = {
            p["name"].lower().strip()
            for p in staff_picks_data.get("items", [])
        }

        rows: list[dict] = []

        # Row 0: Trending Now
        rows.append(
            build_trending_now(rankings, staff_pick_names, content_lookup, used)
        )

        # Row 1: Staff Picks
        rows.append(
            build_staff_picks(staff_picks_data, content_lookup, score_lookup, used)
        )

        # Row 2: New This Month
        rows.append(build_new_this_month(rankings, content_lookup, used))

        # Row 3: Most Clicked This Week
        rows.append(build_most_clicked(rankings, content_lookup, used))

        # Row 4: Deep Dive
        row4 = build_deep_dive(narrative_carousels, content_lookup, score_lookup, used)
        if row4:
            rows.append(row4)

        # Row 5: Person's Universe
        row5 = build_persons_universe(narrative_carousels, rankings, content_lookup, score_lookup, used)
        if row5:
            rows.append(row5)

        # Row 6: Essential Toolkit
        row6 = build_essential_toolkit(package_clusters, content_lookup, score_lookup, used)
        if row6:
            rows.append(row6)

        # Row 7: Learning Path
        row7 = build_learning_path(narrative_carousels, content_lookup, score_lookup, used)
        if row7:
            rows.append(row7)

        # Row 8: If You Like...
        row8 = build_if_you_like(rankings, content_lookup, used)
        if row8:
            rows.append(row8)

        # Row 9: Foundational Papers
        row9 = build_foundational_papers(narrative_carousels, content_lookup, score_lookup, used)
        if row9:
            rows.append(row9)

        # Row 10: Hidden Gems
        rows.append(build_hidden_gems(rankings, content_lookup, used))

        # Row 11: Datasets to Explore
        rows.append(
            build_datasets_to_explore(
                dataset_clusters, rankings, content_lookup, score_lookup, used
            )
        )

        # Row 12: Talks Worth Watching
        rows.append(
            build_talks_worth_watching(
                talk_clusters, rankings, content_lookup, score_lookup, used
            )
        )

        # Row 13: Community & Events
        rows.append(build_community_events(rankings, content_lookup, used))

        # Row 14: Career Corner — DISABLED (career accessible via sidebar)
        # rows.append(build_career_corner(rankings, content_lookup, used))

        # Filter career items from all non-career rows
        for row in rows:
            row["items"] = [i for i in row["items"] if i.get("type") != "career"]

        # Apply max_rows cap
        rows = rows[:max_rows]

        # Run critique
        issues = critique_rows(rows)
        critique_log.append({
            "iteration": iteration + 1,
            "issues": issues,
            "issue_count": len(issues),
        })

        if issues:
            print(f"  Critique found {len(issues)} issue(s):")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  Critique: all checks passed")

        best_rows = rows

        # No auto-fix on last iteration
        if iteration < critique_iterations and issues:
            # Fix: trim oversized rows
            for row in rows:
                if len(row.get("items", [])) > ROW_MAX_ITEMS:
                    row["items"] = row["items"][:ROW_MAX_ITEMS]
                    print(f"  Fixed: trimmed '{row['id']}' to {ROW_MAX_ITEMS} items")
            # Fix: pad undersized rows with available candidates
            all_candidates = [make_item(r, content_lookup) for r in rankings if r["name"].lower().strip() not in used]
            for row in rows:
                if len(row.get("items", [])) < ROW_MIN_ITEMS:
                    before = len(row["items"])
                    fix_row_item_counts(row, all_candidates, used)
                    after = len(row["items"])
                    if after > before:
                        print(f"  Fixed: padded '{row['id']}' from {before} to {after} items")

    # Compute stats
    total_items = sum(len(r.get("items", [])) for r in best_rows)
    unique_types: set[str] = set()
    for row in best_rows:
        for item in row.get("items", []):
            unique_types.add(item.get("type", "unknown"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_rows": len(best_rows),
            "total_items": total_items,
            "unique_types": sorted(unique_types),
            "type_count": len(unique_types),
            "critique_iterations": critique_iterations,
        },
        "critique_log": critique_log,
        "rows": best_rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate Netflix-style homepage rows")
    parser.add_argument(
        "--output",
        default="data/homepage_rows.json",
        help="Output file path (default: data/homepage_rows.json)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=15,
        help="Maximum number of rows to generate (default: 15)",
    )
    parser.add_argument(
        "--critique-iterations",
        type=int,
        default=3,
        help="Number of critique-and-fix iterations (default: 3)",
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data"
    output_path = Path(__file__).parent.parent / args.output

    print("Homepage Row Generator")
    print("=" * 50)
    result = generate_rows(data_dir, args.max_rows, args.critique_iterations)

    print(f"\nWriting {len(result['rows'])} rows to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(f"\nDone.")
    print(f"  Rows: {result['stats']['total_rows']}")
    print(f"  Items: {result['stats']['total_items']}")
    print(f"  Types covered: {', '.join(result['stats']['unique_types'])}")

    last_critique = result["critique_log"][-1] if result["critique_log"] else {}
    if last_critique.get("issue_count", 0) == 0:
        print("  Final critique: PASS")
    else:
        print(f"  Final critique: {last_critique['issue_count']} issue(s) remain")


if __name__ == "__main__":
    main()
