#!/usr/bin/env python3
"""
Add best_for field to datasets based on category and content.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Category to best_for mapping
CATEGORY_BEST_FOR = {
    "AI & LLM": "Learning LLM evaluation, chatbot quality assessment, and dialogue systems",
    "E-Commerce": "Practicing customer analytics, demand forecasting, and recommendation systems",
    "Recommendations": "Building and evaluating recommendation engines and collaborative filtering",
    "Search & Ranking": "Learning search ranking, click prediction, and information retrieval",
    "Ads & Marketing": "Understanding ad click prediction, marketing attribution, and campaign optimization",
    "Customer Analytics": "Analyzing customer behavior, segmentation, and lifetime value prediction",
    "Pricing & Revenue": "Learning dynamic pricing, revenue optimization, and price elasticity estimation",
    "Causal Inference": "Practicing causal inference methods like DiD, RDD, and propensity score matching",
    "A/B Testing": "Learning experimental design, hypothesis testing, and variance reduction techniques",
    "Time Series": "Practicing time series forecasting, trend analysis, and seasonality detection",
    "Finance": "Learning financial modeling, risk assessment, and portfolio optimization",
    "Healthcare": "Understanding healthcare analytics, patient outcomes, and clinical predictions",
    "Supply Chain": "Learning demand forecasting, inventory optimization, and logistics planning",
    "Ride-Hailing": "Analyzing marketplace dynamics, surge pricing, and driver-rider matching",
    "Gaming": "Understanding player behavior, engagement metrics, and in-game economics",
    "Social Networks": "Learning network analysis, community detection, and influence modeling",
    "Fraud Detection": "Practicing anomaly detection, fraud classification, and risk scoring",
    "Geospatial": "Learning location-based analytics, spatial modeling, and geo-experiments",
    "NLP & Text": "Practicing text classification, sentiment analysis, and topic modeling",
    "Computer Vision": "Learning image classification, object detection, and visual embeddings",
    "Multi-Armed Bandits": "Practicing bandit algorithms, exploration-exploitation, and adaptive experiments",
    "Reinforcement Learning": "Learning RL algorithms, policy optimization, and sequential decision making",
    "Synthetic Data": "Practicing causal inference and ML methods with known ground truth",
    "Tabular & General": "General machine learning practice with structured tabular data",
    "Benchmark": "Benchmarking ML models and comparing algorithm performance",
}

def add_best_for():
    """Add best_for field to datasets based on category."""
    datasets_file = DATA_DIR / "datasets.json"
    with open(datasets_file) as f:
        data = json.load(f)

    count = 0
    for item in data:
        if "best_for" not in item or not item["best_for"]:
            category = item.get("category", "")
            # Get best_for from category mapping, with fallback
            if category in CATEGORY_BEST_FOR:
                item["best_for"] = CATEGORY_BEST_FOR[category]
            else:
                # Generic fallback based on category name
                item["best_for"] = f"Learning {category.lower()} analytics and modeling"
            count += 1

    with open(datasets_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Added best_for to {count} datasets")
    return count


def find_short_descriptions():
    """Find datasets with short descriptions (< 50 chars)."""
    datasets_file = DATA_DIR / "datasets.json"
    with open(datasets_file) as f:
        data = json.load(f)

    short = []
    for item in data:
        desc = item.get("description", "")
        if len(desc) < 50:
            short.append({
                "name": item.get("name"),
                "description": desc,
                "len": len(desc)
            })

    print(f"\nDatasets with short descriptions (<50 chars): {len(short)}")
    for s in short[:10]:
        print(f"  - {s['name']}: '{s['description']}' ({s['len']} chars)")
    if len(short) > 10:
        print(f"  ... and {len(short) - 10} more")

    return short


if __name__ == "__main__":
    add_best_for()
    find_short_descriptions()
