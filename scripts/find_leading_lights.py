#!/usr/bin/env python3
"""
Script to find Leading Lights - Economists who pioneered paths in tech.
Uses Perplexity API to search for candidates.
"""

import os
import json
import time
import requests
from typing import List, Dict

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

# Queries to find trailblazer economists in tech
QUERIES = [
    "Who are the most famous economists working at tech companies like Google Amazon Meta Microsoft? Not Nobel laureates. List their names, current roles, and PhD institutions.",
    "Who are the chief economists and heads of economics at FAANG companies Uber Airbnb Netflix? List names, titles, companies, and where they got their PhD.",
    "Which economics professors from Stanford MIT Harvard Berkeley have strong consulting or advisory relationships with tech companies? List names and their tech affiliations.",
    "Who built the first economics teams at tech companies like Google Amazon Uber Airbnb? List the pioneers and their contributions.",
    "Who are the leading economists in market design and auction theory working in tech industry? Not Nobel laureates.",
    "Which economists pioneered experimentation and A/B testing platforms at tech companies?",
    "Who are senior economists (director level or above) at tech companies with economics PhDs?",
    "Which economists moved from academia to senior tech roles and are considered trailblazers?",
]

# Seed list of known trailblazers to help guide the search
SEED_LIST = [
    "Hal Varian - Google Chief Economist",
    "Susan Athey - Stanford, Microsoft advisor",
    "Pat Bajari - Amazon Chief Economist",
    "Steve Tadelis - Berkeley, eBay/Amazon",
    "Michael Ostrovsky - Stanford, market design",
    "Preston McAfee - Google, Microsoft",
]


def query_perplexity(query: str) -> str:
    """Query Perplexity API and return the response."""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY environment variable not set")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant finding economists who are trailblazers in the tech industry. Focus on people with Economics PhDs who are at Director level or above in tech companies, OR professors who work closely with tech. Exclude Nobel laureates. Provide specific names, their current roles, companies, and PhD institutions when available."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0.2,
        "max_tokens": 2000
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"]


def main():
    print("=" * 60)
    print("Finding Leading Lights - Tech Economist Trailblazers")
    print("=" * 60)

    print("\nSeed list of known trailblazers:")
    for person in SEED_LIST:
        print(f"  - {person}")

    print("\n" + "=" * 60)
    print("Querying Perplexity API...")
    print("=" * 60 + "\n")

    all_results = []

    for i, query in enumerate(QUERIES, 1):
        print(f"\n[Query {i}/{len(QUERIES)}]")
        print(f"Q: {query[:80]}...")
        print("-" * 40)

        try:
            result = query_perplexity(query)
            print(result)
            all_results.append({
                "query": query,
                "response": result
            })
            # Rate limiting - be nice to the API
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            all_results.append({
                "query": query,
                "error": str(e)
            })

    # Save results
    output_file = "leading_lights_candidates.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Results saved to {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
