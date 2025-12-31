#!/usr/bin/env python3
"""
Generate narrative-driven carousels from data sources.

This script creates Netflix-style carousels organized by:
- PERSON: Leading economists and their work
- METHOD: High-citation foundational papers
- TOOL: Popular packages by category
- JOURNEY: Learning paths from roadmaps
- COMPANY: Company-specific content clusters
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional
import unicodedata

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "narrative_carousels.json"

# Configuration
MIN_ITEMS_PER_CAROUSEL = 4
MAX_ITEMS_PER_CAROUSEL = 8
MIN_CITATION_FOR_METHOD = 1000


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text


def load_json(filename: str) -> Any:
    """Load JSON file from data directory."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def build_item_lookup(all_data: Dict[str, Any]) -> Dict[str, Dict]:
    """Build a lookup dictionary for all items by ID."""
    lookup = {}

    # Packages
    for pkg in all_data.get('packages', []):
        item_id = f"package-{slugify(pkg.get('name', ''))}"
        lookup[item_id] = {**pkg, '_type': 'package', '_id': item_id}

    # Resources
    for res in all_data.get('resources', []):
        item_id = f"resource-{slugify(res.get('name', ''))}"
        lookup[item_id] = {**res, '_type': 'resource', '_id': item_id}

    # Talks
    for talk in all_data.get('talks', []):
        item_id = f"talk-{slugify(talk.get('name', ''))}"
        lookup[item_id] = {**talk, '_type': 'talk', '_id': item_id}

    # Datasets
    for ds in all_data.get('datasets', []):
        item_id = f"dataset-{slugify(ds.get('name', ''))}"
        lookup[item_id] = {**ds, '_type': 'dataset', '_id': item_id}

    # Books
    for book in all_data.get('books', []):
        item_id = f"book-{slugify(book.get('name', ''))}"
        lookup[item_id] = {**book, '_type': 'book', '_id': item_id}

    # Papers (flat structure)
    for paper in all_data.get('papers_flat', []):
        item_id = f"paper-{slugify(paper.get('name', paper.get('title', '')))}"
        lookup[item_id] = {**paper, '_type': 'paper', '_id': item_id}

    return lookup


def find_items_by_tags(lookup: Dict, tags: List[str], item_type: Optional[str] = None) -> List[Dict]:
    """Find items matching any of the given tags."""
    results = []
    tags_lower = [t.lower() for t in tags]

    for item_id, item in lookup.items():
        if item_type and item.get('_type') != item_type:
            continue

        item_tags = []
        for field in ['tags', 'topic_tags', 'specialty', 'category']:
            val = item.get(field, [])
            if isinstance(val, list):
                item_tags.extend([t.lower() for t in val])
            elif isinstance(val, str):
                item_tags.append(val.lower())

        if any(tag in ' '.join(item_tags) for tag in tags_lower):
            results.append(item)

    return results


def find_items_by_text(lookup: Dict, keywords: List[str], item_type: Optional[str] = None, min_matches: int = 1) -> List[Dict]:
    """Find items with keywords in name/title/description.

    Args:
        lookup: Item lookup dictionary
        keywords: List of keywords to search for
        item_type: Optional filter by item type
        min_matches: Minimum number of keywords that must match (default 1)
    """
    results = []
    keywords_lower = [k.lower() for k in keywords if k]  # Filter empty keywords

    for item_id, item in lookup.items():
        if item_type and item.get('_type') != item_type:
            continue

        text = ' '.join([
            str(item.get('name', '')),
            str(item.get('title', '')),
            str(item.get('description', '')),
            str(item.get('summary', ''))
        ]).lower()

        # Count how many keywords match
        match_count = sum(1 for kw in keywords_lower if kw in text)

        # Require minimum matches (but at least 1)
        required = min(min_matches, len(keywords_lower)) if keywords_lower else 1
        if match_count >= required:
            # Store match quality for sorting
            item['_match_score'] = match_count
            results.append(item)

    # Sort by match quality (most matches first)
    results.sort(key=lambda x: x.get('_match_score', 0), reverse=True)
    return results


def select_diverse_items(items: List[Dict], max_count: int = 6) -> List[Dict]:
    """Select items with type diversity."""
    by_type = defaultdict(list)
    for item in items:
        by_type[item.get('_type', 'unknown')].append(item)

    selected = []
    types = list(by_type.keys())

    # Round-robin selection for diversity
    idx = 0
    while len(selected) < max_count and any(by_type.values()):
        t = types[idx % len(types)]
        if by_type[t]:
            selected.append(by_type[t].pop(0))
        idx += 1
        # Clean up empty types
        types = [t for t in types if by_type[t]]
        if not types:
            break

    return selected


