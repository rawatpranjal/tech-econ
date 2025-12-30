"""
Discovery Module
================
Uses Perplexity API to discover tech economists
"""

import os
import json
import time
import requests
from typing import List, Dict, Optional


class PerplexityDiscovery:
    """Client for discovering economists using Perplexity API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not set")
        self.base_url = "https://api.perplexity.ai/chat/completions"

    def query(self, prompt: str, max_tokens: int = 2000) -> str:
        """Send a query to Perplexity API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant finding economists who are "
                        "trailblazers in the tech industry. Focus on people with "
                        "Economics PhDs who are at Director level or above in tech "
                        "companies, OR professors who work closely with tech. "
                        "Exclude Nobel laureates."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens
        }

        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def find_economists_at_company(self, company: str) -> Dict:
        """Find economists at a specific company."""
        prompt = f"""
        List all economists with PhD degrees currently working at {company}
        in senior roles (Director, VP, Principal, Senior Staff, Chief Economist).
        For each person provide:
        - Full name
        - Current title
        - PhD institution if known
        Return as structured list.
        """
        result = self.query(prompt)
        return {"query": f"company:{company}", "response": result}

    def expand_from_seed(self, seed_name: str) -> Dict:
        """Find economists connected to a seed person."""
        prompt = f"""
        {seed_name} is a prominent tech economist. List other PhD economists
        who have worked with them, co-authored papers, or held similar roles
        at the same companies. Focus on people currently in tech industry
        senior roles or professors with strong tech connections.
        For each person provide: name, current role, PhD institution.
        """
        result = self.query(prompt)
        return {"query": f"seed:{seed_name}", "response": result}

    def find_by_role(self) -> Dict:
        """Find chief economists at tech companies."""
        prompt = """
        List all current Chief Economists, Head of Economics, or Director
        of Economics at major US tech companies. Include their PhD institution
        and current company. Focus on:
        - FAANG companies (Meta, Amazon, Apple, Netflix, Google)
        - Microsoft, Uber, Lyft, Airbnb, DoorDash
        - Stripe, Square, PayPal
        - LinkedIn, Spotify, Zillow
        """
        result = self.query(prompt)
        return {"query": "role:chief_economist", "response": result}

    def run_full_discovery(
        self,
        seed_people: List[str],
        target_companies: List[str],
        output_path: str = "data/raw/discovery_results.json",
        delay: float = 1.0
    ) -> List[Dict]:
        """Run full discovery pipeline."""
        all_results = []

        # Expand from seeds
        print("=== Expanding from seed people ===")
        for seed in seed_people:
            print(f"  Expanding from {seed}...")
            try:
                result = self.expand_from_seed(seed)
                all_results.append(result)
                time.sleep(delay)
            except Exception as e:
                print(f"    Error: {e}")
                all_results.append({"query": f"seed:{seed}", "error": str(e)})

        # Search by company
        print("\n=== Searching by company ===")
        for company in target_companies:
            print(f"  Searching {company}...")
            try:
                result = self.find_economists_at_company(company)
                all_results.append(result)
                time.sleep(delay)
            except Exception as e:
                print(f"    Error: {e}")
                all_results.append({"query": f"company:{company}", "error": str(e)})

        # Search by role
        print("\n=== Searching by role ===")
        try:
            result = self.find_by_role()
            all_results.append(result)
        except Exception as e:
            print(f"  Error: {e}")
            all_results.append({"query": "role:chief_economist", "error": str(e)})

        # Save results
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2)

        print(f"\n=== Saved {len(all_results)} results to {output_path} ===")
        return all_results


def extract_names_from_results(results: List[Dict]) -> List[str]:
    """Extract unique names from discovery results (basic extraction)."""
    # This is a simple extractor - you may want to improve it
    names = set()
    for result in results:
        response = result.get("response", "")
        # Look for patterns like "Name (Title)" or "- Name:"
        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                # Remove bullet point
                line = line.lstrip("-*").strip()
                # Try to extract name before parenthesis or colon
                if "(" in line:
                    name = line.split("(")[0].strip()
                elif ":" in line:
                    name = line.split(":")[0].strip()
                else:
                    name = line.split(",")[0].strip() if "," in line else line

                # Basic validation
                if name and len(name.split()) >= 2 and len(name) < 50:
                    names.add(name)

    return sorted(names)
