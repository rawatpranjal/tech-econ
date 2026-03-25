#!/usr/bin/env python3
"""
Weekly Content Discovery for tech-econ.com

Searches for new packages, datasets, papers, resources, talks, books,
career guides, and community events using Brave + Tavily APIs, then
filters via relevance judgment and metadata extraction.

Modes:
  - Tavily-only: keyword relevance + heuristic extraction (no OpenAI needed)
  - Full: GPT-4o-mini relevance judgment + metadata extraction (needs OPENAI_API_KEY)

Usage:
    TAVILY_API_KEY=... python3 scripts/discover_content.py --dry-run --verbose
    BRAVE_API_KEY=... TAVILY_API_KEY=... OPENAI_API_KEY=... python3 scripts/discover_content.py
    python3 scripts/discover_content.py --dry-run --type packages --limit 5 --verbose
    python3 scripts/discover_content.py --self-test
"""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests as req_lib

# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = Path(__file__).parent.parent / "data"
QUERIES_FILE = Path(__file__).parent / "discovery_queries.json"
STATE_FILE = DATA_DIR / ".discovery_state.json"
REJECTED_FILE = DATA_DIR / ".discovery_rejected.json"
DIGEST_FILE = DATA_DIR / ".discovery_digest.html"
PAPER_STAGING_FILE = DATA_DIR / ".discovery_paper_staging.json"

LLM_MODEL = "gpt-4o-mini"

REQUIRED_FIELDS = {
    "packages": ["name", "description", "category", "url", "tags", "language"],
    "datasets": ["name", "description", "category", "url", "tags"],
    "resources": ["name", "description", "category", "url", "type", "tags"],
    "books": ["name", "author", "year", "description", "category", "type", "url", "tags"],
    "talks": ["name", "description", "category", "url", "type", "tags"],
    "papers": ["title", "authors", "year", "url", "tags", "citations"],
    "career": ["name", "description", "category", "url", "type", "tags"],
    "community": ["name", "description", "category", "url", "type"],
}

DATA_FILE_MAP = {
    "packages": "packages.json",
    "datasets": "datasets.json",
    "resources": "resources.json",
    "books": "books.json",
    "talks": "talks.json",
    "papers": "papers.json",
    "career": "career.json",
    "community": "community.json",
}

SEARCH_ENGINE_MAP = {
    "packages": "brave",
    "papers": "tavily",
    "resources": "brave",
    "datasets": "brave",
    "talks": "brave",
    "books": "brave",
    "career": "brave",
    "community": "brave",
}

# Domains to skip - aggregators, social media, news
DOMAIN_BLOCKLIST = {
    "reddit.com", "news.ycombinator.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "tiktok.com", "pinterest.com",
    "linkedin.com",
    "quora.com", "stackoverflow.com", "stackexchange.com",
    "wikipedia.org", "amazon.com", "goodreads.com",
    "google.com", "bing.com", "yahoo.com",
    "nytimes.com", "wsj.com", "bloomberg.com", "forbes.com",
    "techcrunch.com", "wired.com", "theverge.com",
    "udemy.com", "skillshare.com",
    # Content farms / low-quality SEO sites
    "wahresume.com", "geeksforgeeks.org", "javatpoint.com",
    "tutorialspoint.com", "interviewbit.com", "simplilearn.com",
    "analyticsvidhya.com", "w3schools.com", "educba.com",
    "intellipaat.com", "mygreatlearning.com", "scaler.com",
    "shiksha.com", "naukri.com", "ambitionbox.com",
}


# =============================================================================
# Search Clients
# =============================================================================

class BraveSearchClient:
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.call_count = 0

    def search(self, query: str, count: int = 10) -> list[dict]:
        headers = {
            "X-Subscription-Token": self.api_key,
            "Accept": "application/json",
        }
        params = {"q": query, "count": count}
        try:
            resp = req_lib.get(self.BASE_URL, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            self.call_count += 1
            data = resp.json()
            results = []
            for r in data.get("web", {}).get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                })
            time.sleep(1.0)
            return results
        except Exception as e:
            logging.warning(f"Brave search failed for '{query}': {e}")
            return []


class TavilySearchClient:
    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.call_count = 0

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        try:
            resp = req_lib.post(self.BASE_URL, json=payload, timeout=15)
            resp.raise_for_status()
            self.call_count += 1
            data = resp.json()
            results = []
            for r in data.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("content", r.get("description", "")),
                    "tavily_score": r.get("score", 0.0),
                })
            time.sleep(0.5)
            return results
        except Exception as e:
            logging.warning(f"Tavily search failed for '{query}': {e}")
            return []


class SearchOrchestrator:
    def __init__(self, brave: BraveSearchClient | None, tavily: TavilySearchClient | None):
        self.brave = brave
        self.tavily = tavily

    def search(self, query: str, preferred_engine: str = "brave", count: int = 10) -> list[dict]:
        results = []
        if preferred_engine == "brave" and self.brave:
            results = self.brave.search(query, count)
            if len(results) < 3 and self.tavily:
                results.extend(self.tavily.search(query, count))
        elif preferred_engine == "tavily" and self.tavily:
            results = self.tavily.search(query, count)
            if len(results) < 3 and self.brave:
                results.extend(self.brave.search(query, count))
        elif self.brave:
            results = self.brave.search(query, count)
        elif self.tavily:
            results = self.tavily.search(query, count)

        # Deduplicate by URL
        seen = set()
        unique = []
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)
        return unique


# =============================================================================
# Deduplication
# =============================================================================

