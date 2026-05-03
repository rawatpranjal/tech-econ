"""Shared pytest fixtures for the tech-econ recsys test suite.

Currently empty — fixtures will be added as Job 0.2+ introduces real tests
against rank_all_content.py, generate_embeddings.py, etc.

Inputs: none.
Outputs: pytest fixture functions importable from any test_*.py.
Side effects: none.
Reproducibility: fixtures will set seeds when they touch randomness.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `lib/` and `scripts/` importable from tests without installing the
# package. This is the only test-infra magic; everything else is explicit.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, _REPO_ROOT / "lib", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
