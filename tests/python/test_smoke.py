"""Smoke test — proves pytest discovery and CI plumbing work.

Replace / supplement once Job 0.2+ adds real tests.
"""


def test_pytest_runs() -> None:
    """Trivial assertion — failure means pytest itself is broken."""
    assert 1 + 1 == 2


def test_repo_root_importable() -> None:
    """conftest.py adds repo root + lib/ + scripts/ to sys.path. Verify."""
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    assert str(repo_root) in sys.path, "conftest.py should put repo root on sys.path"
