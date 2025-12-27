#!/usr/bin/env python3
"""
Convert the econometrics-in-python README.md to a JSON database.
Parses markdown tables and extracts package information.
"""

import re
import json
import subprocess
import sys


def fetch_readme():
    """Fetch the raw README.md from GitHub using curl."""
    url = "https://raw.githubusercontent.com/rawatpranjal/econometrics-in-python/main/README.md"
    result = subprocess.run(
        ['curl', '-sL', url],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error fetching README: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_links(links_cell):
    """Extract Docs and GitHub URLs from a links cell like '[Docs](url) . [GitHub](url)'."""
    docs_url = None
    github_url = None

    # Find all markdown links
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', links_cell)
    for text, url in links:
        text_lower = text.lower()
        if 'doc' in text_lower or 'pypi' in text_lower:
            docs_url = url
        elif 'github' in text_lower or 'git' in text_lower:
            github_url = url
        elif docs_url is None:
            docs_url = url  # First link as fallback

    return docs_url, github_url


def parse_readme(content):
    """Parse the README content and extract package data."""
    packages = []
    current_category = None

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Detect category headers (## Category Name)
        if line.startswith('## '):
            category = line[3:].strip()
            # Skip non-package sections
            if category.lower() not in ['contributing', 'learning resources', 'license', 'table of contents']:
                current_category = category

        # Detect table rows (start with |)
        if line.startswith('|') and current_category:
            # Skip header row and separator row
            if '---' in line or 'Package' in line or 'Description' in line:
                i += 1
                continue

            # Parse table row
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty cells

            if len(cells) >= 3:
                # Extract package name (remove bold markers)
                name_raw = cells[0]
                name = re.sub(r'\*\*([^*]+)\*\*', r'\1', name_raw).strip()
                name = re.sub(r'\*([^*]+)\*', r'\1', name).strip()

                if not name or name.lower() in ['package', 'name']:
                    i += 1
                    continue

                description = cells[1].strip() if len(cells) > 1 else ""
                links_cell = cells[2] if len(cells) > 2 else ""
                install_cmd = cells[3] if len(cells) > 3 else ""

                # Clean install command
                install_cmd = re.sub(r'`([^`]+)`', r'\1', install_cmd).strip()

                # Parse links
                docs_url, github_url = parse_links(links_cell)

                # Use first available URL as primary
                primary_url = github_url or docs_url or f"https://pypi.org/project/{name}/"

                packages.append({
                    "name": name,
                    "description": description,
                    "category": current_category,
                    "docs_url": docs_url,
                    "github_url": github_url,
                    "url": primary_url,
                    "install": install_cmd
                })

        i += 1

    return packages


def main():
    print("Fetching README from GitHub...")
    content = fetch_readme()

    print("Parsing packages...")
    packages = parse_readme(content)

    # Remove duplicates by name
    seen = set()
    unique_packages = []
    for pkg in packages:
        if pkg['name'] not in seen:
            seen.add(pkg['name'])
            unique_packages.append(pkg)

    # Sort by category then name
    unique_packages.sort(key=lambda x: (x['category'], x['name']))

    # Save to data directory
    output_path = 'data/packages.json'
    with open(output_path, 'w') as f:
        json.dump(unique_packages, f, indent=2)

    print(f"Saved {len(unique_packages)} packages to {output_path}")

    # Print category summary
    categories = {}
    for pkg in unique_packages:
        cat = pkg['category']
        categories[cat] = categories.get(cat, 0) + 1

    print("\nPackages by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == '__main__':
    main()
