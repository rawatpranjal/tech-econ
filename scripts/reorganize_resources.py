#!/usr/bin/env python3
"""
Reorganize resources.json:
- Consolidate categories (62 → ~35)
- Normalize types (80 → 10)
- Add macro_category field for filtering
- Backfill missing domain values
"""

import json
from pathlib import Path

# Category consolidation: map old → new (only merge true duplicates)
CATEGORY_MAPPING = {
    # Causal Inference consolidation
    "Causal Inference & ML": "Causal Inference",
    "Causal ML": "Causal Inference",

    # Experimentation consolidation
    "AB Testing": "A/B Testing",
    "A/B Testing Fundamentals": "A/B Testing",

    # ML consolidation
    "Fundamentals": "Machine Learning",

    # Bayesian consolidation
    "Probability & Inference": "Bayesian Methods",

    # Programming consolidation
    "Python": "Programming",
    "SQL": "Programming",
    "Software Engineering": "Programming",

    # Fix miscategorized entries (type used as category)
    "Blog": "Frameworks & Strategy",
    "Course": "Machine Learning",
    "Online Guide": "Frameworks & Strategy",
    "Academic Course": "Machine Learning",
    "Academic Program": "Machine Learning",
    "Professional Training": "Machine Learning",
    "Research Archive": "Computational Economics",
    "Research Institute": "Computational Economics",
    "Think Tank": "Computational Economics",

    # Industry consolidation
    "Industry Standards": "Operations Research",
}

# Type normalization: map old → new (80 → 10)
TYPE_MAPPING = {
    # Blog family
    "Blog": "Blog",
    "Blog Post": "Blog",
    "Blog Series": "Blog",
    "Engineering Blog": "Blog",
    "Company Blog": "Blog",
    "Research Blog": "Blog",
    "Tutorial Blog": "Blog",
    "Blog + Book": "Blog",
    "blog": "Blog",

    # Article family
    "Article": "Article",
    "Essay": "Article",
    "Essays": "Article",
    "Essay Series": "Article",
    "Paper": "Article",
    "Analysis": "Article",
    "Report": "Article",
    "Chapter": "Article",
    "Notes": "Article",
    "Case Study": "Article",

    # Course family
    "Course": "Course",
    "course": "Course",
    "Online Course": "Course",
    "Video Course": "Course",
    "Interactive Course": "Course",
    "Course Materials": "Course",
    "Lectures": "Course",
    "Course + Practice": "Course",
    "Course Aggregator": "Course",
    "training": "Course",
    "program": "Course",
    "Workshop Materials": "Course",
    "Workshop Tutorial": "Course",
    "Lecture Notes": "Course",
    "Course Notes": "Course",
    "Academic Course": "Course",

    # Tutorial family
    "Tutorial": "Tutorial",
    "Tutorial Guide": "Tutorial",
    "Tutorial Repository": "Tutorial",
    "Interactive Tutorial": "Tutorial",
    "Video Tutorial": "Tutorial",

    # Book family
    "Book": "Book",
    "Online Book": "Book",
    "Book + Lectures": "Book",

    # Video family
    "Video": "Video",
    "Video Series": "Video",
    "Video Lecture": "Video",

    # Podcast family
    "Podcast": "Podcast",
    "Interview": "Podcast",
    "Newsletter + Podcast": "Podcast",

    # Newsletter family
    "Newsletter": "Newsletter",
    "Substack": "Newsletter",

    # Guide family
    "Guide": "Guide",
    "Documentation": "Guide",
    "Docs": "Guide",
    "Resource Guide": "Guide",
    "Study Guide": "Guide",
    "Resource Hub": "Guide",
    "Curated List": "Guide",
    "Knowledge Base": "Guide",
    "Meta Resource": "Guide",
    "online-guide": "Guide",
    "Resource": "Guide",

    # Tool family
    "Tool": "Tool",
    "Framework": "Tool",
    "Interactive": "Tool",
    "Interactive Tools": "Tool",
    "Platform": "Tool",
    "Package": "Tool",
    "Dataset": "Tool",
    "Repository": "Tool",
    "Product Page": "Tool",
    "Academic": "Tool",
    "Research Portal": "Tool",
    "Research Center": "Tool",
    "Research Organization": "Tool",
    "research-institute": "Tool",
    "research-program": "Tool",
    "archive": "Tool",
    "standards-body": "Tool",
    "Practice Problems": "Tool",
    "Problem Set": "Tool",
}

