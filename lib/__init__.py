"""Shared Python helpers for the recsys / search stack.

Modules here have light dependencies (numpy, stdlib) and are safe to
import in tests without dragging in heavy ML libraries. Keep it that
way — anything that needs sentence-transformers or lightgbm belongs in
scripts/, not lib/.
"""