def has_person_name(item: Dict, name: str) -> bool:
    """Check if item title/name contains the person's name."""
    text = (item.get('name', '') + ' ' + item.get('title', '')).lower()
    # Check for full name or last name
    name_lower = name.lower()
    last_name = name.split()[-1].lower() if name.split() else ''
    return name_lower in text or (last_name and last_name in text)


def generate_person_carousels(leading_lights: List[Dict], lookup: Dict) -> List[Dict]:
    """Generate carousels for each leading light."""
    carousels = []

    for person in leading_lights:
        name = person.get('name', '')
        slug = person.get('slug', slugify(name))
        specialties = person.get('specialty', [])
        company = person.get('company', '')

        # Find related items - search for full name first, then parts
        search_terms = [name]  # Full name first
        if len(name.split()) > 1:
            search_terms.extend([name.split()[0], name.split()[-1]])
        search_terms.extend(specialties)
        if company:
            search_terms.append(company)

        related = find_items_by_text(lookup, search_terms)
        related += find_items_by_tags(lookup, specialties)

        # Dedupe
        seen_ids = set()
        unique_related = []
        for item in related:
            if item['_id'] not in seen_ids:
                seen_ids.add(item['_id'])
                unique_related.append(item)

        if len(unique_related) < MIN_ITEMS_PER_CAROUSEL - 1:
            continue

        # Select hero - MUST mention this person's name
        hero = None
        # First: find items that actually mention this person
        person_items = [i for i in unique_related if has_person_name(i, name)]

        # Prefer talk > paper > resource among items mentioning the person
        for pref_type in ['talk', 'paper', 'resource']:
            for item in person_items:
                if item.get('_type') == pref_type:
                    hero = item
                    break
            if hero:
                break

        # Fallback to any item mentioning the person
        if not hero and person_items:
            hero = person_items[0]

        # Last resort: first item from related (but this is not ideal)
        if not hero and unique_related:
            hero = unique_related[0]

        if not hero:
            continue

        # Select cast (exclude hero)
        cast = [i for i in unique_related if i['_id'] != hero['_id']]
        cast = select_diverse_items(cast, MAX_ITEMS_PER_CAROUSEL - 1)

        if len(cast) < MIN_ITEMS_PER_CAROUSEL - 1:
            continue

        carousel = {
            "id": f"{slug}-universe",
            "template": "person",
            "name": f"{name}'s Universe",
            "description": person.get('bio', '')[:100] + '...' if person.get('bio') else f"The world of {name}",
            "hero": {
                "id": hero['_id'],
                "type": hero['_type'],
                "title": hero.get('name', hero.get('title', '')),
                "url": hero.get('url', '')
            },
            "items": [
                {"id": i['_id'], "type": i['_type'], "title": i.get('name', i.get('title', '')), "url": i.get('url', '')}
                for i in cast
            ],
            "seed": {"type": "person", "name": name, "company": company}
        }
        carousels.append(carousel)

    return carousels


def generate_journey_carousels(roadmaps: List[Dict], lookup: Dict) -> List[Dict]:
    """Generate carousels from learning roadmaps."""
    carousels = []

    for roadmap in roadmaps:
        name = roadmap.get('name', '')
        description = roadmap.get('description', '')
        resources = roadmap.get('resources', [])
        packages = roadmap.get('packages', [])

        if not resources:
            continue

        # Build items from roadmap resources
        items = []
        for res in resources:
            res_name = res.get('name', '')
            # Try to find in lookup
            found = find_items_by_text(lookup, [res_name])
            if found:
                items.append(found[0])
            else:
                # Create inline item
                items.append({
                    '_id': f"resource-{slugify(res_name)}",
                    '_type': 'resource',
                    'name': res_name,
                    'url': res.get('url', ''),
                    'description': res.get('why', '')
                })

        # Add packages
        for pkg in packages:
            pkg_name = pkg.get('name', '')
            found = find_items_by_text(lookup, [pkg_name], item_type='package')
            if found:
                items.append(found[0])

        if len(items) < MIN_ITEMS_PER_CAROUSEL:
            continue

        hero = items[0]
        cast = items[1:MAX_ITEMS_PER_CAROUSEL]

        carousel = {
            "id": slugify(name),
            "template": "journey",
            "name": name,
            "description": description,
            "hero": {
                "id": hero.get('_id', f"resource-{slugify(hero.get('name', ''))}"),
                "type": hero.get('_type', 'resource'),
                "title": hero.get('name', ''),
                "url": hero.get('url', '')
            },
            "items": [
                {"id": i.get('_id', ''), "type": i.get('_type', 'resource'), "title": i.get('name', ''), "url": i.get('url', '')}
                for i in cast
            ],
            "seed": {"type": "journey", "name": name}
        }
        carousels.append(carousel)

    return carousels


