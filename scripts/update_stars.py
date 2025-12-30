#!/usr/bin/env python3
"""
Update GitHub star counts for packages in packages.json.
"""

import json
import os
import re
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
PACKAGES_FILE = DATA_DIR / "packages.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "tech-econ-stars-updater",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


def extract_repo_info(url):
    """Extract owner and repo name from GitHub URL."""
    if not url:
        return None

    # Match github.com/owner/repo patterns
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if match:
        owner = match.group(1)
        repo = match.group(2).rstrip(".git")
        return owner, repo
    return None


def get_star_count(owner, repo):
    """Fetch star count from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get("stargazers_count")
        elif response.status_code == 404:
            print(f"  Repo not found: {owner}/{repo}")
            return None
        elif response.status_code == 403:
            # Rate limited
            reset_time = response.headers.get("X-RateLimit-Reset")
            print(f"  Rate limited. Reset at: {reset_time}")
            return None
        else:
            print(f"  Error {response.status_code} for {owner}/{repo}")
            return None
    except requests.RequestException as e:
        print(f"  Request error for {owner}/{repo}: {e}")
        return None


def main():
    # Load packages
    with open(PACKAGES_FILE) as f:
        packages = json.load(f)

    print(f"Checking {len(packages)} packages for GitHub star counts...")

    updated_count = 0
    rate_limit_remaining = 60  # Default for unauthenticated

    for i, pkg in enumerate(packages):
        github_url = pkg.get("github_url") or pkg.get("url", "")

        if "github.com" not in github_url:
            continue

        repo_info = extract_repo_info(github_url)
        if not repo_info:
            continue

        owner, repo = repo_info

        # Get star count
        stars = get_star_count(owner, repo)

        if stars is not None:
            old_stars = pkg.get("stars")
            if old_stars != stars:
                pkg["stars"] = stars
                updated_count += 1
                print(f"  {pkg['name']}: {old_stars} -> {stars} stars")

        # Rate limiting - be nice to GitHub API
        if (i + 1) % 10 == 0:
            time.sleep(1)

    # Save updated packages
    with open(PACKAGES_FILE, "w") as f:
        json.dump(packages, f, indent=2)
        f.write("\n")

    print(f"\nUpdated {updated_count} packages with new star counts.")


if __name__ == "__main__":
    main()
