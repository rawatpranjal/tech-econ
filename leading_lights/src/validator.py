"""
Validator Module
================
Verify PhD credentials and role seniority
"""

from typing import Optional
import re


class Validator:
    """Validate economist credentials using Perplexity API."""

    SENIOR_KEYWORDS = [
        'chief', 'head', 'director', 'vp', 'vice president',
        'principal', 'senior staff', 'distinguished', 'fellow',
        'lead', 'senior principal', 'staff', 'managing'
    ]

    PROFESSOR_KEYWORDS = [
        'professor', 'faculty', 'lecturer', 'researcher',
        'assistant professor', 'associate professor', 'full professor',
        'emeritus', 'visiting'
    ]

    PHD_ECONOMICS_FIELDS = [
        'economics', 'economic', 'business economics', 'applied economics',
        'finance', 'public policy', 'political economy', 'econometrics',
        'agricultural economics', 'labor economics', 'industrial organization'
    ]

    def __init__(self, perplexity_client=None):
        self.perplexity = perplexity_client

    def verify_phd(self, name: str, claimed_institution: str) -> bool:
        """Verify PhD using Perplexity API."""
        if not self.perplexity:
            return False

        prompt = f"""
        Verify: Did {name} receive a PhD in Economics (or related field like
        Business Economics, Finance, Public Policy) from {claimed_institution}?
        Answer with YES or NO followed by a brief explanation.
        """
        response = self.perplexity.query(prompt)
        return self._parse_confirmation(response)

    def verify_current_role(self, name: str, claimed_company: str) -> bool:
        """Verify current employment."""
        if not self.perplexity:
            return False

        prompt = f"""
        Is {name} currently working at {claimed_company}?
        What is their current role/title?
        Answer with YES or NO followed by their current role.
        """
        response = self.perplexity.query(prompt)
        return self._parse_confirmation(response)

    def is_senior_enough(self, title: str) -> bool:
        """Check if title indicates senior level."""
        if not title:
            return False
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.SENIOR_KEYWORDS)

    def is_professor(self, title: str) -> bool:
        """Check if title indicates professor/academic."""
        if not title:
            return False
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.PROFESSOR_KEYWORDS)

    def is_economics_phd(self, field: str) -> bool:
        """Check if PhD field is economics or related."""
        if not field:
            return False
        field_lower = field.lower()
        return any(kw in field_lower for kw in self.PHD_ECONOMICS_FIELDS)

    def is_eligible(self, person: dict) -> bool:
        """
        Check if person meets Leading Lights criteria:
        - Has Economics PhD (or related field)
        - Is senior level in tech OR is professor with tech ties
        """
        # Must have PhD institution
        if not person.get('phd_institution'):
            return False

        # Check field if available
        phd_field = person.get('phd_field', '')
        if phd_field and not self.is_economics_phd(phd_field):
            return False

        # Must be senior or professor
        title = person.get('current_title', '')
        is_senior = self.is_senior_enough(title)
        is_prof = self.is_professor(title) or person.get('is_professor', False)

        return is_senior or is_prof

    def _parse_confirmation(self, response: str) -> bool:
        """Parse yes/no from API response."""
        if not response:
            return False

        response_lower = response.lower().strip()

        # Check for explicit yes/no at start
        if response_lower.startswith('yes'):
            return True
        if response_lower.startswith('no'):
            return False

        # Check for positive indicators
        positive = ['yes', 'correct', 'confirmed', 'true', 'indeed', 'affirmative']
        negative = ['no', 'incorrect', 'not', 'false', 'unable to confirm']

        # Weight towards negative if uncertain
        has_positive = any(word in response_lower for word in positive)
        has_negative = any(word in response_lower for word in negative)

        if has_positive and not has_negative:
            return True
        return False


def validate_batch(persons: list, validator: Validator) -> list:
    """Validate a batch of persons."""
    results = []
    for person in persons:
        is_eligible = validator.is_eligible(person)
        person['eligible'] = is_eligible
        results.append(person)
    return results
