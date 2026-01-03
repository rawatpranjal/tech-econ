#!/usr/bin/env python3
"""
Advanced LLM Metadata Enrichment for tech-econ.org

Uses GPT-4o-mini for cost-effective enrichment (~$1 for full corpus).

Features:
- Section-specific schemas and prompts (papers, packages, datasets, etc.)
- Content hashing for incremental updates
- Confidence scoring with tiered processing
- Anti-hallucination safeguards

Usage:
    OPENAI_API_KEY=sk-... python3 scripts/enrich_metadata_v2.py
    OPENAI_API_KEY=sk-... python3 scripts/enrich_metadata_v2.py --file packages.json
    OPENAI_API_KEY=sk-... python3 scripts/enrich_metadata_v2.py --file papers.json --limit 10
    OPENAI_API_KEY=sk-... python3 scripts/enrich_metadata_v2.py --force  # Re-enrich all
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:
    print("Error: pydantic package not installed")
    print("Install with: pip install pydantic")
    sys.exit(1)

try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    print("Error: openai package not installed")
    print("Install with: pip install openai")
    sys.exit(1)

# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / ".enrichment_state.json"
REVIEW_FILE = DATA_DIR / ".enrichment_review.json"

SCHEMA_VERSION = "2.1"
MODEL_VERSION = "gpt-4o-mini"

# Rate limiting - GPT-4o-mini has generous limits
REQUESTS_PER_MINUTE = 60
REQUEST_DELAY = 60.0 / REQUESTS_PER_MINUTE
SAVE_EVERY_N = 10

# Async batch processing settings
BATCH_SIZE = 10  # Concurrent requests per batch (safe for 60 RPM limit)

# Files to process (in order)
DATA_FILES = [
    "packages.json",
    "datasets.json",
    "resources.json",
    "books.json",
    "talks.json",
    "career.json",
    "community.json",
]

# Papers handled separately due to nested structure
PAPERS_FILE = "papers.json"

# Anti-hallucination instruction added to all prompts
ANTI_HALLUCINATION = """
CRITICAL: Only include information that can be reasonably inferred from the provided data.
- If you cannot determine a field from the given information, use null or empty array []
- DO NOT invent datasets, paper references, specific statistics, or tool names
- DO NOT guess temporal coverage, geographic scope, or size metrics
- For implements_paper/builds_on: Only include if explicitly mentioned or very well-known
- For synthetic_questions: Base these on the actual description, not assumptions
- When uncertain, prefer empty/null over fabricated data
"""

# =============================================================================
# Content-Type Specific Embedding Text Instructions
# =============================================================================

EMBEDDING_TEXT_BASE = """
EMBEDDING_TEXT: Generate a rich, dense description (500-1000 words) for semantic search.
Write as continuous prose, keyword-rich, technically accurate.
Do NOT invent specific paper names, dataset names, or tool names not in the source.
"""

EMBEDDING_TEXT_PAPER = EMBEDDING_TEXT_BASE + """
For this PAPER, include:
- Research problem and motivation
- Key methodology/approach in technical detail
- Main findings and contributions
- Econometric/statistical techniques used
- Data requirements and assumptions
- Limitations and caveats
- Related research areas this connects to
- Practical implications for applied researchers
- When/why a practitioner would cite or apply this paper
"""

EMBEDDING_TEXT_PACKAGE = EMBEDDING_TEXT_BASE + """
For this PACKAGE/LIBRARY, include:
- Core functionality and main features
- API design philosophy (object-oriented, functional, declarative)
- Key classes, functions, or modules
- Installation and basic usage patterns
- Comparison to alternative approaches (without inventing names)
- Performance characteristics and scalability
- Integration with data science workflows
- Common pitfalls and best practices
- When to use vs when NOT to use this package
"""

EMBEDDING_TEXT_DATASET = EMBEDDING_TEXT_BASE + """
For this DATASET, include:
- Data structure and schema (rows, columns, variables)
- Collection methodology and data sources
- Coverage: temporal, geographic, demographic
- Key variables and what they measure
- Data quality and known limitations
- Common preprocessing steps needed
- Research questions it can address
- Types of analyses it supports (regression, ML, descriptive)
- How researchers typically use this in studies
"""

EMBEDDING_TEXT_RESOURCE = EMBEDDING_TEXT_BASE + """
For this LEARNING RESOURCE, include:
- Topics and concepts covered in detail
- Teaching approach and pedagogy
- Prerequisites and assumed knowledge
- Learning outcomes and skills gained
- Hands-on exercises or projects included
- How it compares to other learning paths
- Best audience (students, practitioners, career changers)
- How long it takes to complete
- What you can do after finishing this resource
"""

EMBEDDING_TEXT_TALK = EMBEDDING_TEXT_BASE + """
For this TALK/PODCAST/VIDEO, include:
- Main topics and themes discussed
- Key insights and takeaways
- Speaker's perspective and expertise
- Industry or academic context
- Practical advice or recommendations shared
- Questions answered or raised
- Relevance to different audience segments
- How it fits in the broader discourse
- Why someone would watch/listen to this
"""

EMBEDDING_TEXT_CAREER = EMBEDDING_TEXT_BASE + """
For this CAREER RESOURCE, include:
- Career paths and roles discussed
- Skills and qualifications emphasized
- Industry and company context
- Interview preparation content
- Salary and compensation insights (if any)
- Day-to-day job responsibilities covered
- Career progression and growth paths
- Networking and job search strategies
- Common challenges and how to overcome them
"""

EMBEDDING_TEXT_COMMUNITY = EMBEDDING_TEXT_BASE + """
For this CONFERENCE/EVENT, include:
- Event focus and main themes
- Typical attendee profile
- Session formats (talks, workshops, networking)
- Academic vs industry orientation
- Geographic reach and accessibility
- Notable tracks or special sessions
- Networking opportunities
- What attendees typically gain
- How it compares to similar events
"""

EMBEDDING_TEXT_MAP = {
    "paper": EMBEDDING_TEXT_PAPER,
    "package": EMBEDDING_TEXT_PACKAGE,
    "dataset": EMBEDDING_TEXT_DATASET,
    "resource": EMBEDDING_TEXT_RESOURCE,
    "book": EMBEDDING_TEXT_RESOURCE,
    "talk": EMBEDDING_TEXT_TALK,
    "career": EMBEDDING_TEXT_CAREER,
    "community": EMBEDDING_TEXT_COMMUNITY,
}

# =============================================================================
# Pydantic Schemas - Section Specific
# =============================================================================

AudienceType = Literal["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"]
DifficultyType = Literal["beginner", "intermediate", "advanced"]


class BaseEnrichment(BaseModel):
    """Base schema for all content types."""
    difficulty: DifficultyType
    prerequisites: list[str] = Field(default_factory=list, max_length=5)
    topic_tags: list[str] = Field(default_factory=list, max_length=7)
    summary: str = Field(default="", max_length=600)
    audience: list[AudienceType] = Field(default_factory=list)
    synthetic_questions: list[str] = Field(default_factory=list, min_length=4, max_length=8)
    use_cases: list[str] = Field(default_factory=list, max_length=4)
    embedding_text: str = Field(default="", max_length=6000)  # ~1000 words for semantic search


class PaperEnrichment(BaseEnrichment):
    """Extended schema for academic papers."""
    methodology_tags: list[str] = Field(default_factory=list, max_length=5)
    key_findings: str = Field(default="", max_length=300)
    research_questions: list[str] = Field(default_factory=list, max_length=3)
    datasets_used: list[str] = Field(default_factory=list, max_length=5)
    implements_method: str | None = None
    builds_on: list[str] = Field(default_factory=list, max_length=3)


class PackageEnrichment(BaseEnrichment):
    """Extended schema for software packages."""
    primary_use_cases: list[str] = Field(default_factory=list, max_length=5)
    api_complexity: Literal["simple", "intermediate", "advanced"] = "intermediate"
    framework_compatibility: list[str] = Field(default_factory=list, max_length=5)
    implements_paper: str | None = None
    related_packages: list[str] = Field(default_factory=list, max_length=5)
    maintenance_status: Literal["active", "stable", "unmaintained"] = "active"


class DatasetEnrichment(BaseEnrichment):
    """Extended schema for datasets."""
    domain_tags: list[str] = Field(default_factory=list, max_length=5)
    data_modality: Literal["tabular", "text", "image", "time-series", "graph", "mixed"] = "tabular"
    temporal_coverage: str | None = None
    geographic_scope: str | None = None
    size_category: Literal["small", "medium", "large", "massive"] = "medium"
    benchmark_usage: list[str] = Field(default_factory=list, max_length=4)


class ResourceEnrichment(BaseEnrichment):
    """Extended schema for learning resources (blogs, tutorials, courses)."""
    content_format: Literal["article", "tutorial", "course", "video", "book", "newsletter"] = "article"
    estimated_duration: str | None = None
    skill_progression: list[str] = Field(default_factory=list, max_length=4)


class TalkEnrichment(BaseEnrichment):
    """Extended schema for talks/podcasts/interviews."""
    speaker_expertise: list[str] = Field(default_factory=list, max_length=4)
    key_insights: list[str] = Field(default_factory=list, max_length=4)
    mentioned_tools: list[str] = Field(default_factory=list, max_length=5)


class CareerEnrichment(BaseEnrichment):
    """Extended schema for career resources."""
    role_type: list[str] = Field(default_factory=list, max_length=4)
    experience_level: Literal["entry", "mid", "senior", "executive"] = "mid"
    company_context: list[str] = Field(default_factory=list, max_length=4)


class CommunityEnrichment(BaseEnrichment):
    """Extended schema for community/conferences."""
    event_format: Literal["conference", "meetup", "workshop", "online", "hybrid"] = "conference"
    geographic_focus: str | None = None
    frequency: Literal["annual", "biannual", "quarterly", "monthly", "one-time"] = "annual"


# Schema mapping
SCHEMA_MAP = {
    "paper": PaperEnrichment,
    "package": PackageEnrichment,
    "dataset": DatasetEnrichment,
    "resource": ResourceEnrichment,
    "book": ResourceEnrichment,
    "talk": TalkEnrichment,
    "career": CareerEnrichment,
    "community": CommunityEnrichment,
}


# =============================================================================
# Section-Specific Prompts
# =============================================================================

PAPER_PROMPT = """You're enriching academic paper metadata for tech-econ.org, a curated library for tech economists.

