"""
Formatter Module
================
Format verified data for tech-econ.org community.json
"""

from typing import List, Dict
import json


def build_description(person: Dict) -> str:
    """Build rich description from person data."""
    parts = []

    # PhD info
    if person.get('phd_institution'):
        phd_str = f"PhD {person['phd_institution']}"
        if person.get('phd_year'):
            phd_str += f" ({person['phd_year']})"
        parts.append(phd_str)

    # Current role
    if person.get('current_title') and person.get('current_company'):
        parts.append(f"{person['current_title']} at {person['current_company']}")
    elif person.get('current_title'):
        parts.append(person['current_title'])

    # Career highlights
    if person.get('career_path'):
        parts.append(f"Career: {person['career_path']}")

    # What they're known for
    if person.get('known_for'):
        parts.append(person['known_for'])

    return ". ".join(parts) + "." if parts else ""


def format_for_site(verified_data: List[Dict]) -> List[Dict]:
    """Format for tech-econ.org community.json."""
    output = []

    for person in verified_data:
        # Determine best URL
        url = (
            person.get('personal_site') or
            person.get('linkedin_url') or
            ''
        )

        # Determine type based on role
        title = person.get('current_title', '')
        if 'chief' in title.lower():
            person_type = 'Chief Economist'
        elif 'professor' in title.lower():
            person_type = 'Professor & Advisor'
        elif 'vp' in title.lower() or 'vice president' in title.lower():
            person_type = 'VP Economics'
        elif 'director' in title.lower():
            person_type = 'Director'
        elif 'head' in title.lower():
            person_type = 'Head Economist'
        else:
            person_type = title or 'Tech Economist'

        entry = {
            "name": person['name'],
            "description": build_description(person),
            "category": "Leading Lights",
            "url": url,
            "type": person_type,
            "location": person.get('location', ''),
            "best_for": person.get('known_for', '')
        }
        output.append(entry)

    return output


def merge_with_existing(new_entries: List[Dict], existing_path: str) -> List[Dict]:
    """Merge new entries with existing community.json."""
    with open(existing_path, 'r') as f:
        existing = json.load(f)

    # Get existing Leading Lights names
    existing_names = {
        entry['name']
        for entry in existing
        if entry.get('category') == 'Leading Lights'
    }

    # Filter out duplicates
    new_unique = [
        entry for entry in new_entries
        if entry['name'] not in existing_names
    ]

    # Add new entries
    result = existing + new_unique

    return result


def save_for_site(entries: List[Dict], output_path: str = "data/for_site.json"):
    """Save formatted entries to JSON."""
    with open(output_path, 'w') as f:
        json.dump(entries, f, indent=2)
    print(f"Saved {len(entries)} entries to {output_path}")


def preview_entries(entries: List[Dict], n: int = 5):
    """Preview formatted entries."""
    print(f"\n=== Preview of {min(n, len(entries))} entries ===\n")
    for entry in entries[:n]:
        print(f"Name: {entry['name']}")
        print(f"Type: {entry['type']}")
        print(f"Description: {entry['description'][:100]}...")
        print(f"URL: {entry['url']}")
        print("-" * 50)
