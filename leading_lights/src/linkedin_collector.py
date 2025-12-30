"""
LinkedIn Collector Module
=========================
Helpers for collecting LinkedIn profile data (manual + optional API)
"""

import pandas as pd
from typing import List, Dict, Optional
from urllib.parse import quote


def generate_search_urls(candidates: List[str]) -> List[str]:
    """Generate LinkedIn search URLs for manual review."""
    base = "https://www.linkedin.com/search/results/people/?keywords="
    return [f"{base}{quote(name + ' economist')}" for name in candidates]


def generate_google_search_urls(candidates: List[str]) -> List[str]:
    """Generate Google search URLs as backup."""
    base = "https://www.google.com/search?q="
    return [f"{base}{quote(name + ' economist PhD linkedin')}" for name in candidates]


def create_collection_sheet(candidates: List[str]) -> pd.DataFrame:
    """Create spreadsheet for manual data entry."""
    df = pd.DataFrame({
        'name': candidates,
        'linkedin_url': '',
        'current_title': '',
        'current_company': '',
        'phd_institution': '',
        'phd_year': '',
        'phd_field': '',  # Economics, Finance, Business Economics, etc.
        'career_path': '',  # Format: "Company1 (2015-2019) → Company2 (2019-2022)"
        'known_for': '',
        'twitter': '',
        'personal_site': '',
        'location': '',
        'is_senior': False,  # Director+, VP, Senior Staff, etc.
        'is_professor': False,
        'verified': False,
        'notes': ''
    })

    # Add helper columns
    df['linkedin_search'] = generate_search_urls(candidates)
    df['google_search'] = generate_google_search_urls(candidates)

    return df


def load_completed_sheet(filepath: str) -> pd.DataFrame:
    """Load manually completed collection sheet."""
    df = pd.read_csv(filepath)
    # Convert boolean columns
    for col in ['is_senior', 'is_professor', 'verified']:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


def validate_sheet(df: pd.DataFrame) -> Dict:
    """Validate collection sheet for completeness."""
    stats = {
        'total': len(df),
        'verified': df['verified'].sum() if 'verified' in df.columns else 0,
        'with_linkedin': (df['linkedin_url'].notna() & (df['linkedin_url'] != '')).sum(),
        'with_phd': (df['phd_institution'].notna() & (df['phd_institution'] != '')).sum(),
        'is_senior': df['is_senior'].sum() if 'is_senior' in df.columns else 0,
        'is_professor': df['is_professor'].sum() if 'is_professor' in df.columns else 0,
    }
    stats['completion_rate'] = stats['verified'] / stats['total'] if stats['total'] > 0 else 0
    return stats


def filter_eligible(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to only eligible candidates (PhD + senior/professor)."""
    has_phd = df['phd_institution'].notna() & (df['phd_institution'] != '')
    is_qualified = df['is_senior'] | df['is_professor']
    is_verified = df['verified'] == True

    return df[has_phd & is_qualified & is_verified].copy()


# Optional: Proxycurl API integration (paid service)
class ProxycurlScraper:
    """
    LinkedIn profile scraper using Proxycurl API.
    Requires paid API key from https://nubela.co/proxycurl
    """

    def __init__(self, api_key: Optional[str] = None):
        import os
        self.api_key = api_key or os.environ.get("PROXYCURL_API_KEY")
        self.base_url = "https://nubela.co/proxycurl/api/v2/linkedin"

    def get_profile(self, linkedin_url: str) -> Dict:
        """Fetch profile data from LinkedIn URL."""
        if not self.api_key:
            raise ValueError("PROXYCURL_API_KEY not set")

        import requests
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"url": linkedin_url}
        response = requests.get(self.base_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def extract_career_path(self, profile: Dict) -> str:
        """Extract career path from profile."""
        experiences = profile.get('experiences', [])
        path = []
        for exp in experiences:
            company = exp.get('company', 'Unknown')
            start = exp.get('starts_at', {}).get('year', '?')
            end = exp.get('ends_at', {}).get('year', 'present') if exp.get('ends_at') else 'present'
            path.append(f"{company} ({start}-{end})")
        return " → ".join(path[:5])  # Limit to 5 most recent

    def extract_phd_info(self, profile: Dict) -> Dict:
        """Extract PhD information from education."""
        education = profile.get('education', [])
        for edu in education:
            degree = edu.get('degree_name', '').lower()
            if 'phd' in degree or 'ph.d' in degree or 'doctor' in degree:
                return {
                    'institution': edu.get('school', ''),
                    'field': edu.get('field_of_study', ''),
                    'year': edu.get('ends_at', {}).get('year', '')
                }
        return {}