# Macro category mapping: category → macro_category
MACRO_CATEGORY_MAPPING = {
    # Causal Methods
    "Causal Inference": "Causal Methods",
    "Causal Inference & ML": "Causal Methods",
    "Causal ML": "Causal Methods",
    "Difference-in-Differences": "Causal Methods",
    "IV & RDD": "Causal Methods",
    "Synthetic Control": "Causal Methods",
    "Econometrics": "Causal Methods",

    # Experimentation
    "A/B Testing": "Experimentation",
    "AB Testing": "Experimentation",
    "A/B Testing Fundamentals": "Experimentation",
    "Variance Reduction": "Experimentation",
    "Sequential Testing": "Experimentation",
    "Interference & Switchback": "Experimentation",
    "Bandits & Adaptive": "Experimentation",

    # Machine Learning
    "Machine Learning": "Machine Learning",
    "Fundamentals": "Machine Learning",
    "Deep Learning": "Machine Learning",
    "Gradient Boosting": "Machine Learning",
    "Search & Ranking": "Machine Learning",
    "Recommender Systems": "Machine Learning",
    "LLMs & Agents": "Machine Learning",

    # Bayesian & Probability
    "Bayesian Methods": "Bayesian & Probability",
    "Probability & Inference": "Bayesian & Probability",

    # Platform & Markets
    "Platform Economics": "Platform & Markets",
    "Marketplace Economics": "Platform & Markets",
    "Market Design & Matching": "Platform & Markets",
    "Auction Theory": "Platform & Markets",

    # Marketing & Growth
    "Marketing Science": "Marketing & Growth",
    "Ads & Attribution": "Marketing & Growth",
    "MarTech & Customer Analytics": "Marketing & Growth",
    "Growth & Retention": "Marketing & Growth",
    "Pricing & Revenue": "Marketing & Growth",
    "Advertising & Attention": "Marketing & Growth",

    # Operations Research
    "Operations Research": "Operations Research",
    "Linear Programming": "Operations Research",
    "Convex Optimization": "Operations Research",
    "Routing & Logistics": "Operations Research",

    # Time Series
    "Classical Methods": "Time Series",
    "Specialized Methods": "Time Series",
    "Production Systems": "Time Series",

    # Programming
    "Programming": "Programming",
    "Python": "Programming",
    "SQL": "Programming",
    "Software Engineering": "Programming",

    # Strategy
    "Frameworks & Strategy": "Strategy",
    "Tech Strategy": "Strategy",
    "Case Studies": "Strategy",
    "Metrics & Measurement": "Strategy",
    "Trust & Safety": "Strategy",

    # Industry Economics
    "Insurance & Actuarial": "Industry Economics",
    "Healthcare Economics & Health-Tech": "Industry Economics",
    "Transportation Economics & Technology": "Industry Economics",
    "Energy & Utilities Economics": "Industry Economics",
    "Sports Analytics": "Industry Economics",
    "Computational Economics": "Industry Economics",
    "Applied Economics": "Industry Economics",
    "Quantitative Finance": "Industry Economics",
}

# Domain backfill: category → domain (for entries missing domain)
DOMAIN_BACKFILL = {
    "Causal Inference": "Causal Inference",
    "Causal Inference & ML": "Causal Inference",
    "Causal ML": "Causal Inference",
    "Difference-in-Differences": "Causal Inference",
    "IV & RDD": "Causal Inference",
    "Synthetic Control": "Causal Inference",
    "Econometrics": "Causal Inference",

    "A/B Testing": "Experimentation",
    "AB Testing": "Experimentation",
    "A/B Testing Fundamentals": "Experimentation",
    "Variance Reduction": "Experimentation",
    "Sequential Testing": "Experimentation",
    "Interference & Switchback": "Experimentation",
    "Bandits & Adaptive": "Experimentation",

    "Machine Learning": "Machine Learning",
    "Fundamentals": "Machine Learning",
    "Deep Learning": "Machine Learning",
    "Gradient Boosting": "Machine Learning",
    "Search & Ranking": "Machine Learning",
    "Recommender Systems": "Machine Learning",
    "LLMs & Agents": "Machine Learning",

    "Bayesian Methods": "Statistics",
    "Probability & Inference": "Statistics",

    "Platform Economics": "Platform Economics",
    "Marketplace Economics": "Platform Economics",
    "Market Design & Matching": "Platform Economics",
    "Auction Theory": "Platform Economics",

    "Marketing Science": "Marketing",
    "Ads & Attribution": "Marketing",
    "MarTech & Customer Analytics": "Marketing",
    "Growth & Retention": "Marketing",
    "Pricing & Revenue": "Marketing",
    "Advertising & Attention": "Marketing",

    "Operations Research": "Optimization",
    "Linear Programming": "Optimization",
    "Convex Optimization": "Optimization",
    "Routing & Logistics": "Optimization",

    "Classical Methods": "Forecasting & Time Series",
    "Specialized Methods": "Forecasting & Time Series",
    "Production Systems": "Forecasting & Time Series",

    "Programming": "Programming",
    "Python": "Programming",
    "SQL": "Programming",
    "Software Engineering": "Programming",

    "Frameworks & Strategy": "Product Sense",
    "Tech Strategy": "Product Sense",
    "Case Studies": "Product Sense",
    "Metrics & Measurement": "Product Sense",
    "Trust & Safety": "Product Sense",

    "Insurance & Actuarial": "Domain Applications",
    "Healthcare Economics & Health-Tech": "Domain Applications",
    "Transportation Economics & Technology": "Domain Applications",
    "Energy & Utilities Economics": "Domain Applications",
    "Sports Analytics": "Domain Applications",
    "Computational Economics": "Economics",
    "Applied Economics": "Economics",
    "Quantitative Finance": "Economics",
}


