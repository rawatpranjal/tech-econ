#!/usr/bin/env python3
"""
Generate weekly highlight article using Claude API.
Picks a topic from data/papers.json and generates a deep-dive article.
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path

import anthropic
import yaml

# Paths
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
CONTENT_DIR = ROOT / "content" / "weekly-highlights"
HISTORY_FILE = DATA_DIR / "highlight-history.json"

# Load topic data
def load_topics():
    """Load topics from papers.json"""
    with open(DATA_DIR / "papers.json") as f:
        data = json.load(f)
    return data.get("topics", [])

def load_packages():
    """Load packages for reference"""
    with open(DATA_DIR / "packages.json") as f:
        return json.load(f)

def load_resources():
    """Load learning resources for reference"""
    with open(DATA_DIR / "resources.json") as f:
        return json.load(f)

def load_history():
    """Load generation history"""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"covered": [], "last_generated": None}

def save_history(history):
    """Save generation history"""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def select_topic(topics, history, override=None):
    """Select next topic to cover"""
    if override:
        # Find topic by id or name
        for topic in topics:
            if topic["id"] == override or topic["name"].lower() == override.lower():
                return topic

    # Get uncovered topics
    covered_ids = set(history.get("covered", []))
    uncovered = [t for t in topics if t["id"] not in covered_ids]

    # If all covered, reset and start over
    if not uncovered:
        history["covered"] = []
        uncovered = topics

    # Pick random uncovered topic
    return random.choice(uncovered)

def find_related_packages(topic, packages):
    """Find packages related to the topic"""
    keywords = topic["name"].lower().split() + topic.get("description", "").lower().split()
    related = []

    for pkg in packages:
        pkg_text = (pkg.get("name", "") + " " + pkg.get("description", "")).lower()
        if any(kw in pkg_text for kw in keywords if len(kw) > 3):
            related.append(pkg)

    return related[:5]

def find_related_resources(topic, resources):
    """Find learning resources related to the topic"""
    keywords = topic["name"].lower().split() + topic.get("description", "").lower().split()
    related = []

    for res in resources:
        res_text = (res.get("title", "") + " " + res.get("description", "")).lower()
        if any(kw in res_text for kw in keywords if len(kw) > 3):
            related.append(res)

    return related[:5]

def generate_article(topic, packages, resources):
    """Generate article using Claude API"""
    client = anthropic.Anthropic()

    # Build context from topic
    subtopics_text = ""
    for st in topic.get("subtopics", []):
        subtopics_text += f"\n### {st['name']}\n"
        subtopics_text += f"Application: {st.get('application', '')}\n"
        for paper in st.get("papers", [])[:2]:
            subtopics_text += f"- {paper['title']} ({paper['year']}): {paper.get('description', '')}\n"

    packages_text = "\n".join([f"- {p['name']}: {p.get('description', '')[:100]}" for p in packages])
    resources_text = "\n".join([f"- {r['title']}: {r.get('description', '')[:100]}" for r in resources])

    prompt = f"""You are writing a weekly deep-dive article for tech-econ.com, a resource site for tech economists and applied researchers.

Topic: {topic['name']}
Description: {topic.get('description', '')}

Key subtopics and papers:
{subtopics_text}

Related Python packages:
{packages_text}

Related learning resources:
{resources_text}

Write a practical, engaging article following this EXACT structure:

1. **The Problem** (1-2 paragraphs)
   - Why this topic matters for tech economists
   - Real business impact

2. **Common Approaches** (3-4 techniques)
   - Brief explanation of each approach
   - When to use each one
   - Include quotes from key researchers where relevant

3. **Try It Yourself** (Python code)
   - Working code example using a real library
   - Include pip install command
   - Add helpful comments
   - Show expected output

4. **Real-World Applications** (5-6 companies)
   - How specific tech companies use this
   - Be specific about their implementation
   - Link to their engineering blogs if possible

5. **Further Reading**
   - Essential Reading (2-3 papers/books)
   - Tools & Libraries (3-4 packages)
   - Courses (1-2 courses)
   - Key Researchers (2-3 people)
   - Datasets for Practice (2-3 datasets)

Format requirements:
- Use markdown with proper headings (##, ###)
- Include working hyperlinks where possible
- Code blocks should use ```python
- Keep it practical and actionable
- Target length: 1500-2000 words

Output ONLY the article content in markdown format, starting with the first section heading. Do not include frontmatter."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text

def create_markdown_file(topic, content):
    """Create markdown file with frontmatter"""
    today = datetime.now()
    slug = topic["id"]
    filename = f"{today.strftime('%Y-%m-%d')}-{slug}.md"

    frontmatter = {
        "title": topic["name"],
        "date": today.strftime("%Y-%m-%d"),
        "category": topic["name"],
        "description": topic.get("description", ""),
        "tags": [topic["name"]] + [st["name"] for st in topic.get("subtopics", [])[:3]],
        "draft": False
    }

    # Ensure content directory exists
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    filepath = CONTENT_DIR / filename
    with open(filepath, "w") as f:
        f.write("---\n")
        f.write(yaml.dump(frontmatter, default_flow_style=False))
        f.write("---\n\n")
        f.write(content)

    return filepath

def main():
    print("Loading data...")
    topics = load_topics()
    packages = load_packages()
    resources = load_resources()
    history = load_history()

    # Check for topic override from environment
    override = os.environ.get("TOPIC_OVERRIDE", "").strip() or None

    print(f"Selecting topic (override: {override})...")
    topic = select_topic(topics, history, override)
    print(f"Selected topic: {topic['name']}")

    # Find related content
    related_packages = find_related_packages(topic, packages)
    related_resources = find_related_resources(topic, resources)
    print(f"Found {len(related_packages)} related packages, {len(related_resources)} related resources")

    print("Generating article with Claude...")
    content = generate_article(topic, related_packages, related_resources)

    print("Creating markdown file...")
    filepath = create_markdown_file(topic, content)
    print(f"Created: {filepath}")

    # Update history
    history["covered"].append(topic["id"])
    history["last_generated"] = datetime.now().isoformat()
    save_history(history)
    print("Updated history")

    print("Done!")

if __name__ == "__main__":
    main()