def generate_tool_carousels(packages: List[Dict], lookup: Dict) -> List[Dict]:
    """Generate carousels for popular tool categories."""
    carousels = []

    # Group packages by category
    by_category = defaultdict(list)
    for pkg in packages:
        category = pkg.get('category', 'Other')
        by_category[category].append(pkg)

    # Create carousel for categories with enough items
    for category, pkgs in by_category.items():
        if len(pkgs) < MIN_ITEMS_PER_CAROUSEL:
            continue

        # Sort by some quality metric (prefer ones with docs)
        pkgs.sort(key=lambda p: (
            1 if p.get('docs_url') else 0,
            1 if p.get('github_url') else 0,
            len(p.get('use_cases', []))
        ), reverse=True)

        hero_pkg = pkgs[0]
        cast_pkgs = pkgs[1:MAX_ITEMS_PER_CAROUSEL]

        # Find related non-package items
        category_keywords = category.lower().split()
        related = find_items_by_text(lookup, category_keywords)
        related = [r for r in related if r.get('_type') != 'package'][:3]

        carousel = {
            "id": f"tools-{slugify(category)}",
            "template": "tool",
            "name": f"{category} Toolkit",
            "description": f"Essential tools for {category.lower()}",
            "hero": {
                "id": f"package-{slugify(hero_pkg.get('name', ''))}",
                "type": "package",
                "title": hero_pkg.get('name', ''),
                "url": hero_pkg.get('url', hero_pkg.get('github_url', ''))
            },
            "items": [
                {"id": f"package-{slugify(p.get('name', ''))}", "type": "package", "title": p.get('name', ''), "url": p.get('url', p.get('github_url', ''))}
                for p in cast_pkgs
            ] + [
                {"id": r['_id'], "type": r['_type'], "title": r.get('name', r.get('title', '')), "url": r.get('url', '')}
                for r in related
            ],
            "seed": {"type": "tool", "category": category}
        }
        carousels.append(carousel)

    return carousels[:30]  # Limit to top 30 categories


def generate_method_carousels(papers: List[Dict], lookup: Dict) -> List[Dict]:
    """Generate carousels for high-citation method papers."""
    carousels = []

    # Common words to filter out from title search
    STOP_WORDS = {'the', 'a', 'an', 'of', 'for', 'and', 'or', 'in', 'on', 'to', 'with', 'by', 'from', 'is', 'are', 'as', 'at'}

    # Filter high-citation papers
    high_citation = [
        p for p in papers
        if (p.get('citations') or 0) >= MIN_CITATION_FOR_METHOD
    ]

    # Sort by citations and dedupe by title
    high_citation.sort(key=lambda p: p.get('citations') or 0, reverse=True)
    seen_titles = set()
    unique_papers = []
    for p in high_citation:
        title_key = slugify(p.get('title', ''))[:30]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_papers.append(p)
    high_citation = unique_papers

    for paper in high_citation[:40]:  # Top 40
        title = paper.get('title', paper.get('name', ''))
        citations = paper.get('citations') or 0
        topic_tags = paper.get('topic_tags', [])

        # Use topic/subtopic info if available
        topic = paper.get('_topic', '')
        subtopic = paper.get('_subtopic', '')

        # Build keywords: filter stop words, use significant title words + tags + topic info
        title_words = [w for w in title.split()[:8] if w.lower() not in STOP_WORDS]
        keywords = title_words + topic_tags + [topic, subtopic]
        keywords = [k for k in keywords if k and k not in ['method-tag', 'domain-tag', 'application-tag']]

        # Find related items with stricter matching (require 2+ keyword matches)
        related = find_items_by_text(lookup, keywords, min_matches=2)
        related = [r for r in related if r.get('_id') != f"paper-{slugify(title)}"]

        # Add by tags
        if topic_tags:
            tag_matches = find_items_by_tags(lookup, topic_tags)
            for tm in tag_matches:
                if tm not in related:
                    related.append(tm)

        related = select_diverse_items(related, MAX_ITEMS_PER_CAROUSEL - 1)

        if len(related) < MIN_ITEMS_PER_CAROUSEL - 1:
            continue

        # Create catchy name (avoid double "The")
        short_title = ' '.join(title.split()[:6])
        if len(title.split()) > 6:
            short_title += '...'
        prefix = "" if short_title.lower().startswith("the ") else "The "

        carousel = {
            "id": f"method-{slugify(title)[:40]}",
            "template": "method",
            "name": f"{prefix}{short_title} Legacy",
            "description": f"A foundational paper with {citations:,}+ citations and its ecosystem",
            "hero": {
                "id": f"paper-{slugify(title)}",
                "type": "paper",
                "title": title,
                "citations": citations
            },
            "items": [
                {"id": r['_id'], "type": r['_type'], "title": r.get('name', r.get('title', '')), "url": r.get('url', '')}
                for r in related
            ],
            "seed": {"type": "method", "paper": title}
        }
        carousels.append(carousel)

    return carousels