PAPER:
Title: {title}
Authors: {authors}
Year: {year}
Description: {description}
Tags: {tags}
Citations: {citations}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": ["specific-method-1", "specific-concept-2"],
  "topic_tags": ["method-tag", "domain-tag", "application-tag"],
  "summary": "2-3 sentences: What problem does this solve? What's the main contribution?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 natural search queries to find this paper"],
  "use_cases": ["2-3 practical scenarios where you'd apply this"],
  "methodology_tags": ["difference-in-differences", "instrumental-variables", etc.],
  "key_findings": "One sentence: main result if mentioned in description, or empty string",
  "research_questions": ["What question does this answer?"],
  "datasets_used": ["Only if explicitly mentioned in description, else empty array"],
  "implements_method": "Name of new method if this paper introduces one, else null",
  "builds_on": ["Only well-known foundational papers if clearly referenced, else empty"],
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}

RULES:
- METHODOLOGY_TAGS: Use hyphenated method names (difference-in-differences, regression-discontinuity)
- PREREQUISITES: Actual methods/concepts needed (bayesian-inference, panel-data)
- SYNTHETIC_QUESTIONS: Natural queries like "how to estimate treatment effects"
- KEY_FINDINGS: Only include if explicitly stated in description; leave empty if not mentioned
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


