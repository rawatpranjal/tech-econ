#!/usr/bin/env python3
"""
Add macro_category and subtopic fields to talks.json based on existing category.
Maps 41 categories to 8 macro categories.

Usage:
    python3 scripts/add_macro_categories.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Category to macro_category + subtopic mapping
# Format: "original category": ("macro_category", "subtopic")
CATEGORY_MAPPING = {
    # Causal & Experimentation
    "Causal Inference & ML": ("Causal & Experimentation", "Causal Inference"),
    "Experimentation & Scaling": ("Causal & Experimentation", "Experimentation"),
    "AB Testing": ("Causal & Experimentation", "A/B Testing"),
    "Experimentation": ("Causal & Experimentation", "Experimentation"),
    "Bayesian Statistics": ("Causal & Experimentation", "Bayesian Methods"),
    "Applied Statistics": ("Causal & Experimentation", "Applied Statistics"),
    "Statistical Learning": ("Causal & Experimentation", "Statistical Learning"),

    # Platforms & Markets
    "Platform Economics": ("Platforms & Markets", "Platform Economics"),
    "Strategy & Digital Platforms": ("Platforms & Markets", "Platform Strategy"),
    "Market Design & Auctions": ("Platforms & Markets", "Market Design"),
    "Antitrust & Competition": ("Platforms & Markets", "Antitrust"),

    # AI & Technology
    "AI & Labor": ("AI & Technology", "AI & Labor"),
    "AI Economics & Labor": ("AI & Technology", "AI & Labor"),
    "Machine Learning": ("AI & Technology", "Machine Learning"),
    "MLOps": ("AI & Technology", "MLOps"),
    "Recommendation Systems": ("AI & Technology", "Recommendations"),

    # Industry Economics
    "Tech Economics": ("Industry Economics", "Tech Industry"),
    "Gig Economy": ("Industry Economics", "Gig Economy"),
    "Transportation Economics & Technology": ("Industry Economics", "Transportation"),
    "Real Estate Economics": ("Industry Economics", "Real Estate"),
    "Healthcare Economics & Health-Tech": ("Industry Economics", "Healthcare"),
    "Insurance & Actuarial": ("Industry Economics", "Insurance"),
    "Energy Economics": ("Industry Economics", "Energy"),
    "Energy & Utilities Economics": ("Industry Economics", "Energy"),
    "Defense Economics": ("Industry Economics", "Defense"),
    "Defense Technology": ("Industry Economics", "Defense"),
    "Cybersecurity Economics": ("Industry Economics", "Cybersecurity"),

    # Pricing & Marketing
    "Pricing & Behavioral": ("Pricing & Marketing", "Pricing Strategy"),
    "Pricing & Market Design": ("Pricing & Marketing", "Pricing Strategy"),
    "Marketing Science": ("Pricing & Marketing", "Marketing Science"),
    "MarTech & Customer Analytics": ("Pricing & Marketing", "Customer Analytics"),
    "Ad Tech & Advertising Economics": ("Pricing & Marketing", "Ad Tech"),
    "Growth & Retention": ("Pricing & Marketing", "Growth"),

    # Labor & Careers
    "Labor Economics": ("Labor & Careers", "Labor Economics"),
    "Applied Economics": ("Labor & Careers", "Applied Economics"),
    "Tech Strategy": ("Labor & Careers", "Tech Strategy"),

    # Operations
    "Operations Research": ("Operations", "Operations Research"),
    "Forecasting": ("Operations", "Forecasting"),

    # Foundational
    "Monographs": ("Foundational", "Classic Papers"),
    "Nobel Lectures": ("Foundational", "Nobel Lectures"),
    "Sports Analytics": ("Foundational", "Sports Analytics"),
}


def main():
    filepath = DATA_DIR / "talks.json"
    print(f"Processing {filepath}...")

    with open(filepath) as f:
        talks = json.load(f)

    updated = 0
    unmapped = set()

    for talk in talks:
        category = talk.get("category", "")

        if category in CATEGORY_MAPPING:
            macro, subtopic = CATEGORY_MAPPING[category]
            talk["macro_category"] = macro
            talk["subtopic"] = subtopic
            updated += 1
        else:
            unmapped.add(category)
            # Default fallback
            talk["macro_category"] = "Other"
            talk["subtopic"] = category

    with open(filepath, "w") as f:
        json.dump(talks, f, indent=2)

    print(f"Updated {updated} talks")
    if unmapped:
        print(f"Unmapped categories: {unmapped}")


if __name__ == "__main__":
    main()
