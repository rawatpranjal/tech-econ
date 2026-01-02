#!/usr/bin/env python3
"""Add sector-based subtopics to industry blogs in resources.json."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Manual mapping for blogs (name pattern -> sector)
SECTOR_MAPPING = {
    # Marketplaces / Rideshare / Gig Economy
    "Uber": "Marketplaces",
    "Lyft": "Marketplaces",
    "DoorDash": "Marketplaces",
    "Airbnb": "Marketplaces",
    "Instacart": "Marketplaces",
    "Etsy": "Marketplaces",
    "eBay": "Marketplaces",
    "Fiverr": "Marketplaces",
    "Upwork": "Marketplaces",
    "Thumbtack": "Marketplaces",
    "OLX": "Marketplaces",
    "Afi Labs": "Marketplaces",  # Ride-share dispatch
    "Simon Rothman": "Marketplaces",  # How to Build a Marketplace

    # Streaming / Entertainment
    "Netflix": "Streaming",
    "Spotify": "Streaming",

    # Social Media
    "Meta": "Social Media",
    "LinkedIn": "Social Media",
    "TikTok": "Social Media",
    "Eugene Wei": "Social Media",  # Status as a Service, TikTok analysis
    "Dean Eckles": "Social Media",  # Network experiments

    # E-commerce / Retail
    "Amazon": "E-commerce",
    "Walmart": "E-commerce",
    "Wayfair": "E-commerce",
    "Stitch Fix": "E-commerce",
    "Booking.com": "E-commerce",

    # AdTech / Marketing Tech
    "Google": "AdTech",
    "Adjust": "AdTech",
    "Remerge": "AdTech",
    "Branch": "AdTech",
    "Lumen": "AdTech",
    "Mobile Dev Memo": "AdTech",
    "Kevin Simler": "AdTech",  # Ads Don't Work That Way
    "Neil Hoyne": "AdTech",  # CLV marketing
    "Koen Pauwels": "AdTech",  # Marketing metrics
    "Kevin Hillstrom": "AdTech",  # MineThatData
    "Recast": "AdTech",  # MMM
    "Haus": "AdTech",  # Geo experimentation
    "Juan Orduz": "AdTech",  # Bayesian marketing

    # Fintech
    "Stripe": "Fintech",

    # Creator Economy
    "Li Jin": "Creator Economy",

    # Operations Research
    "Erwin Kalvelagen": "Operations Research",
    "Paul Rubin": "Operations Research",
    "Alain Chabrier": "Operations Research",
    "Austin Buchanan": "Operations Research",
    "Franco Peschiera": "Operations Research",
    "Kevin Gue": "Operations Research",
    "Laura Albert": "Operations Research",
    "Michael Trick": "Operations Research",
    "Nathan Brixius": "Operations Research",
    "Richard Oberdieck": "Operations Research",
    "Ryan O'Neil": "Operations Research",
    "SolverMax": "Operations Research",
    "Stephen Maher": "Operations Research",
    "Tallys Yunes": "Operations Research",
    "Timefold": "Operations Research",
    "Nextmv": "Operations Research",
    "Chronos": "Operations Research",  # AWS forecasting
    "Mario Filho": "Operations Research",  # Forecastegy

    # VC & Strategy
    "Bill Gurley": "VC & Strategy",
    "a16z": "VC & Strategy",
    "Stratechery": "VC & Strategy",
    "Sangeet Choudary": "VC & Strategy",  # Platform Scale
    "Teresa Torres": "VC & Strategy",  # Product strategy
    "Byron Sharp": "VC & Strategy",  # How Brands Grow

    # Research & Academia
    "PyMC": "Research & Academia",
    "Freakonometrics": "Research & Academia",
    "Evan Miller": "Research & Academia",
    "Matteo Courthoud": "Research & Academia",
    "Adam Kelleher": "Research & Academia",
    "Dario Sansone": "Research & Academia",
    "Anton Korinek": "Research & Academia",
    "Aswath Damodaran": "Research & Academia",
    "Energy Institute": "Research & Academia",
    "Lukas Vermeer": "Research & Academia",
    "Microsoft Research": "Research & Academia",
    "CausalImpact": "Research & Academia",
}


def get_sector(blog):
    """Determine sector for an industry blog."""
    name = blog.get("name", "")
    desc = blog.get("description", "").lower()

    # Check manual mapping first (by name pattern)
    for pattern, sector in SECTOR_MAPPING.items():
        if pattern.lower() in name.lower():
            return sector

    # Fallback based on description keywords
    if any(kw in desc for kw in ["marketplace", "rideshare", "delivery", "gig"]):
        return "Marketplaces"
    elif any(kw in desc for kw in ["streaming", "recommendation", "netflix", "spotify"]):
        return "Streaming"
    elif any(kw in desc for kw in ["social", "network effect", "viral"]):
        return "Social Media"
    elif any(kw in desc for kw in ["retail", "ecommerce", "e-commerce", "shopping"]):
        return "E-commerce"
    elif any(kw in desc for kw in ["ad ", "ads ", "advertising", "attribution", "mmm", "media mix"]):
        return "AdTech"
    elif any(kw in desc for kw in ["payment", "fintech", "banking"]):
        return "Fintech"
    elif any(kw in desc for kw in ["creator", "passion economy"]):
        return "Creator Economy"
    elif any(kw in desc for kw in ["optimization", "solver", "cplex", "gurobi", "or ", "operations research", "scheduling"]):
        return "Operations Research"
    elif any(kw in desc for kw in ["venture", "strategy", "platform scale", "aggregation"]):
        return "VC & Strategy"
    else:
        return "Research & Academia"


def main():
    # Load resources data
    data_path = DATA_DIR / "resources.json"
    with open(data_path) as f:
        data = json.load(f)

    # Process blogs only
    updated = 0
    sector_counts = {}

    for item in data:
        if item.get("type") != "Blog":
            continue

        sector = get_sector(item)
        item["subtopic"] = sector
        updated += 1
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    # Save updated data
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {updated} industry blogs with sector subtopics\n")
    print("Sector distribution:")
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        print(f"  {sector}: {count}")


if __name__ == "__main__":
    main()