PACKAGE_PROMPT = """You're enriching software package metadata for tech-econ.org.

PACKAGE:
Name: {name}
Description: {description}
Category: {category}
Language: {language}
Tags: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": ["python-pandas", "scikit-learn-basics", etc.],
  "topic_tags": ["causal-inference", "time-series", "bayesian", etc.],
  "summary": "2-3 sentences: What does this package do? Who uses it?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 search queries to find this package"],
  "use_cases": ["2-4 specific scenarios"],
  "primary_use_cases": ["causal forest estimation", "A/B test analysis", etc.],
  "api_complexity": "simple|intermediate|advanced",
  "framework_compatibility": ["Only include if explicitly mentioned or obvious from description"],
  "implements_paper": "Author (Year) only if clearly documented, else null",
  "related_packages": ["Only well-known similar packages you're confident exist"],
  "maintenance_status": "active|stable|unmaintained",
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}

RULES:
- PRIMARY_USE_CASES: Specific tasks inferred from description
- IMPLEMENTS_PAPER: Only if package explicitly mentions implementing a paper
- RELATED_PACKAGES: Only include packages you're certain exist
- SYNTHETIC_QUESTIONS: "python library for X", "how to do Y in python"
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


DATASET_PROMPT = """You're enriching dataset metadata for tech-econ.org.

DATASET:
Name: {name}
Description: {description}
Category: {category}
Tags: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": ["pandas-dataframes", "regression-analysis", etc.],
  "topic_tags": ["e-commerce", "consumer-behavior", "pricing", etc.],
  "summary": "2-3 sentences: What data is this? What can you do with it?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 search queries to find this dataset"],
  "use_cases": ["2-4 analysis scenarios"],
  "domain_tags": ["retail", "healthcare", "fintech", etc.],
  "data_modality": "tabular|text|image|time-series|graph|mixed",
  "temporal_coverage": "Only if explicitly mentioned, else null",
  "geographic_scope": "Only if explicitly mentioned, else null",
  "size_category": "small|medium|large|massive - only if inferable, default medium",
  "benchmark_usage": ["Common uses if mentioned in description"],
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}

RULES:
- DOMAIN_TAGS: Industry/sector tags based on description
- SIZE_CATEGORY: Only specify if size is mentioned; otherwise use "medium"
- TEMPORAL_COVERAGE: Only if years are explicitly mentioned
- GEOGRAPHIC_SCOPE: Only if location/region is explicitly mentioned
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


RESOURCE_PROMPT = """You're enriching learning resource metadata for tech-econ.org.

RESOURCE:
Name: {name}
Description: {description}
Category: {category}
Type: {type}
Tags: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": ["python-basics", "linear-regression", etc.],
  "topic_tags": ["causal-inference", "machine-learning", "statistics", etc.],
  "summary": "2-3 sentences: What will you learn? Who is this for?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 search queries"],
  "use_cases": ["when to use this resource"],
  "content_format": "article|tutorial|course|video|book|newsletter",
  "estimated_duration": "Only if inferable from description, else null",
  "skill_progression": ["skills you'll gain based on description"],
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


TALK_PROMPT = """You're enriching talk/podcast metadata for tech-econ.org.

