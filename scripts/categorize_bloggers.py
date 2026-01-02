#!/usr/bin/env python3
"""Add subtopic categories to community.json bloggers for carousel organization."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Manual mapping for well-known bloggers (name -> subtopic)
BLOGGER_TOPICS = {
    # Causal Inference
    "Nick Huntington-Klein": "Causal Inference",
    "Paul Goldsmith-Pinkham": "Causal Inference",
    "Matheus Facure": "Causal Inference",
    "Matteo Courthoud": "Causal Inference",
    "Lucy D'Agostino McGowan": "Causal Inference",
    "Francis DiTraglia": "Causal Inference",
    "Andrew Heiss": "Causal Inference",
    "Ellie Murray": "Causal Inference",
    "Apoorva Lal": "Causal Inference",
    "Aleksander Molak": "Causal Inference",
    "Carlos Fernández-Loría": "Causal Inference",

    # Machine Learning & AI
    "Andrej Karpathy": "Machine Learning & AI",
    "Lilian Weng": "Machine Learning & AI",
    "Sebastian Raschka": "Machine Learning & AI",
    "Nathan Lambert": "Machine Learning & AI",
    "Christoph Molnar": "Machine Learning & AI",
    "Tor Lattimore": "Machine Learning & AI",

    # Experimentation & A/B Testing
    "Alex Deng": "Experimentation",
    "Sean J. Taylor": "Experimentation",
    "Emily Glassberg Sands": "Experimentation",
    "Yuzheng Sun (课代表立正)": "Experimentation",
    "MeasuringU": "Experimentation",

    # Economics & Research
    "Andrew Gelman": "Economics & Research",
    "Marc Bellemare": "Economics & Research",
    "Al Roth's Market Design Blog": "Economics & Research",
    "Marginal Revolution (Tyler Cowen)": "Economics & Research",
    "New Things Under the Sun (Matt Clancy)": "Economics & Research",
    "Jed Kolko": "Economics & Research",
    "Arpit Gupta": "Economics & Research",
    "Robert Kubinec": "Economics & Research",
    "David McKenzie": "Economics & Research",
    "James Brand": "Economics & Research",

    # Growth & Product
    "Lenny Rachitsky": "Growth & Product",
    "Elena Verna": "Growth & Product",
    "Casey Winters": "Growth & Product",
    "Adam Fishman": "Growth & Product",
    "Dan Hockenmaier": "Growth & Product",
    "Deepak Singh": "Growth & Product",

    # Platform Economics
    "Sangeet Paul Choudary": "Platform Economics",
    "Kevin Kwok": "Platform Economics",
    "Stratechery (Ben Thompson)": "Platform Economics",
    "Leo Saenger": "Platform Economics",

    # Data Science & Analytics
    "Eugene Yan": "Data Science & Analytics",
    "Emily Riederer": "Data Science & Analytics",
    "Michael Kaminsky": "Data Science & Analytics",
    "James LeDoux": "Data Science & Analytics",
    "Pranjal Rawat": "Data Science & Analytics",
    "Vincent Arel-Bundock": "Data Science & Analytics",
    "Thomas Vladeck": "Data Science & Analytics",
    "Ken Acquah": "Data Science & Analytics",
    "Massimiliano Costacurta": "Data Science & Analytics",
    "Michael Luca": "Data Science & Analytics",

    # Specialized
    "Ming Tommy Tang (Chatomics)": "Bioinformatics",
    "Mike Shields": "Advertising & Media",
}


def categorize_blogger(blog):
    """Determine subtopic for a blogger."""
    name = blog.get("name", "")

    # Check manual mapping first
    if name in BLOGGER_TOPICS:
        return BLOGGER_TOPICS[name]

    # Fallback based on topic_tags and description
    tags = " ".join(blog.get("topic_tags", [])).lower()
    desc = blog.get("description", "").lower()
    content = tags + " " + desc

    if any(kw in content for kw in ["causal", "treatment effect", "did ", "rct"]):
        return "Causal Inference"
    elif any(kw in content for kw in ["machine learning", "deep learning", "neural", "llm", "ai"]):
        return "Machine Learning & AI"
    elif any(kw in content for kw in ["experiment", "a/b test", "ab test", "randomized"]):
        return "Experimentation"
    elif any(kw in content for kw in ["growth", "product", "monetization", "pricing"]):
        return "Growth & Product"
    elif any(kw in content for kw in ["platform", "network effect", "marketplace"]):
        return "Platform Economics"
    elif any(kw in content for kw in ["econom", "market design", "policy"]):
        return "Economics & Research"
    else:
        return "Data Science & Analytics"


def main():
    # Load community data
    data_path = DATA_DIR / "community.json"
    with open(data_path) as f:
        data = json.load(f)

    # Process blogs
    updated = 0
    topic_counts = {}

    for item in data:
        if item.get("category") != "Blogs":
            continue

        subtopic = categorize_blogger(item)
        item["subtopic"] = subtopic
        updated += 1
        topic_counts[subtopic] = topic_counts.get(subtopic, 0) + 1

    # Save updated data
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {updated} bloggers with subtopics\n")
    print("Topic distribution:")
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"  {topic}: {count}")


if __name__ == "__main__":
    main()
