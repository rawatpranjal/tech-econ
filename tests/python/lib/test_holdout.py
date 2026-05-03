"""Tests for lib.holdout (Phase 1 evaluation primitives)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from lib.holdout import TemporalSplitStats, temporal_split, to_utc_datetime


# Reference "now" for deterministic tests.
NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# to_utc_datetime
# ---------------------------------------------------------------------------
class TestToUtcDatetime:
    def test_aware_datetime_passes_through(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert to_utc_datetime(dt) == dt

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime(2026, 1, 1)
        assert to_utc_datetime(dt) == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_epoch_seconds(self):
        # 2026-01-01T00:00:00Z = 1767225600
        assert to_utc_datetime(1767225600) == datetime(
            2026, 1, 1, tzinfo=timezone.utc
        )

    def test_iso_string_with_z_suffix(self):
        assert to_utc_datetime("2026-05-03T12:00:00Z") == NOW

    def test_iso_string_with_offset(self):
        # +00:00 explicit offset
        assert to_utc_datetime("2026-05-03T12:00:00+00:00") == NOW

    def test_iso_string_naive_treated_as_utc(self):
        assert to_utc_datetime("2026-05-03T12:00:00") == NOW

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            to_utc_datetime("not a date")

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Cannot convert"):
            to_utc_datetime(["a", "list"])


# ---------------------------------------------------------------------------
# temporal_split — happy path
# ---------------------------------------------------------------------------
class TestTemporalSplit:
    def test_basic_split(self):
        events = [
            {"timestamp": "2026-04-01T00:00:00Z", "id": "old"},      # train
            {"timestamp": "2026-04-15T00:00:00Z", "id": "older"},    # train (18 days ago)
            {"timestamp": "2026-04-25T00:00:00Z", "id": "borderline"},  # test (8 days ago)
            {"timestamp": "2026-05-02T00:00:00Z", "id": "recent"},   # test (1 day ago)
        ]
        train, test, stats = temporal_split(events, holdout_days=14, now=NOW)
        train_ids = [e["id"] for e in train]
        test_ids = [e["id"] for e in test]
        assert sorted(train_ids) == sorted(["old", "older"])
        assert sorted(test_ids) == sorted(["borderline", "recent"])
        assert stats.n_train == 2
        assert stats.n_test == 2
        assert stats.cutoff == datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)

    def test_returns_stats_with_window_bounds(self):
        events = [
            {"timestamp": "2026-04-01T00:00:00Z"},
            {"timestamp": "2026-04-10T00:00:00Z"},
            {"timestamp": "2026-05-01T00:00:00Z"},
            {"timestamp": "2026-05-02T00:00:00Z"},
        ]
        _, _, stats = temporal_split(events, holdout_days=14, now=NOW)
        assert stats.train_window_start == datetime(2026, 4, 1, tzinfo=timezone.utc)
        assert stats.train_window_end == datetime(2026, 4, 10, tzinfo=timezone.utc)
        assert stats.test_window_start == datetime(2026, 5, 1, tzinfo=timezone.utc)
        assert stats.test_window_end == datetime(2026, 5, 2, tzinfo=timezone.utc)

    def test_all_events_in_train(self):
        events = [{"timestamp": "2026-01-01T00:00:00Z"}, {"timestamp": "2026-01-02T00:00:00Z"}]
        train, test, stats = temporal_split(events, holdout_days=14, now=NOW)
        assert len(train) == 2
        assert len(test) == 0
        assert stats.test_window_start is None
        assert stats.test_window_end is None

    def test_all_events_in_test(self):
        events = [{"timestamp": "2026-05-01T00:00:00Z"}, {"timestamp": "2026-05-02T00:00:00Z"}]
        train, test, stats = temporal_split(events, holdout_days=14, now=NOW)
        assert len(train) == 0
        assert len(test) == 2
        assert stats.train_window_start is None

    def test_empty_events(self):
        train, test, stats = temporal_split([], holdout_days=14, now=NOW)
        assert train == []
        assert test == []
        assert stats.n_train == 0
        assert stats.n_test == 0


# ---------------------------------------------------------------------------
# temporal_split — error paths
# ---------------------------------------------------------------------------
class TestTemporalSplitErrors:
    def test_zero_holdout_raises(self):
        with pytest.raises(ValueError, match="holdout_days must be positive"):
            temporal_split([], holdout_days=0, now=NOW)

    def test_negative_holdout_raises(self):
        with pytest.raises(ValueError, match="holdout_days must be positive"):
            temporal_split([], holdout_days=-1, now=NOW)

    def test_missing_timestamp_field_raises(self):
        events = [{"id": "no-ts"}]
        with pytest.raises(KeyError, match="no 'timestamp' field"):
            temporal_split(events, holdout_days=14, now=NOW)

    def test_invalid_timestamp_value_raises(self):
        events = [{"timestamp": "not-a-date"}]
        with pytest.raises(ValueError, match="Could not parse"):
            temporal_split(events, holdout_days=14, now=NOW)


# ---------------------------------------------------------------------------
# temporal_split — non-dict event objects
# ---------------------------------------------------------------------------
@dataclass
class FakeEvent:
    timestamp: str
    item_id: str


class TestTemporalSplitWithObjects:
    def test_dataclass_events(self):
        events = [
            FakeEvent(timestamp="2026-04-01T00:00:00Z", item_id="a"),
            FakeEvent(timestamp="2026-05-02T00:00:00Z", item_id="b"),
        ]
        train, test, _ = temporal_split(events, holdout_days=14, now=NOW)
        assert len(train) == 1 and train[0].item_id == "a"
        assert len(test) == 1 and test[0].item_id == "b"

    def test_custom_timestamp_key(self):
        events = [
            {"created_at": "2026-04-01T00:00:00Z"},
            {"created_at": "2026-05-02T00:00:00Z"},
        ]
        train, test, _ = temporal_split(
            events, holdout_days=14, now=NOW, timestamp_key="created_at"
        )
        assert len(train) == 1
        assert len(test) == 1


# ---------------------------------------------------------------------------
# Stats dataclass
# ---------------------------------------------------------------------------
def test_stats_is_frozen():
    """Architecture rule — split stats must be immutable so callers can
    safely log them without worrying about downstream mutation."""
    stats = TemporalSplitStats(
        n_train=1, n_test=1,
        train_window_start=NOW, train_window_end=NOW,
        test_window_start=NOW, test_window_end=NOW,
        cutoff=NOW,
    )
    with pytest.raises(Exception):
        stats.n_train = 999  # type: ignore[misc]