TALK:
Name: {name}
Description: {description}
Category: {category}
Type: {type}
Tags: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": [],
  "topic_tags": ["industry-insights", "career-advice", etc.],
  "summary": "2-3 sentences: What's discussed? Key takeaways?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 search queries"],
  "use_cases": ["why watch/listen to this"],
  "speaker_expertise": ["areas mentioned in description"],
  "key_insights": ["Only insights explicitly mentioned in description"],
  "mentioned_tools": ["Only tools/methods explicitly mentioned"],
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


CAREER_PROMPT = """You're enriching career resource metadata for tech-econ.org.

RESOURCE:
Name: {name}
Description: {description}
Category: {category}
Tags: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": [],
  "topic_tags": ["interview-prep", "salary-negotiation", "job-search", etc.],
  "summary": "2-3 sentences: What career advice does this provide?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 search queries about career topics"],
  "use_cases": ["when to use this resource"],
  "role_type": ["data-scientist", "economist", "ML-engineer", etc.],
  "experience_level": "entry|mid|senior|executive",
  "company_context": ["Only if mentioned: FAANG, startup, finance, etc."],
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


COMMUNITY_PROMPT = """You're enriching conference/community metadata for tech-econ.org.

EVENT:
Name: {name}
Description: {description}
Category: {category}
Type: {type}
Location: {location}
Tags: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": [],
  "topic_tags": ["networking", "academic-conference", "industry-event", etc.],
  "summary": "2-3 sentences: What is this event? Who attends?",
  "audience": ["Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"],
  "synthetic_questions": ["6-8 search queries"],
  "use_cases": ["why attend this"],
  "event_format": "conference|meetup|workshop|online|hybrid",
  "geographic_focus": "Only if location is mentioned, else null",
  "frequency": "annual|biannual|quarterly|monthly|one-time",
  "embedding_text": "500-1000 word dense description for semantic search (see instructions below)"
}}
{anti_hallucination}

{embedding_text_instruction}

JSON only, no markdown."""


PROMPT_MAP = {
    "paper": PAPER_PROMPT,
    "package": PACKAGE_PROMPT,
    "dataset": DATASET_PROMPT,
    "resource": RESOURCE_PROMPT,
    "book": RESOURCE_PROMPT,
    "talk": TALK_PROMPT,
    "career": CAREER_PROMPT,
    "community": COMMUNITY_PROMPT,
}


# =============================================================================
# State Management
# =============================================================================

def load_state() -> dict:
    """Load enrichment state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "schema_version": SCHEMA_VERSION,
        "last_run": None,
        "items": {}
    }