class DeduplicationIndex:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.urls: set = set()
        self.names: set = set()
        self.rejected: dict = {}

    def build(self):
        for content_type, filename in DATA_FILE_MAP.items():
            filepath = self.data_dir / filename
            if not filepath.exists():
                continue
            data = _load_json(filepath)
            if content_type == "papers":
                for topic in data.get("topics", []):
                    for subtopic in topic.get("subtopics", []):
                        for paper in subtopic.get("papers", []):
                            url = paper.get("url", "")
                            if url:
                                self.urls.add(self.normalize_url(url))
                            title = paper.get("title", "")
                            if title:
                                self.names.add(title.lower().strip())
            elif isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url", "")
                    if url:
                        self.urls.add(self.normalize_url(url))
                    name = item.get("name", item.get("title", ""))
                    if name:
                        self.names.add(name.lower().strip())

        # Load rejection cache
        if REJECTED_FILE.exists():
            self.rejected = _load_json(REJECTED_FILE)
            self._prune_rejections()

    @staticmethod
    def normalize_url(url: str) -> str:
        parsed = urlparse(url.strip())
        host = parsed.hostname or ""
        host = host.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        query = parsed.query if "arxiv.org" in host else ""
        return urlunparse(("", host, path, "", query, "")).lstrip("/")

    def is_duplicate(self, url: str, name: str) -> tuple[bool, str]:
        norm_url = self.normalize_url(url)
        if norm_url in self.urls:
            return True, "URL already exists"
        name_lower = name.lower().strip()
        for existing in self.names:
            if SequenceMatcher(None, name_lower, existing).ratio() > 0.85:
                return True, f"Similar name: '{existing}'"
        return False, ""

    def is_rejected(self, url: str) -> bool:
        return self.normalize_url(url) in self.rejected

    def is_blocked_domain(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        for blocked in DOMAIN_BLOCKLIST:
            if blocked in host:
                return True
        return False

    def add_rejection(self, url: str, score: float, reason: str):
        self.rejected[self.normalize_url(url)] = {
            "rejected_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "score": score,
            "reason": reason,
            "ttl_weeks": 8,
        }

    def mark_added(self, url: str, name: str):
        self.urls.add(self.normalize_url(url))
        if name:
            self.names.add(name.lower().strip())

    def save_rejections(self):
        _save_json(REJECTED_FILE, self.rejected)

    def _prune_rejections(self):
        now = datetime.now(timezone.utc)
        to_remove = []
        for url, info in self.rejected.items():
            try:
                rejected_at = datetime.strptime(info["rejected_at"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                ttl = info.get("ttl_weeks", 8)
                if (now - rejected_at).days > ttl * 7:
                    to_remove.append(url)
            except (KeyError, ValueError):
                to_remove.append(url)
        for url in to_remove:
            del self.rejected[url]


# =============================================================================
# LLM Relevance Judge
# =============================================================================

RELEVANCE_PROMPT = """You are a content curator for tech-econ.com, a curated directory for tech economists, data scientists, and applied researchers.

The site covers: econometrics, causal inference, A/B testing, ML for economics, platform economics, pricing, marketplaces, experimentation, applied statistics.

Score each candidate for relevance. Return a JSON array with one object per candidate:
{{"index": 1, "relevance_score": 8, "suggested_type": "package", "reasoning": "..."}}

REJECT (score < 7): general CS not economics-focused, pure software engineering, low-quality/promotional, paywalled without value.
ACCEPT (score >= 7): tools for economists, causal inference methods, experimentation, pricing, quality datasets, practitioner tutorials, reputable papers.

Candidates:
{candidates}

Return ONLY a JSON array."""

class RelevanceJudge:
    BATCH_SIZE = 5

    def __init__(self, openai_client):
        self.client = openai_client
        self.call_count = 0
        self.total_tokens = 0

    def judge_batch(self, candidates: list[dict]) -> list[dict]:
        numbered = "\n".join(
            f'{i+1}. Title: "{c["title"]}" | URL: {c["url"]} | Snippet: "{c.get("description", "")[:200]}"'
            for i, c in enumerate(candidates)
        )
        prompt = RELEVANCE_PROMPT.format(candidates=numbered)

        for attempt in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                self.call_count += 1
                self.total_tokens += resp.usage.total_tokens if resp.usage else 0
                text = resp.choices[0].message.content
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    scores = parsed.get("results", parsed.get("candidates", list(parsed.values())[0]))
                else:
                    scores = parsed

                for score_item in scores:
                    idx = score_item.get("index", 0) - 1
                    if 0 <= idx < len(candidates):
                        candidates[idx]["relevance_score"] = score_item.get("relevance_score", 0)
                        candidates[idx]["reasoning"] = score_item.get("reasoning", "")
                        candidates[idx]["suggested_type"] = score_item.get("suggested_type", "")
                return candidates
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logging.warning(f"LLM parse error (attempt {attempt+1}): {e}")
                if attempt == 1:
                    for c in candidates:
                        c.setdefault("relevance_score", 0)
                        c.setdefault("reasoning", "parse error")
        return candidates

    def judge_all(self, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
        accepted, rejected = [], []
        for i in range(0, len(candidates), self.BATCH_SIZE):
            batch = candidates[i:i + self.BATCH_SIZE]
            self.judge_batch(batch)
            for c in batch:
                if c.get("relevance_score", 0) >= 7:
                    accepted.append(c)
                else:
                    rejected.append(c)
        return accepted, rejected


# =============================================================================
# Keyword-based Relevance Judge (no LLM needed)
# =============================================================================

RELEVANCE_KEYWORDS = {
    "high": [
        "econometrics", "causal inference", "causal-inference", "a/b test",
        "ab test", "experimentation", "diff-in-diff", "difference-in-difference",
        "instrumental variable", "regression discontinuity", "synthetic control",
        "treatment effect", "propensity score", "panel data", "fixed effect",
        "platform economics", "marketplace", "pricing", "auction",
        "applied economics", "tech economist", "data scientist",
        "randomized control", "rct", "double machine learning",
        "heterogeneous treatment", "uplift model", "counterfactual",
    ],
    "medium": [
        "economics", "economist", "statistical", "statistics",
        "machine learning", "regression", "bayesian", "time series",
        "natural experiment", "quasi-experiment", "observational study",
        "demand estimation", "supply chain", "market design",
        "mechanism design", "game theory", "industrial organization",
        "labor economics", "policy evaluation", "impact evaluation",
        "survival analysis", "hazard model", "duration model",
        "matching", "weighting", "bootstrap", "inference",
        "python", "r package", "stata", "jupyter",
    ],
}


class KeywordRelevanceJudge:
    """Scores candidates using Tavily relevance score + keyword matching."""

    def __init__(self):
        self.call_count = 0
        self.total_tokens = 0

    def judge_batch(self, candidates: list[dict]) -> list[dict]:
        for c in candidates:
            text = f"{c.get('title', '')} {c.get('description', '')}".lower()
            high_hits = sum(1 for kw in RELEVANCE_KEYWORDS["high"] if kw in text)
            medium_hits = sum(1 for kw in RELEVANCE_KEYWORDS["medium"] if kw in text)
            kw_score = min((high_hits * 2.0) + (medium_hits * 1.0), 10.0)
            tavily_score = c.get("tavily_score", 0.0) * 10
            combined = (kw_score * 0.6) + (tavily_score * 0.4)
            c["relevance_score"] = round(combined, 1)
            c["high_keyword_hits"] = high_hits
            c["reasoning"] = f"keyword={kw_score:.1f}(high={high_hits},med={medium_hits}), tavily={tavily_score:.1f}"
        return candidates

    def judge_all(self, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
        accepted, rejected = [], []
        self.judge_batch(candidates)
        for c in candidates:
            if c.get("relevance_score", 0) >= 5.0 and c.get("high_keyword_hits", 0) >= 1:
                accepted.append(c)
            else:
                rejected.append(c)
        return accepted, rejected


# =============================================================================
# Heuristic Metadata Extractor (no LLM needed)
# =============================================================================

TYPE_INFERENCE = {
    "resources": {
        "default": "Article",
        "url_patterns": {
            "youtube.com": "Video", "youtu.be": "Video",
            "substack.com": "Newsletter", "medium.com": "Blog",
            "github.io": "Tutorial",
            "coursera.org": "Course", "edx.org": "Course",
        },
        "text_patterns": {
            "tutorial": "Tutorial", "course": "Course",
            "guide": "Guide", "blog": "Blog",
            "newsletter": "Newsletter", "podcast": "Podcast",
        },
    },
    "talks": {
        "default": "Video",
        "url_patterns": {
            "youtube.com": "Video", "youtu.be": "Video",
            "spotify.com": "Podcast", "apple.com/podcast": "Podcast",
        },
        "text_patterns": {
            "interview": "Interview", "podcast": "Podcast",
            "lecture": "Video", "keynote": "Video",
            "workshop": "Video", "panel": "Video",
            "webinar": "Video",
        },
    },
    "community": {
        "default": "Conference",
        "url_patterns": {
            "meetup.com": "Meetup", "slack.com": "Slack Community",
            "discord.gg": "Discord Server",
        },
        "text_patterns": {
            "conference": "Annual Conference",
            "meetup": "Meetup", "summit": "Annual Summit",
            "seminar": "Academic", "lab": "Tech Lab",
        },
    },
    "career": {
        "default": "Article",
        "url_patterns": {"youtube.com": "Video"},
        "text_patterns": {"guide": "Guide", "course": "Course", "job board": "Job Board"},
    },
}


class HeuristicMetadataExtractor:
    """Extracts metadata from search results without LLM calls."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.categories = self._load_categories()
        self.call_count = 0

    def _load_categories(self) -> dict[str, list[str]]:
        cats = {}
        for ctype, filename in DATA_FILE_MAP.items():
            if ctype == "papers":
                continue
            filepath = self.data_dir / filename
            if not filepath.exists():
                continue
            data = _load_json(filepath)
            if isinstance(data, list):
                cats[ctype] = sorted(set(
                    item.get("category", "") for item in data
                    if isinstance(item, dict) and item.get("category")
                ))
        return cats

    def _guess_category(self, text: str, content_type: str, search_category: str = "") -> str:
        cats = self.categories.get(content_type, [])
        if not cats:
            return "General"
        if search_category and search_category != "_generic" and search_category in cats:
            return search_category
        text_lower = text.lower()
        best, best_score = cats[0], 0
        for cat in cats:
            cat_words = [w for w in cat.lower().split() if len(w) > 2]
            score = sum(1 for word in cat_words if word in text_lower)
            if score > best_score:
                best, best_score = cat, score
        return best

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return tag.lower().strip().replace(" ", "-").replace("/", "-")

    def _extract_tags(self, text: str, url: str = "") -> list[str]:
        text_lower = text.lower()
        tags = []
        seen = set()
        url_lower = url.lower()
        if "github.com" in url_lower:
            parts = urlparse(url).path.strip("/").split("/")
            if len(parts) >= 2:
                repo = parts[1].lower().replace("_", "-")
                if len(repo) > 2 and repo not in seen:
                    tags.append(repo)
                    seen.add(repo)
        elif "pypi.org" in url_lower or "cran.r-project.org" in url_lower:
            parts = urlparse(url).path.strip("/").split("/")
            if parts:
                pkg = parts[-1].lower()
                if pkg and pkg not in seen:
                    tags.append(pkg)
                    seen.add(pkg)
        all_kw = RELEVANCE_KEYWORDS["high"] + RELEVANCE_KEYWORDS["medium"]
        for kw in all_kw:
            if kw in text_lower and len(tags) < 5:
                normalized = self._normalize_tag(kw)
                if normalized not in seen:
                    tags.append(normalized)
                    seen.add(normalized)
        return tags[:5] if tags else ["uncategorized"]

    def _guess_language(self, text: str) -> str:
        text_lower = text.lower()
        patterns = [
            (r'\bpython\b|pypi|\.py\b', "Python"),
            (r'\br[\s-](?:package|library)|cran\b|r-project', "R"),
            (r'\bjulia\b', "Julia"),
            (r'\bstata\b', "Stata"),
            (r'\bmatlab\b', "MATLAB"),
            (r'\bjavascript\b|\.js\b|npm\b', "JavaScript"),
            (r'\bjava\b(?!script)', "Java"),
            (r'\bc\+\+\b|cpp\b', "C++"),
        ]
        for pattern, lang in patterns:
            if re.search(pattern, text_lower):
                return lang
        return "Python"

    def _guess_type(self, text: str, url: str, content_type: str) -> str:
        config = TYPE_INFERENCE.get(content_type)
        if not config:
            return "Article"
        url_lower = url.lower()
        text_lower = text.lower()
        for pattern, type_val in config.get("url_patterns", {}).items():
            if pattern in url_lower:
                return type_val
        for pattern, type_val in config.get("text_patterns", {}).items():
            if pattern in text_lower:
                return type_val
        return config["default"]

    def extract(self, candidate: dict, content_type: str) -> dict | None:
        title = candidate.get("title", "").strip()
        url = candidate.get("url", "")
        desc = candidate.get("description", "").strip()
        if not title or not url:
            return None

        text = f"{title} {desc}"
        search_cat = candidate.get("search_category", "")
        category = self._guess_category(text, content_type, search_cat)
        tags = self._extract_tags(text, url)
        self.call_count += 1

        # Reject GitHub topic/awesome-list pages (not real packages)
        if content_type == "packages":
            url_lower = url.lower()
            if "/topics/" in url_lower or "/topics?" in url_lower or url_lower.endswith("/topics"):
                return None
            if "awesome-list" in url_lower or "awesome-" in title.lower():
                return None

        if content_type == "papers":
            return {
                "title": title,
                "authors": "",
                "year": datetime.now().year,
                "url": url,
                "tags": tags,
                "citations": 0,
                "tag": None,
                "description": desc[:300] if desc else title,
            }
        elif content_type == "packages":
            return {
                "name": title,
                "description": desc[:300] if desc else title,
                "category": category,
                "url": url,
                "tags": tags,
                "language": self._guess_language(text),
                "github_url": url if "github.com" in url else None,
                "install": "",
            }
        elif content_type == "books":
            return {
                "name": title,
                "author": "",
                "year": datetime.now().year,
                "description": desc[:300] if desc else title,
                "category": category,
                "type": "Book",
                "url": url,
                "tags": tags,
            }
        else:
            item = {
                "name": title,
                "description": desc[:300] if desc else title,
                "category": category,
                "url": url,
                "tags": tags,
            }
            if content_type in ("resources", "talks", "career", "community"):
                item["type"] = self._guess_type(text, url, content_type)
            return item


# =============================================================================
# Post-Extraction Validation
# =============================================================================

VALID_TYPES = {
    "resources": {"Article", "Blog", "Book", "Course", "Guide", "Newsletter",
                  "Online Book", "Podcast", "Tool", "Tutorial", "Video"},
    "talks": {"Video", "Interview", "Podcast", "Lecture", "Conference Talk",
              "Workshop", "Panel", "Tutorial", "Talk", "Seminar",
              "YouTube Channel", "Presentation", "Video Series"},
    "community": {"Conference", "Annual Conference", "Workshop", "Meetup", "Summit",
                  "Academic", "Tech Lab", "Research Center", "Blog",
                  "Slack Community", "Discord Server", "Annual Summit", "Annual Workshop"},
    "career": {"Article", "Blog", "Book", "Career Portal", "Community", "Conference",
               "Course", "Database", "Documentation", "GitHub", "Guide", "Job Board",
               "Newsletter", "Podcast", "Practice", "Research", "Tool", "Video"},
}


def validate_item(item: dict, content_type: str) -> tuple[bool, list[str]]:
    """Validate an extracted item before writing. Returns (is_valid, list_of_issues)."""
    issues = []
    required = REQUIRED_FIELDS.get(content_type, [])

    for field in required:
        val = item.get(field)
        if val is None or val == "" or val == []:
            issues.append(f"missing required: {field}")

    url = item.get("url", "")
    if url:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.hostname:
            issues.append(f"invalid URL: {url[:60]}")

    name = item.get("name", item.get("title", ""))
    if len(name) < 3:
        issues.append(f"name too short: '{name}'")
    if len(name) > 200:
        issues.append(f"name too long: {len(name)} chars")

    tags = item.get("tags", [])
    if not isinstance(tags, list):
        issues.append(f"tags is not a list: {type(tags)}")

    if content_type in VALID_TYPES:
        item_type = item.get("type", "")
        if item_type and item_type not in VALID_TYPES[content_type]:
            issues.append(f"invalid type '{item_type}' for {content_type}")

    if content_type == "papers":
        year = item.get("year", 0)
        if year and (year < 1950 or year > datetime.now().year + 1):
            issues.append(f"suspicious year: {year}")

    if content_type == "community":
        item_type = item.get("type", "")
        name_lower = item.get("name", "").lower()
        if item_type == "Workshop" or "workshop" in name_lower:
            issues.append("workshops excluded from community")

    is_valid = not any("missing required" in i or "excluded" in i for i in issues)
    return is_valid, issues


# =============================================================================
# Metadata Extraction (LLM-based)
# =============================================================================

TEMPLATES = {
    "packages": '{"name": "", "description": "", "category": "", "url": "", "tags": [], "language": "", "github_url": null, "install": ""}',
    "datasets": '{"name": "", "description": "", "category": "", "url": "", "tags": [], "github_url": null}',
    "resources": '{"name": "", "description": "", "category": "", "url": "", "type": "", "tags": [], "level": ""}',
    "books": '{"name": "", "author": "", "year": 2026, "description": "", "category": "", "type": "Book", "url": "", "tags": []}',
    "talks": '{"name": "", "description": "", "category": "", "url": "", "type": "", "tags": []}',
    "papers": '{"title": "", "authors": "", "year": 2026, "url": "", "tags": [], "citations": 0, "tag": null, "description": ""}',
    "career": '{"name": "", "description": "", "category": "", "url": "", "type": "Article", "tags": []}',
    "community": '{"name": "", "description": "", "category": "", "url": "", "type": ""}',
}

EXTRACTION_PROMPT = """Extract metadata for this {content_type} to add to tech-econ.com.

Source:
- Title: {title}
- URL: {url}
- Description: {description}

Fill this JSON template:
{template}

VALID CATEGORIES:
{categories}

RULES:
- "category" MUST be from the list above (pick closest match)
- "tags": 3-5 lowercase hyphenated (e.g. "causal-inference")
- "description": 1-2 accurate sentences
- DO NOT invent authors, years, statistics, or features not in the source
- "url" MUST be exactly: {url}
{extra_rules}

Return ONLY valid JSON."""

PAPER_EXTRA = """- "citations": 0 if unknown
- "year": extract from URL/title or use current year
- "tag": one of [Classic, SOTA, Industry, Survey, Methodological] or null
- Also include "topic_id" and "subtopic_id" from:
{paper_topics}"""


class MetadataExtractor:
    def __init__(self, openai_client, data_dir: Path):
        self.client = openai_client
        self.data_dir = data_dir
        self.categories = self._load_categories()
        self.paper_topics = self._load_paper_topics()
        self.call_count = 0

    def _load_categories(self) -> dict[str, list[str]]:
        cats = {}
        for ctype, filename in DATA_FILE_MAP.items():
            if ctype == "papers":
                continue
            filepath = self.data_dir / filename
            if not filepath.exists():
                continue
            data = _load_json(filepath)
            if isinstance(data, list):
                cats[ctype] = sorted(set(
                    item.get("category", "") for item in data
                    if isinstance(item, dict) and item.get("category")
                ))
        return cats

    def _load_paper_topics(self) -> str:
        filepath = self.data_dir / "papers.json"
        if not filepath.exists():
            return ""
        data = _load_json(filepath)
        lines = []
        for topic in data.get("topics", []):
            tid = topic.get("id", "")
            for st in topic.get("subtopics", []):
                sid = st.get("id", "")
                lines.append(f"  {tid} > {sid}")
        return "\n".join(lines)

    def extract(self, candidate: dict, content_type: str) -> dict | None:
        template = TEMPLATES.get(content_type, "{}")
        categories = "\n".join(f"  - {c}" for c in self.categories.get(content_type, []))
        extra_rules = ""
        if content_type == "papers":
            extra_rules = PAPER_EXTRA.format(paper_topics=self.paper_topics)

        prompt = EXTRACTION_PROMPT.format(
            content_type=content_type,
            title=candidate.get("title", ""),
            url=candidate["url"],
            description=candidate.get("description", "")[:500],
            template=template,
            categories=categories if categories else "(use your best judgment)",
            extra_rules=extra_rules,
        )

        for attempt in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                self.call_count += 1
                text = resp.choices[0].message.content
                item = json.loads(text)

                # Force correct URL
                item["url"] = candidate["url"]

                # Validate required fields
                required = REQUIRED_FIELDS.get(content_type, [])
                missing = [f for f in required if f not in item or not item[f]]
                if missing:
                    logging.warning(f"Missing fields {missing} for {candidate['url']}")
                    if attempt == 0:
                        continue
                    return None

                # Ensure tags is a list
                if isinstance(item.get("tags"), str):
                    item["tags"] = [t.strip() for t in item["tags"].split(",")]

                return item
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"Extraction parse error (attempt {attempt+1}): {e}")
        return None


# =============================================================================
# Data Writers
# =============================================================================

def _load_json(filepath: Path):
    with open(filepath) as f:
        return json.load(f)


def _save_json(filepath: Path, data):
    """Atomic JSON write: write to temp file, then rename."""
    dir_path = filepath.parent
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dir_path, suffix=".tmp", delete=False
        ) as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.write("\n")
            tmp_path = Path(tmp.name)
        tmp_path.replace(filepath)
    except Exception:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)
        raise


def append_to_flat_json(item: dict, content_type: str, data_dir: Path) -> bool:
    filepath = data_dir / DATA_FILE_MAP[content_type]
    data = _load_json(filepath)
    if isinstance(data, list):
        data.append(item)
        _save_json(filepath, data)
        return True
    logging.error(f"{filepath} is not a JSON array")
    return False


def append_to_papers(item: dict, topic_id: str, subtopic_id: str, data_dir: Path) -> str:
    filepath = data_dir / "papers.json"
    data = _load_json(filepath)
    for topic in data.get("topics", []):
        if topic.get("id") == topic_id:
            for subtopic in topic.get("subtopics", []):
                if subtopic.get("id") == subtopic_id:
                    subtopic.setdefault("papers", []).append(item)
                    _save_json(filepath, data)
                    return "added"

    # Stage for manual review
    staging = _load_json(PAPER_STAGING_FILE) if PAPER_STAGING_FILE.exists() else []
    staging.append({"item": item, "topic_id": topic_id, "subtopic_id": subtopic_id})
    _save_json(PAPER_STAGING_FILE, staging)
    return "staged"


# =============================================================================
# Email Digest
# =============================================================================

def generate_digest(results: dict) -> str:
    added = results.get("added", [])
    rejected = results.get("rejected", [])
    staged = results.get("staged", [])
    errors = results.get("errors", [])
    api = results.get("api_usage", {})
    dry = results.get("dry_run", False)

    by_type = {}
    for item in added:
        t = item.get("type", "unknown")
        by_type.setdefault(t, []).append(item)

    sections = []

    sections.append(f"""
<h1>Weekly Discovery {"(DRY RUN)" if dry else "Report"}</h1>
<p>Run: {results.get("run_date", "")[:19]} UTC | Duration: {results.get("duration_seconds", 0)}s</p>
<hr>""")

    sections.append(f"<h2>Items Added ({len(added)} total)</h2>")
    if not added:
        sections.append("<p><em>No items added this week.</em></p>")
    for content_type, items in sorted(by_type.items()):
        sections.append(f"<h3>{content_type.title()} ({len(items)})</h3><ul>")
        for item in items:
            meta = item.get("item", {})
            name = meta.get("name", meta.get("title", "?"))
            cat = meta.get("category", "")
            url = item.get("url", "")
            sections.append(f'<li><strong>{name}</strong> [{cat}]<br><a href="{url}">{url}</a></li>')
        sections.append("</ul>")

    top_rejected = sorted(rejected, key=lambda r: r.get("relevance_score", 0), reverse=True)[:10]
    if top_rejected:
        sections.append(f"<h2>Top Rejected ({len(rejected)} total)</h2>")
        sections.append('<table border="1" cellpadding="4"><tr><th>URL</th><th>Score</th><th>Reason</th></tr>')
        for r in top_rejected:
            sections.append(f'<tr><td>{r.get("url", "")[:60]}</td><td>{r.get("relevance_score", 0)}/10</td><td>{r.get("reasoning", "")}</td></tr>')
        sections.append("</table>")

    if staged:
        sections.append(f"<h2>Papers Pending Review ({len(staged)})</h2><ul>")
        for s in staged:
            meta = s.get("item", s) if isinstance(s, dict) else s
            sections.append(f'<li>{meta.get("title", "?")}</li>')
        sections.append("</ul>")

    sections.append(f"""
<h2>API Usage</h2>
<ul>
<li>Brave: {api.get("brave", 0)} calls</li>
<li>Tavily: {api.get("tavily", 0)} calls</li>
<li>OpenAI: {api.get("openai_calls", 0)} calls (~${api.get("openai_cost_usd", 0):.3f})</li>
</ul>""")

    if errors:
        sections.append(f"<h2>Errors ({len(errors)})</h2><ul>")
        for e in errors:
            sections.append(f"<li>{e}</li>")
        sections.append("</ul>")

    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #1a1a2e; }} h2 {{ color: #16213e; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
table {{ border-collapse: collapse; width: 100%; }} th {{ background: #f0f0f0; }}
a {{ color: #0066cc; }}
</style></head><body>{body}</body></html>"""


# =============================================================================
# State Management
# =============================================================================

def _default_state() -> dict:
    return {
        "schema_version": "1.0",
        "total_runs": 0,
        "total_items_added": 0,
        "total_cost_usd": 0.0,
        "query_rotation_week": 0,
        "api_usage_monthly": {"brave": 0, "tavily": 0, "month": ""},
        "history": [],
        "recently_added_urls": [],
    }


def load_state() -> dict:
    if not STATE_FILE.exists():
        return _default_state()
    try:
        state = _load_json(STATE_FILE)
        if not isinstance(state, dict) or "schema_version" not in state:
            raise ValueError("Invalid state structure")
        return state
    except (json.JSONDecodeError, ValueError) as e:
        logging.warning(f"State file corrupted ({e}), backing up and resetting")
        backup = STATE_FILE.with_suffix(f".json.bak.{int(time.time())}")
        STATE_FILE.rename(backup)
        return _default_state()


def save_state(state: dict):
    _save_json(STATE_FILE, state)


def get_weekly_queries(queries_config: dict, content_type: str, week_number: int) -> list[dict]:
    type_queries = queries_config.get(content_type, {})
    budget = queries_config.get("_meta", {}).get("budget", {}).get(content_type, {})
    queries_per_week = budget.get("queries_per_week", 10)

    all_queries = []
    for category, query_list in type_queries.items():
        if category.startswith("_") and category != "_generic":
            continue
        if not isinstance(query_list, list):
            continue
        cat_label = category if category != "_generic" else "_generic"
        for q in query_list:
            all_queries.append({"query": q, "category": cat_label})

    if not all_queries:
        return []

    start = (week_number * queries_per_week) % len(all_queries)
    selected = []
    for i in range(min(queries_per_week, len(all_queries))):
        idx = (start + i) % len(all_queries)
        selected.append(all_queries[idx])
    return selected


# =============================================================================
# Pipeline
# =============================================================================

def process_content_type(
    content_type: str,
    queries: list[dict],
    search: SearchOrchestrator,
    dedup: DeduplicationIndex,
    judge,
    extractor,
    data_dir: Path,
    limit: int,
    dry_run: bool,
) -> dict:
    result = {"added": [], "rejected": [], "staged": [], "errors": []}
    preferred_engine = SEARCH_ENGINE_MAP.get(content_type, "brave")

    # 1. Search
    all_results = []
    for q in queries:
        try:
            results = search.search(q["query"], preferred_engine=preferred_engine)
            for r in results:
                r["search_query"] = q["query"]
                r["search_category"] = q["category"]
            all_results.extend(results)
        except Exception as e:
            result["errors"].append(f"Search '{q['query']}': {e}")

    logging.info(f"  {content_type}: {len(all_results)} raw results from {len(queries)} queries")

    # 2. Dedup + domain filter
    candidates = []
    seen_urls = set()
    for r in all_results:
        url = r.get("url", "")
        if not url:
            continue
        norm = DeduplicationIndex.normalize_url(url)
        if norm in seen_urls:
            continue
        seen_urls.add(norm)
        if dedup.is_blocked_domain(url):
            continue
        is_dup, _ = dedup.is_duplicate(url, r.get("title", ""))
        if is_dup:
            continue
        if dedup.is_rejected(url):
            continue
        candidates.append(r)

    logging.info(f"  {content_type}: {len(candidates)} candidates after dedup")
    if not candidates:
        return result

    # 3. Relevance judgment
    accepted, rejected = judge.judge_all(candidates)
    for r in rejected:
        dedup.add_rejection(r["url"], r.get("relevance_score", 0), r.get("reasoning", ""))
        result["rejected"].append(r)

    logging.info(f"  {content_type}: {len(accepted)} accepted, {len(rejected)} rejected")

    # 4. Extract metadata + validate + write
    added_count = 0
    for candidate in accepted:
        if added_count >= limit:
            break
        try:
            item = extractor.extract(candidate, content_type)
            if item is None:
                result["errors"].append(f"Extraction failed: {candidate['url']}")
                continue

            is_valid, issues = validate_item(item, content_type)
            if not is_valid:
                result["errors"].append(f"Validation failed {candidate['url']}: {issues}")
                continue
            if issues:
                logging.warning(f"  Validation warnings {candidate['url']}: {issues}")

            if dry_run:
                result["added"].append({"item": item, "type": content_type, "url": candidate["url"]})
                added_count += 1
                continue

            if content_type == "papers":
                topic_id = item.pop("topic_id", None)
                subtopic_id = item.pop("subtopic_id", None)
                if topic_id and subtopic_id:
                    status = append_to_papers(item, topic_id, subtopic_id, data_dir)
                    if status == "staged":
                        result["staged"].append(item)
                    else:
                        result["added"].append({"item": item, "type": "paper", "url": candidate["url"]})
                        dedup.mark_added(candidate["url"], item.get("title", ""))
                        added_count += 1
                else:
                    result["staged"].append(item)
            else:
                if append_to_flat_json(item, content_type, data_dir):
                    result["added"].append({"item": item, "type": content_type, "url": candidate["url"]})
                    dedup.mark_added(candidate["url"], item.get("name", ""))
                    added_count += 1
        except Exception as e:
            result["errors"].append(f"Add failed {candidate['url']}: {e}")

    return result


# =============================================================================
# Self-Test
# =============================================================================

def run_self_test() -> int:
    """End-to-end pipeline test with mock data. Returns 0 on success, 1 on failure."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("=" * 60)
    logging.info("SELF-TEST: Running pipeline validation with mock data")
    logging.info("=" * 60)
    passed = 0
    failed = 0

    # 1. DeduplicationIndex
    logging.info("Test 1: DeduplicationIndex...")
    try:
        dedup = DeduplicationIndex(DATA_DIR)
        dedup.build()
        assert len(dedup.urls) > 0, "Dedup index has no URLs"
        assert DeduplicationIndex.normalize_url("https://www.github.com/foo/bar/") == "github.com/foo/bar"
        is_dup, _ = dedup.is_duplicate("https://ax.dev", "Ax (Meta Adaptive Experimentation)")
        assert is_dup, "Should detect existing item as duplicate"
        is_dup, _ = dedup.is_duplicate("https://example.com/new-tool-99999", "Brand New Fake Tool 99999")
        assert not is_dup, "Should not flag novel item as duplicate"
        logging.info("  PASS: DeduplicationIndex (%d URLs, %d names)", len(dedup.urls), len(dedup.names))
        passed += 1
    except Exception as e:
        logging.error("  FAIL: DeduplicationIndex: %s", e)
        failed += 1

    # 2. KeywordRelevanceJudge
    logging.info("Test 2: KeywordRelevanceJudge...")
    try:
        judge = KeywordRelevanceJudge()
        mock = [
            {"title": "New Python Causal Inference Library", "url": "https://example.com/1",
             "description": "A package for difference-in-differences and treatment effect estimation", "tavily_score": 0.8},
            {"title": "Best Pizza Recipes 2026", "url": "https://example.com/2",
             "description": "Top pizza recipes from around the world", "tavily_score": 0.9},
        ]
        accepted, rejected = judge.judge_all(deepcopy(mock))
        assert len(accepted) >= 1, f"Should accept causal inference item, got {len(accepted)}"
        assert any("pizza" in r.get("title", "").lower() for r in rejected), "Should reject pizza"
        logging.info("  PASS: KeywordRelevanceJudge (accepted=%d, rejected=%d)", len(accepted), len(rejected))
        passed += 1
    except Exception as e:
        logging.error("  FAIL: KeywordRelevanceJudge: %s", e)
        failed += 1

    # 3. HeuristicMetadataExtractor
    logging.info("Test 3: HeuristicMetadataExtractor...")
    try:
        extractor = HeuristicMetadataExtractor(DATA_DIR)
        item = extractor.extract({"title": "econml - Causal ML", "url": "https://github.com/py-why/econml",
            "description": "Python package for heterogeneous treatment effects", "search_category": "Causal Inference (ML)"}, "packages")
        assert item is not None and item["language"] == "Python" and item["github_url"] is not None
        logging.info("  PASS: Extraction produced: %s", item["name"])
        passed += 1
    except Exception as e:
        logging.error("  FAIL: HeuristicMetadataExtractor: %s", e)
        failed += 1

    # 4. validate_item
    logging.info("Test 4: validate_item...")
    try:
        good = {"name": "Test Pkg", "url": "https://example.com", "category": "General",
                "description": "A test package", "tags": ["test"], "language": "Python"}
        valid, _ = validate_item(good, "packages")
        assert valid, "Good item should be valid"
        bad = {"name": "", "url": "", "category": "", "tags": [], "language": ""}
        valid, issues = validate_item(bad, "packages")
        assert not valid and len(issues) > 0
        logging.info("  PASS: validate_item")
        passed += 1
    except Exception as e:
        logging.error("  FAIL: validate_item: %s", e)
        failed += 1

    # 5. Type inference
    logging.info("Test 5: Type inference...")
    try:
        ext = HeuristicMetadataExtractor(DATA_DIR)
        t = ext.extract({"title": "Talk", "url": "https://youtube.com/watch?v=123", "description": "causal ML"}, "talks")
        assert t["type"] == "Video", f"YouTube should be Video, got {t['type']}"
        r = ext.extract({"title": "Newsletter", "url": "https://causalinf.substack.com/", "description": "econ"}, "resources")
        assert r["type"] == "Newsletter", f"Substack should be Newsletter, got {r['type']}"
        logging.info("  PASS: Type inference")
        passed += 1
    except Exception as e:
        logging.error("  FAIL: Type inference: %s", e)
        failed += 1

    # 6. Atomic write round-trip
    logging.info("Test 6: Atomic write...")
    try:
        tf = DATA_DIR / ".self_test_tmp.json"
        td = [{"test": True}]
        _save_json(tf, td)
        assert _load_json(tf) == td
        tf.unlink(missing_ok=True)
        logging.info("  PASS: Atomic write")
        passed += 1
    except Exception as e:
        logging.error("  FAIL: Atomic write: %s", e)
        failed += 1

    # 7. Paper handling
    logging.info("Test 7: Paper staging...")
    try:
        ext = HeuristicMetadataExtractor(DATA_DIR)
        p = ext.extract({"title": "Treatment Effects", "url": "https://arxiv.org/abs/2401.12345", "description": "interference"}, "papers")
        assert p is not None and "topic_id" not in p and "subtopic_id" not in p
        logging.info("  PASS: Papers have no topic_id")
        passed += 1
    except Exception as e:
        logging.error("  FAIL: Paper staging: %s", e)
        failed += 1

    # 8. Language detection
    logging.info("Test 8: Language detection...")
    try:
        ext = HeuristicMetadataExtractor(DATA_DIR)
        g = ext.extract({"title": "Better Tools", "url": "https://example.com/tools", "description": "for researchers"}, "packages")
        assert g["language"] == "Python", f"Generic should default Python, got {g['language']}"
        r = ext.extract({"title": "R Package for DiD", "url": "https://cran.r-project.org/package=did2s", "description": "R library"}, "packages")
        assert r["language"] == "R", f"CRAN should detect R, got {r['language']}"
        logging.info("  PASS: Language detection")
        passed += 1
    except Exception as e:
        logging.error("  FAIL: Language detection: %s", e)
        failed += 1

    logging.info("=" * 60)
    logging.info("SELF-TEST: %d PASSED, %d FAILED", passed, failed)
    logging.info("=" * 60)
    return 0 if failed == 0 else 1


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Discover new content for tech-econ.com")
    parser.add_argument("--dry-run", action="store_true", help="Search and score, don't write")
    parser.add_argument("--type", type=str, help="Single content type to process")
    parser.add_argument("--limit", type=int, default=15, help="Max items to add total (default: 15)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--self-test", action="store_true", help="Run pipeline self-test with mock data (no API keys needed)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.self_test:
        sys.exit(run_self_test())

    # API keys
    brave_key = os.environ.get("BRAVE_API_KEY")
    tavily_key = os.environ.get("TAVILY_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not brave_key and not tavily_key:
        logging.error("At least one of BRAVE_API_KEY or TAVILY_API_KEY is required")
        sys.exit(1)

    use_llm = bool(openai_key)
    openai_client = None
    if use_llm:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=openai_key)
        except ImportError:
            logging.warning("openai package not installed — falling back to keyword-based judging")
            use_llm = False

    if not use_llm:
        logging.info("Running in Tavily-only mode (keyword relevance + heuristic extraction)")

    brave = BraveSearchClient(brave_key) if brave_key else None
    tavily = TavilySearchClient(tavily_key) if tavily_key else None
    search_orch = SearchOrchestrator(brave, tavily)

    # Load config
    queries_config = _load_json(QUERIES_FILE)
    state = load_state()

    # Reset monthly API counters if new month
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if state.get("api_usage_monthly", {}).get("month") != current_month:
        state["api_usage_monthly"] = {"brave": 0, "tavily": 0, "month": current_month}

    week_number = state.get("query_rotation_week", 0)

    # Build dedup index
    dedup = DeduplicationIndex(DATA_DIR)
    dedup.build()
    logging.info(f"Dedup index: {len(dedup.urls)} URLs, {len(dedup.names)} names")

    # Relevance + extraction components
    if use_llm:
        judge = RelevanceJudge(openai_client)
        extractor = MetadataExtractor(openai_client, DATA_DIR)
    else:
        judge = KeywordRelevanceJudge()
        extractor = HeuristicMetadataExtractor(DATA_DIR)

    # Content types to process
    content_types = [args.type] if args.type else list(DATA_FILE_MAP.keys())
    if args.type and args.type not in DATA_FILE_MAP:
        logging.error(f"Unknown type: {args.type}. Valid: {list(DATA_FILE_MAP.keys())}")
        sys.exit(1)

    per_type_limit = args.limit if args.type else max(1, args.limit // len(content_types))

    # Run pipeline
    start_time = time.time()
    all_results = {"added": [], "rejected": [], "staged": [], "errors": []}

    for content_type in content_types:
        logging.info(f"Processing {content_type}...")
        queries = get_weekly_queries(queries_config, content_type, week_number)
        if not queries:
            logging.warning(f"  No queries for {content_type}")
            continue
        try:
            result = process_content_type(
                content_type, queries, search_orch, dedup, judge, extractor,
                DATA_DIR, per_type_limit, args.dry_run,
            )
            all_results["added"].extend(result["added"])
            all_results["rejected"].extend(result["rejected"])
            all_results["staged"].extend(result["staged"])
            all_results["errors"].extend(result["errors"])
        except Exception as e:
            logging.error(f"Failed {content_type}: {e}")
            all_results["errors"].append(f"{content_type}: {e}")

    duration = time.time() - start_time
    dedup.save_rejections()

    # API usage summary
    openai_calls = judge.call_count + extractor.call_count if use_llm else 0
    openai_tokens = getattr(judge, "total_tokens", 0)
    api_usage = {
        "brave": brave.call_count if brave else 0,
        "tavily": tavily.call_count if tavily else 0,
        "openai_calls": openai_calls,
        "openai_cost_usd": round((openai_tokens * 0.00000015) + (extractor.call_count * 500 * 0.00000015), 4) if use_llm else 0.0,
    }

    # Generate digest
    digest_data = {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration),
        "dry_run": args.dry_run,
        "added": all_results["added"],
        "rejected": all_results["rejected"],
        "staged": all_results["staged"],
        "api_usage": api_usage,
        "errors": all_results["errors"],
    }
    digest_html = generate_digest(digest_data)

    if not args.dry_run:
        DIGEST_FILE.write_text(digest_html)

    # Update state
    state["total_runs"] += 1
    state["total_items_added"] += len(all_results["added"])
    if all_results["added"] or all_results["rejected"]:
        state["query_rotation_week"] = week_number + 1
    else:
        logging.warning("No results processed; query rotation NOT advanced")
    state["api_usage_monthly"]["brave"] += api_usage["brave"]
    state["api_usage_monthly"]["tavily"] += api_usage["tavily"]
    state["total_cost_usd"] = round(state.get("total_cost_usd", 0) + api_usage["openai_cost_usd"], 4)
    state["history"].append({
        "run_date": digest_data["run_date"],
        "items_added": len(all_results["added"]),
        "items_rejected": len(all_results["rejected"]),
        "items_staged": len(all_results["staged"]),
        "cost_usd": api_usage["openai_cost_usd"],
        "errors": len(all_results["errors"]),
    })
    state["history"] = state["history"][-52:]
    for item in all_results["added"]:
        state.setdefault("recently_added_urls", []).append(item.get("url", ""))
    state["recently_added_urls"] = state.get("recently_added_urls", [])[-200:]

    if not args.dry_run:
        save_state(state)

    # Summary
    logging.info("=" * 60)
    logging.info(f"Discovery complete in {duration:.0f}s")
    logging.info(f"  Added: {len(all_results['added'])}")
    logging.info(f"  Rejected: {len(all_results['rejected'])}")
    logging.info(f"  Staged: {len(all_results['staged'])}")
    logging.info(f"  Errors: {len(all_results['errors'])}")
    logging.info(f"  API: Brave={api_usage['brave']}, Tavily={api_usage['tavily']}, OpenAI={api_usage['openai_calls']}")
    if args.dry_run:
        logging.info("  (DRY RUN - no files modified)")
        for item in all_results["added"]:
            meta = item.get("item", {})
            name = meta.get("name", meta.get("title", "?"))
            logging.info(f"  Would add [{item['type']}]: {name} - {item['url']}")


if __name__ == "__main__":
    main()