def transform_resource(resource):
    """Apply all transformations to a single resource."""
    # 1. Category consolidation
    old_category = resource.get("category", "")
    new_category = CATEGORY_MAPPING.get(old_category, old_category)
    resource["category"] = new_category

    # 2. Type normalization
    old_type = resource.get("type", "")
    new_type = TYPE_MAPPING.get(old_type, old_type)
    if new_type == old_type and old_type:
        # If not in mapping, try title case
        new_type = old_type.title()
    resource["type"] = new_type

    # 3. Add macro_category
    # Try new category first, then old category
    macro = MACRO_CATEGORY_MAPPING.get(new_category) or MACRO_CATEGORY_MAPPING.get(old_category)
    if not macro:
        # Default based on patterns
        if "Economics" in old_category or "Finance" in old_category:
            macro = "Industry Economics"
        else:
            macro = "Strategy"  # Default fallback
    resource["macro_category"] = macro

    # 4. Backfill domain if missing
    if not resource.get("domain"):
        domain = DOMAIN_BACKFILL.get(old_category) or DOMAIN_BACKFILL.get(new_category)
        if domain:
            resource["domain"] = domain
        else:
            # Default based on macro category
            macro_to_domain = {
                "Causal Methods": "Causal Inference",
                "Experimentation": "Experimentation",
                "Machine Learning": "Machine Learning",
                "Bayesian & Probability": "Statistics",
                "Platform & Markets": "Platform Economics",
                "Marketing & Growth": "Marketing",
                "Operations Research": "Optimization",
                "Time Series": "Forecasting & Time Series",
                "Programming": "Programming",
                "Strategy": "Product Sense",
                "Industry Economics": "Domain Applications",
            }
            resource["domain"] = macro_to_domain.get(macro, "Domain Applications")

    # 5. Normalize difficulty/level
    difficulty = resource.get("difficulty", "")
    if difficulty:
        difficulty_lower = difficulty.lower()
        if "beginner" in difficulty_lower or "easy" in difficulty_lower:
            resource["difficulty"] = "beginner"
        elif "advanced" in difficulty_lower or "hard" in difficulty_lower:
            resource["difficulty"] = "advanced"
        elif "intermediate" in difficulty_lower or "medium" in difficulty_lower:
            resource["difficulty"] = "intermediate"

    return resource


def main():
    # Load resources
    data_path = Path(__file__).parent.parent / "data" / "resources.json"
    with open(data_path) as f:
        resources = json.load(f)

    print(f"Loaded {len(resources)} resources")

    # Collect stats before
    categories_before = set(r.get("category", "") for r in resources)
    types_before = set(r.get("type", "") for r in resources)
    missing_domain_before = sum(1 for r in resources if not r.get("domain"))

    print(f"\nBefore transformation:")
    print(f"  Categories: {len(categories_before)}")
    print(f"  Types: {len(types_before)}")
    print(f"  Missing domain: {missing_domain_before}")

    # Transform all resources
    transformed = [transform_resource(r) for r in resources]

    # Collect stats after
    categories_after = set(r.get("category", "") for r in transformed)
    types_after = set(r.get("type", "") for r in transformed)
    macro_categories = set(r.get("macro_category", "") for r in transformed)
    missing_domain_after = sum(1 for r in transformed if not r.get("domain"))

    print(f"\nAfter transformation:")
    print(f"  Categories: {len(categories_after)}")
    print(f"  Types: {len(types_after)}")
    print(f"  Macro categories: {len(macro_categories)}")
    print(f"  Missing domain: {missing_domain_after}")

    print(f"\n--- Categories ({len(categories_after)}) ---")
    for cat in sorted(categories_after):
        count = sum(1 for r in transformed if r.get("category") == cat)
        print(f"  {count:3d}  {cat}")

    print(f"\n--- Types ({len(types_after)}) ---")
    for t in sorted(types_after):
        count = sum(1 for r in transformed if r.get("type") == t)
        print(f"  {count:3d}  {t}")

    print(f"\n--- Macro Categories ({len(macro_categories)}) ---")
    for macro in sorted(macro_categories):
        count = sum(1 for r in transformed if r.get("macro_category") == macro)
        print(f"  {count:3d}  {macro}")

    # Save transformed resources
    with open(data_path, "w") as f:
        json.dump(transformed, f, indent=2)

    print(f"\nSaved transformed resources to {data_path}")


if __name__ == "__main__":
    main()