def save_state(state: dict) -> None:
    """Save enrichment state to file."""
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def compute_hash(item: dict) -> str:
    """Compute SHA256 hash of item's core content."""
    core_fields = ["name", "title", "description", "category", "tags", "url"]
    content = {k: item.get(k) for k in core_fields if k in item}
    content_str = json.dumps(content, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()[:16]


def get_item_id(item: dict) -> str:
    """Get unique identifier for an item."""
    return item.get("name") or item.get("title") or item.get("url", "unknown")


def needs_enrichment(item: dict, state: dict, file_key: str, force: bool = False) -> bool:
    """Check if item needs enrichment based on content hash."""
    if force:
        return True

    item_id = get_item_id(item)
    content_hash = compute_hash(item)

    file_state = state.get("items", {}).get(file_key, {})

    if item_id not in file_state:
        return True

    existing = file_state[item_id]

    if existing.get("content_hash") != content_hash:
        return True

    if existing.get("schema_version", "1.0") < SCHEMA_VERSION:
        return True

    return False


def update_state(state: dict, file_key: str, item: dict, confidence: float) -> None:
    """Update state after enriching an item."""
    if "items" not in state:
        state["items"] = {}
    if file_key not in state["items"]:
        state["items"][file_key] = {}

    item_id = get_item_id(item)
    state["items"][file_key][item_id] = {
        "content_hash": compute_hash(item),
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "confidence": confidence
    }


# =============================================================================
# Confidence Scoring
# =============================================================================

def calculate_confidence(enrichment: dict, item: dict, content_type: str) -> float:
    """Calculate confidence score for enrichment quality."""
    score = 1.0

    # Check synthetic questions (critical for search)
    questions = enrichment.get("synthetic_questions", [])
    if not questions:
        score -= 0.3
    elif len(questions) < 4:
        score -= 0.15

    # Check summary quality
    summary = enrichment.get("summary", "")
    if not summary:
        score -= 0.2
    elif len(summary) < 50:
        score -= 0.1

    # Check difficulty validity
    difficulty = enrichment.get("difficulty", "")
    if difficulty not in {"beginner", "intermediate", "advanced"}:
        score -= 0.2

    # Check audience validity
    valid_audiences = {"Early-PhD", "Junior-DS", "Mid-DS", "Senior-DS", "Curious-browser"}
    audience = enrichment.get("audience", [])
    if not audience:
        score -= 0.1
    elif not all(a in valid_audiences for a in audience):
        score -= 0.15

    # Internal consistency checks
    if difficulty == "beginner":
        prereqs = enrichment.get("prerequisites", [])
        advanced_prereqs = ["PhD", "research", "advanced", "expert"]
        if any(p.lower() in str(prereqs).lower() for p in advanced_prereqs):
            score -= 0.1

    # Content-type specific checks
    if content_type == "paper":
        if not enrichment.get("methodology_tags"):
            score -= 0.1
    elif content_type == "package":
        if not enrichment.get("primary_use_cases"):
            score -= 0.1
    elif content_type == "dataset":
        if not enrichment.get("domain_tags"):
            score -= 0.1

    return max(0.0, min(1.0, score))


def log_for_review(item: dict, enrichment: dict, confidence: float, reason: str) -> None:
    """Log items that need human review."""
    review_log = []
    if REVIEW_FILE.exists():
        with open(REVIEW_FILE) as f:
            review_log = json.load(f)

    review_log.append({
        "item_id": get_item_id(item),
        "confidence": confidence,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "enrichment_sample": {
            "difficulty": enrichment.get("difficulty"),
            "audience": enrichment.get("audience"),
            "synthetic_questions": enrichment.get("synthetic_questions", [])[:2]
        }
    })

    with open(REVIEW_FILE, "w") as f:
        json.dump(review_log, f, indent=2)
        f.write("\n")


# =============================================================================
# Enrichment
# =============================================================================

def format_prompt(item: dict, content_type: str) -> str:
    """Format the prompt template with item data."""
    template = PROMPT_MAP.get(content_type, RESOURCE_PROMPT)

    # Build format dict with all possible fields
    format_dict = {
        "name": item.get("name", item.get("title", "")),
        "title": item.get("title", item.get("name", "")),
        "description": item.get("description", ""),
        "category": item.get("category", ""),
        "type": item.get("type", ""),
        "language": item.get("language", ""),
        "location": item.get("location", ""),
        "authors": item.get("authors", ""),
        "year": item.get("year", ""),
        "citations": item.get("citations", 0),
        "tags": ", ".join(item.get("tags", [])) if isinstance(item.get("tags"), list) else item.get("tags", ""),
        "anti_hallucination": ANTI_HALLUCINATION,
        # Get content-type specific embedding text instruction
        "embedding_text_instruction": EMBEDDING_TEXT_MAP.get(content_type, EMBEDDING_TEXT_BASE),
    }

    return template.format(**format_dict)


def enrich_item(client: Any, item: dict, content_type: str) -> tuple[dict | None, float]:
    """Enrich a single item with LLM-generated metadata."""
    prompt = format_prompt(item, content_type)

    try:
        response = client.chat.completions.create(
            model=MODEL_VERSION,
            messages=[
                {
                    "role": "system",
                    "content": "You are a metadata enrichment assistant. Return only valid JSON. Never fabricate information - use null or empty arrays when data is not available."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,  # Increased from 800 to accommodate embedding_text
            temperature=0.3,  # Lower temperature for more consistent output
            response_format={"type": "json_object"}  # Force JSON response
        )

        text = response.choices[0].message.content.strip()
        enrichment = json.loads(text)

        # Validate with Pydantic schema
        schema_class = SCHEMA_MAP.get(content_type, BaseEnrichment)
        try:
            validated = schema_class(**enrichment)
            enrichment = validated.model_dump()
        except ValidationError as e:
            print(f"    Validation warning: {e.error_count()} issues (using raw)")

        # Calculate confidence
        confidence = calculate_confidence(enrichment, item, content_type)

        return enrichment, confidence

    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {e}")
        return None, 0.0
    except Exception as e:
        print(f"    API error: {e}")
        return None, 0.0


async def enrich_item_async(client: AsyncOpenAI, item: dict, content_type: str) -> tuple[dict | None, float]:
    """Async version: Enrich a single item with LLM-generated metadata."""
    prompt = format_prompt(item, content_type)

    try:
        response = await client.chat.completions.create(
            model=MODEL_VERSION,
            messages=[
                {
                    "role": "system",
                    "content": "You are a metadata enrichment assistant. Return only valid JSON. Never fabricate information - use null or empty arrays when data is not available."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        text = response.choices[0].message.content.strip()
        enrichment = json.loads(text)

        # Validate with Pydantic schema
        schema_class = SCHEMA_MAP.get(content_type, BaseEnrichment)
        try:
            validated = schema_class(**enrichment)
            enrichment = validated.model_dump()
        except ValidationError:
            pass  # Use raw enrichment if validation fails

        # Calculate confidence
        confidence = calculate_confidence(enrichment, item, content_type)

        return enrichment, confidence

    except json.JSONDecodeError:
        return None, 0.0
    except Exception:
        return None, 0.0


async def process_batch_async(
    client: AsyncOpenAI,
    items: list[dict],
    content_type: str,
    batch_size: int = BATCH_SIZE
) -> list[tuple[dict | None, float]]:
    """Process a batch of items concurrently with rate limiting."""
    semaphore = asyncio.Semaphore(batch_size)

    async def process_with_semaphore(item: dict) -> tuple[dict | None, float]:
        async with semaphore:
            return await enrich_item_async(client, item, content_type)

    tasks = [process_with_semaphore(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to (None, 0.0)
    return [
        r if isinstance(r, tuple) else (None, 0.0)
        for r in results
    ]


def apply_enrichment(item: dict, enrichment: dict, content_type: str) -> None:
    """Apply enrichment data to item."""
    # Base fields (all content types)
    base_fields = [
        "difficulty", "prerequisites", "topic_tags", "summary",
        "audience", "synthetic_questions", "use_cases", "embedding_text"
    ]

    # Extended fields per content type
    extended_fields = {
        "paper": ["methodology_tags", "key_findings", "research_questions",
                  "datasets_used", "implements_method", "builds_on"],
        "package": ["primary_use_cases", "api_complexity", "framework_compatibility",
                    "implements_paper", "related_packages", "maintenance_status"],
        "dataset": ["domain_tags", "data_modality", "temporal_coverage",
                    "geographic_scope", "size_category", "benchmark_usage"],
        "resource": ["content_format", "estimated_duration", "skill_progression"],
        "book": ["content_format", "estimated_duration", "skill_progression"],
        "talk": ["speaker_expertise", "key_insights", "mentioned_tools"],
        "career": ["role_type", "experience_level", "company_context"],
        "community": ["event_format", "geographic_focus", "frequency"],
    }

    # Apply base fields
    for field in base_fields:
        if field in enrichment:
            item[field] = enrichment[field]

    # Apply extended fields
    for field in extended_fields.get(content_type, []):
        if field in enrichment and enrichment[field]:
            item[field] = enrichment[field]


# =============================================================================
# File Processing
# =============================================================================

def save_file(filepath: Path, data: Any) -> None:
    """Save data to JSON file."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def process_flat_file(
    client: Any,
    filepath: Path,
    state: dict,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False
) -> int:
    """Process a flat JSON file (list of items)."""
    if not filepath.exists():
        print(f"Skipping {filepath.name} (not found)")
        return 0

    with open(filepath) as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Skipping {filepath.name} (not a list)")
        return 0

    content_type = filepath.stem.rstrip("s")  # packages -> package
    file_key = filepath.name

    # Count items needing enrichment
    to_enrich = [i for i, item in enumerate(data)
                 if needs_enrichment(item, state, file_key, force)]

    print(f"\n{'='*60}")
    print(f"Processing {filepath.name}: {len(data) - len(to_enrich)}/{len(data)} done, {len(to_enrich)} remaining")
    print(f"{'='*60}")

    if limit:
        to_enrich = to_enrich[:limit]

    enriched_count = 0
    pending_save = 0

    for idx, item_idx in enumerate(to_enrich):
        item = data[item_idx]
        name = get_item_id(item)
        print(f"  [{idx + 1}/{len(to_enrich)}] {name[:50]}...")

        if dry_run:
            enriched_count += 1
            continue

        enrichment, confidence = enrich_item(client, item, content_type)

        if enrichment:
            apply_enrichment(item, enrichment, content_type)
            update_state(state, file_key, item, confidence)
            enriched_count += 1
            pending_save += 1

            # Log for review if needed
            if confidence < 0.7:
                log_for_review(item, enrichment, confidence, "low_confidence")
                print(f"    [REVIEW NEEDED - confidence: {confidence:.2f}]")
            elif confidence < 0.9:
                print(f"    [OK - confidence: {confidence:.2f}]")

            # Periodic save
            if pending_save >= SAVE_EVERY_N:
                save_file(filepath, data)
                save_state(state)
                print(f"    [Saved {enriched_count} items]")
                pending_save = 0
        else:
            print(f"    [FAILED - skipping]")

        time.sleep(REQUEST_DELAY)

    # Final save
    if not dry_run and pending_save > 0:
        save_file(filepath, data)
        save_state(state)
        print(f"  Final save: {enriched_count} items")

    print(f"  Done: {enriched_count} enriched")
    return enriched_count


async def process_flat_file_async(
    client: AsyncOpenAI,
    filepath: Path,
    state: dict,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False
) -> int:
    """Async version: Process a flat JSON file with batch parallelism."""
    if not filepath.exists():
        print(f"Skipping {filepath.name} (not found)")
        return 0

    with open(filepath) as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Skipping {filepath.name} (not a list)")
        return 0

    content_type = filepath.stem.rstrip("s")  # packages -> package
    file_key = filepath.name

    # Collect items needing enrichment
    items_to_enrich = [(i, data[i]) for i, item in enumerate(data)
                       if needs_enrichment(item, state, file_key, force)]

    print(f"\n{'='*60}")
    print(f"Processing {filepath.name}: {len(data) - len(items_to_enrich)}/{len(data)} done, {len(items_to_enrich)} remaining")
    print(f"{'='*60}")

    if limit:
        items_to_enrich = items_to_enrich[:limit]

    if dry_run:
        print(f"  [DRY RUN] Would process {len(items_to_enrich)} items")
        return len(items_to_enrich)

    enriched_count = 0
    failed_count = 0

    # Process in batches
    for batch_start in range(0, len(items_to_enrich), BATCH_SIZE):
        batch = items_to_enrich[batch_start:batch_start + BATCH_SIZE]
        batch_items = [item for _, item in batch]

        print(f"  Batch {batch_start // BATCH_SIZE + 1}: processing {len(batch)} items...")

        # Process batch concurrently
        results = await process_batch_async(client, batch_items, content_type)

        # Apply results
        for (item_idx, item), (enrichment, confidence) in zip(batch, results):
            if enrichment:
                apply_enrichment(item, enrichment, content_type)
                update_state(state, file_key, item, confidence)
                enriched_count += 1

                if confidence < 0.7:
                    log_for_review(item, enrichment, confidence, "low_confidence")
            else:
                failed_count += 1

        # Save after each batch
        save_file(filepath, data)
        save_state(state)
        print(f"    [Saved batch: {enriched_count} enriched, {failed_count} failed]")

    print(f"  Done: {enriched_count} enriched, {failed_count} failed")
    return enriched_count


def process_papers_file(
    client: Any,
    filepath: Path,
    state: dict,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False
) -> int:
    """Process the nested papers.json file."""
    if not filepath.exists():
        print(f"Skipping {filepath.name} (not found)")
        return 0

    with open(filepath) as f:
        data = json.load(f)

    if "topics" not in data:
        print(f"Skipping {filepath.name} (no topics)")
        return 0

    file_key = filepath.name
    content_type = "paper"

    # Collect all papers with their paths
    papers_to_enrich = []
    for topic in data["topics"]:
        for subtopic in topic.get("subtopics", []):
            for paper_idx, paper in enumerate(subtopic.get("papers", [])):
                if needs_enrichment(paper, state, file_key, force):
                    papers_to_enrich.append({
                        "topic_id": topic["id"],
                        "subtopic_id": subtopic["id"],
                        "paper_idx": paper_idx,
                        "paper": paper
                    })

    total_papers = sum(
        len(st.get("papers", []))
        for t in data["topics"]
        for st in t.get("subtopics", [])
    )

    print(f"\n{'='*60}")
    print(f"Processing {filepath.name}: {total_papers - len(papers_to_enrich)}/{total_papers} done, {len(papers_to_enrich)} remaining")
    print(f"{'='*60}")

    if limit:
        papers_to_enrich = papers_to_enrich[:limit]

    enriched_count = 0
    pending_save = 0

    for idx, paper_info in enumerate(papers_to_enrich):
        paper = paper_info["paper"]
        title = paper.get("title", "unknown")
        print(f"  [{idx + 1}/{len(papers_to_enrich)}] {title[:50]}...")

        if dry_run:
            enriched_count += 1
            continue

        enrichment, confidence = enrich_item(client, paper, content_type)

        if enrichment:
            apply_enrichment(paper, enrichment, content_type)
            update_state(state, file_key, paper, confidence)
            enriched_count += 1
            pending_save += 1

            if confidence < 0.7:
                log_for_review(paper, enrichment, confidence, "low_confidence")
                print(f"    [REVIEW NEEDED - confidence: {confidence:.2f}]")

            if pending_save >= SAVE_EVERY_N:
                save_file(filepath, data)
                save_state(state)
                print(f"    [Saved {enriched_count} items]")
                pending_save = 0
        else:
            print(f"    [FAILED - skipping]")

        time.sleep(REQUEST_DELAY)

    if not dry_run and pending_save > 0:
        save_file(filepath, data)
        save_state(state)
        print(f"  Final save: {enriched_count} items")

    print(f"  Done: {enriched_count} enriched")
    return enriched_count


async def process_papers_file_async(
    client: AsyncOpenAI,
    filepath: Path,
    state: dict,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False
) -> int:
    """Async version: Process the nested papers.json file with batch parallelism."""
    if not filepath.exists():
        print(f"Skipping {filepath.name} (not found)")
        return 0

    with open(filepath) as f:
        data = json.load(f)

    if "topics" not in data:
        print(f"Skipping {filepath.name} (no topics)")
        return 0

    file_key = filepath.name
    content_type = "paper"

    # Collect all papers needing enrichment
    papers_to_enrich = []
    for topic in data["topics"]:
        for subtopic in topic.get("subtopics", []):
            for paper_idx, paper in enumerate(subtopic.get("papers", [])):
                if needs_enrichment(paper, state, file_key, force):
                    papers_to_enrich.append({
                        "topic_id": topic["id"],
                        "subtopic_id": subtopic["id"],
                        "paper_idx": paper_idx,
                        "paper": paper
                    })

    total_papers = sum(
        len(st.get("papers", []))
        for t in data["topics"]
        for st in t.get("subtopics", [])
    )

    print(f"\n{'='*60}")
    print(f"Processing {filepath.name}: {total_papers - len(papers_to_enrich)}/{total_papers} done, {len(papers_to_enrich)} remaining")
    print(f"{'='*60}")

    if limit:
        papers_to_enrich = papers_to_enrich[:limit]

    if dry_run:
        print(f"  [DRY RUN] Would process {len(papers_to_enrich)} papers")
        return len(papers_to_enrich)

    enriched_count = 0
    failed_count = 0

    # Process in batches
    for batch_start in range(0, len(papers_to_enrich), BATCH_SIZE):
        batch = papers_to_enrich[batch_start:batch_start + BATCH_SIZE]
        batch_papers = [info["paper"] for info in batch]

        print(f"  Batch {batch_start // BATCH_SIZE + 1}: processing {len(batch)} papers...")

        # Process batch concurrently
        results = await process_batch_async(client, batch_papers, content_type)

        # Apply results
        for paper_info, (enrichment, confidence) in zip(batch, results):
            paper = paper_info["paper"]
            if enrichment:
                apply_enrichment(paper, enrichment, content_type)
                update_state(state, file_key, paper, confidence)
                enriched_count += 1

                if confidence < 0.7:
                    log_for_review(paper, enrichment, confidence, "low_confidence")
            else:
                failed_count += 1

        # Save after each batch
        save_file(filepath, data)
        save_state(state)
        print(f"    [Saved batch: {enriched_count} enriched, {failed_count} failed]")

    print(f"  Done: {enriched_count} enriched, {failed_count} failed")
    return enriched_count


async def run_all_async(
    client: AsyncOpenAI,
    state: dict,
    files_to_process: list[str],
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False
) -> int:
    """Run all file processing asynchronously."""
    total_enriched = 0

    for filename in files_to_process:
        filepath = DATA_DIR / filename

        if filename == PAPERS_FILE:
            total_enriched += await process_papers_file_async(
                client, filepath, state, dry_run, limit, force
            )
        else:
            total_enriched += await process_flat_file_async(
                client, filepath, state, dry_run, limit, force
            )

    return total_enriched


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Advanced LLM metadata enrichment for tech-econ.org (GPT-4o-mini)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't make API calls or save changes")
    parser.add_argument("--file", type=str,
                        help="Only process specific file (e.g., packages.json)")
    parser.add_argument("--limit", type=int,
                        help="Max items to enrich per file")
    parser.add_argument("--force", action="store_true",
                        help="Re-enrich all items (ignore content hashes)")
    parser.add_argument("--sync", action="store_true",
                        help="Use synchronous processing (slower, for debugging)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: OPENAI_API_KEY not set")
        print("Set with: export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    # Load state
    state = load_state()

    print(f"Advanced Enrichment v{SCHEMA_VERSION}")
    print(f"Model: {MODEL_VERSION} (cost: ~$0.15/1M input, $0.60/1M output)")
    print(f"Mode: {'SYNC' if args.sync else 'ASYNC'} (batch size: {BATCH_SIZE})")
    if args.force:
        print("Mode: FORCE (re-enriching all items)")
    if args.limit:
        print(f"Limit: {args.limit} items per file")
    if args.dry_run:
        print("Mode: DRY RUN")

    # Determine files to process
    if args.file:
        files_to_process = [args.file]
    else:
        files_to_process = DATA_FILES + [PAPERS_FILE]

    # Use async processing by default (much faster)
    if args.sync:
        # Legacy sync mode for debugging
        client = OpenAI(api_key=api_key) if api_key else None
        total_enriched = 0

        for filename in files_to_process:
            filepath = DATA_DIR / filename

            if filename == PAPERS_FILE:
                total_enriched += process_papers_file(
                    client, filepath, state, args.dry_run, args.limit, args.force
                )
            else:
                total_enriched += process_flat_file(
                    client, filepath, state, args.dry_run, args.limit, args.force
                )
    else:
        # Async mode (default) - 10x faster with batch processing
        client = AsyncOpenAI(api_key=api_key) if api_key else None
        total_enriched = asyncio.run(
            run_all_async(client, state, files_to_process, args.dry_run, args.limit, args.force)
        )

    # Final state save
    if not args.dry_run:
        save_state(state)

    print(f"\n{'='*60}")
    print(f"Total enriched: {total_enriched} items")
    if args.dry_run:
        print("[DRY RUN - no changes made]")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