def load_existing_manual_carousels() -> List[Dict]:
    """Load existing manually curated carousels (only those without generated flag)."""
    existing = load_json("narrative_carousels.json")
    if existing and 'carousels' in existing:
        # Only keep manually created carousels (identified by specific IDs or lack of generated flag)
        manual_ids = {
            'susan-athey-universe', 'bus-engine-paper', 'how-uber-does-pricing',
            'peeking-problem', 'econml-ecosystem', 'netflix-prize', 'ols-to-causal-forests',
            'credibility-revolution', 'cold-start-problem', 'hal-varian-playbook'
        }
        return [c for c in existing['carousels'] if c.get('id') in manual_ids]
    return []


def merge_carousels(manual: List[Dict], generated: List[Dict]) -> List[Dict]:
    """Merge manual and generated carousels, preferring manual."""
    manual_ids = {c['id'] for c in manual}

    # Add generated carousels that don't conflict
    merged = list(manual)
    for carousel in generated:
        if carousel['id'] not in manual_ids:
            merged.append(carousel)

    return merged


def main():
    print("Loading data sources...")

    # Load all data
    all_data = {
        'packages': load_json("packages.json") or [],
        'resources': load_json("resources.json") or [],
        'talks': load_json("talks.json") or [],
        'datasets': load_json("datasets.json") or [],
        'books': load_json("books.json") or [],
        'papers_flat': load_json("papers_flat.json") or [],
    }

    leading_lights = load_json("leading_lights.json") or []
    roadmaps = load_json("roadmaps.json") or []

    # Papers from nested structure
    papers_nested = load_json("papers.json")
    if papers_nested and 'topics' in papers_nested:
        for topic in papers_nested['topics']:
            for subtopic in topic.get('subtopics', []):
                for paper in subtopic.get('papers', []):
                    paper['_topic'] = topic.get('name', '')
                    paper['_subtopic'] = subtopic.get('name', '')
                    all_data['papers_flat'].append(paper)

    print(f"Loaded: {len(all_data['packages'])} packages, {len(all_data['resources'])} resources")
    print(f"        {len(all_data['talks'])} talks, {len(all_data['papers_flat'])} papers")
    print(f"        {len(leading_lights)} leading lights, {len(roadmaps)} roadmaps")

    # Build lookup
    print("Building item lookup...")
    lookup = build_item_lookup(all_data)
    print(f"Indexed {len(lookup)} items")

    # Generate carousels
    print("\nGenerating carousels...")

    person_carousels = generate_person_carousels(leading_lights, lookup)
    print(f"  PERSON carousels: {len(person_carousels)}")

    journey_carousels = generate_journey_carousels(roadmaps, lookup)
    print(f"  JOURNEY carousels: {len(journey_carousels)}")

    tool_carousels = generate_tool_carousels(all_data['packages'], lookup)
    print(f"  TOOL carousels: {len(tool_carousels)}")

    method_carousels = generate_method_carousels(all_data['papers_flat'], lookup)
    print(f"  METHOD carousels: {len(method_carousels)}")

    # Combine all generated
    all_generated = person_carousels + journey_carousels + tool_carousels + method_carousels
    print(f"\nTotal generated: {len(all_generated)}")

    # Load and merge with manual carousels
    print("\nMerging with existing manual carousels...")
    manual_carousels = load_existing_manual_carousels()
    print(f"Existing manual carousels: {len(manual_carousels)}")

    final_carousels = merge_carousels(manual_carousels, all_generated)
    print(f"Final carousel count: {len(final_carousels)}")

    # Output
    output = {
        "version": "2.0",
        "generated_at": "2024-12-31",
        "description": "Narrative-driven carousels for Netflix-style discovery",
        "stats": {
            "total": len(final_carousels),
            "manual": len(manual_carousels),
            "generated": len(all_generated),
            "by_template": {
                "person": len([c for c in final_carousels if c.get('template') == 'person']),
                "method": len([c for c in final_carousels if c.get('template') == 'method']),
                "tool": len([c for c in final_carousels if c.get('template') == 'tool']),
                "journey": len([c for c in final_carousels if c.get('template') == 'journey']),
                "problem": len([c for c in final_carousels if c.get('template') == 'problem']),
                "dataset": len([c for c in final_carousels if c.get('template') == 'dataset']),
                "era": len([c for c in final_carousels if c.get('template') == 'era']),
                "company": len([c for c in final_carousels if c.get('template') == 'company']),
            }
        },
        "carousels": final_carousels
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(final_carousels)} carousels to {OUTPUT_FILE}")
    print("\nBy template:")
    for template, count in output['stats']['by_template'].items():
        if count > 0:
            print(f"  {template}: {count}")


if __name__ == "__main__":
    main()
