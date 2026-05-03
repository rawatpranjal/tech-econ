"""TypedDicts for every JSON shape the recsys pipeline owns.

Inputs:
    - none (this module is type definitions only)

Outputs:
    - importable TypedDicts that callers use for static-checking and
      runtime sanity assertions

Side effects:
    - none

Reproducibility:
    - n/a (no runtime behaviour)

Architecture rules enforced
    - A2: cross-module data flow is typed. dict[str, Any] is allowed
      only at the IO boundary; everything else uses these shapes.
    - C8: every TypedDict here is `total=False` so existing data files
      that pre-date a field don't crash readers (forward compat).

These are not pydantic models — runtime validation is the job of
scripts/validate_data.py. TypedDict gives us:
    * mypy-style static analysis when callers use it
    * runtime introspection (.__optional_keys__) for shape assertions
      in tests and ad-hoc debugging

Usage
    from lib.schemas import Package, RelatedItemsFile

    def is_package_shaped(d: dict) -> bool:
        # tolerant: every observed field is one we recognise
        known = Package.__optional_keys__ | Package.__required_keys__
        return all(k in known or k.startswith("_") for k in d)
"""

from __future__ import annotations

from typing import TypedDict


# ---------------------------------------------------------------------------
# Provenance shape (mirrors lib.data_io.OutputMeta)
# ---------------------------------------------------------------------------
class OutputMetaDict(TypedDict, total=False):
    version: str
    generated_at: str
    git_sha: str | None
    schema_version: int


# ---------------------------------------------------------------------------
# Content items.
#
# Field lists derived from the actual data files at the time this module
# was authored (2026-05-03). New fields land here as we add them; old
# ones stay forever even if dropped (a TypedDict reader is happy to see
# a missing field but will type-error on a misspelled one).
# ---------------------------------------------------------------------------
class _CommonItem(TypedDict, total=False):
    """Fields shared by all content types — every typed item carries
    most of these. Kept as a separate TypedDict so per-type schemas can
    inherit without restating."""

    # Identity
    id: str
    name: str
    url: str
    description: str

    # Categorisation
    category: str
    tags: list[str]
    type: str

    # Engagement / ranking signals
    model_score: float
    cold_start: bool
    freshness_boost: float

    # LLM-enriched metadata (added by scripts/enrich_metadata.py)
    summary: str
    best_for: list[str]
    use_cases: list[str]
    audience: str
    difficulty: str
    prerequisites: list[str]
    topic_tags: list[str]
    domain_tags: list[str]
    semantic_cluster: str
    synthetic_questions: list[str]
    primary_use_cases: list[str]
    related_concepts: list[str]
    canonical_topics: list[str]
    depth_level: str

    # Search/embedding pipeline (added by scripts/generate_embeddings.py)
    tfidf_keywords: list[str]
    embedding_text: str

    # Content-format / quality metadata
    maintenance_status: str
    implements_paper: str | bool


class Package(_CommonItem, total=False):
    docs_url: str
    github_url: str
    install: str
    language: str
    api_complexity: str
    related_packages: list[str]
    stars: int
    mentioned_tools: list[str]
    content_format: str
    speaker_expertise: str
    company_context: str
    experience_level: str
    data_modality: str
    citations: int


class PaperFlat(_CommonItem, total=False):
    title: str
    authors: list[str]
    year: int
    citations: int
    tag: str
    topic: str
    subtopic: str


class Dataset(_CommonItem, total=False):
    docs_url: str | None
    github_url: str | None


class Resource(_CommonItem, total=False):
    docs_url: str | None
    github_url: str | None


class Talk(_CommonItem, total=False):
    speaker: str
    speakers: list[str]
    duration: str
    year: int
    venue: str
    media_type: str  # "video" | "podcast"


class Book(_CommonItem, total=False):
    authors: list[str]
    year: int
    publisher: str
    isbn: str


class Career(_CommonItem, total=False):
    company: str
    role_type: str


class Community(_CommonItem, total=False):
    speaker: str
    speakers: list[str]
    venue: str
    location: str


# ---------------------------------------------------------------------------
# File shapes
# ---------------------------------------------------------------------------
class RelatedItem(TypedDict):
    id: str
    score: float


class RelatedItemsFile(TypedDict, total=False):
    """Shape of static/embeddings/related-items.json."""
    version: int
    generatedAt: str
    topK: int
    items: dict[str, list[RelatedItem]]
    _meta: OutputMetaDict


class GlobalRankingsItem(TypedDict, total=False):
    id: str
    name: str
    score: float
    cold_start: bool
    type: str


class GlobalRankingsFile(TypedDict, total=False):
    """Shape of data/global_rankings.json."""
    updated: str
    algorithm: str
    total_items: int
    observed_items: int
    cold_start_items: int
    coverage: float
    scoring: dict[str, float]
    metadata_fields: list[str]
    items: list[GlobalRankingsItem]
    _meta: OutputMetaDict


__all__ = [
    "OutputMetaDict",
    "Package",
    "PaperFlat",
    "Dataset",
    "Resource",
    "Talk",
    "Book",
    "Career",
    "Community",
    "RelatedItem",
    "RelatedItemsFile",
    "GlobalRankingsItem",
    "GlobalRankingsFile",
]
