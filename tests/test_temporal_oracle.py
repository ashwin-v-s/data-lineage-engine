"""
Tests for the temporal oracle (M3).
Tests the four-row example from the pack and edge cases.
"""
from datetime import date, datetime, timezone

import pytest

from backend.app.temporal.reference import visible, visible_with_timestamps


class TestTemporalOracle:
    """Test the Python temporal oracle with the pack's four-row example."""
    
    @pytest.fixture
    def pack_example_versions(self):
        """
        The four-row example from Section 10 of the pack:
        - Original belief: A->B valid from Jan 1, learned Jan 2
        - Correction on Mar 10: A->B actually ended Mar 1
        - New edge: A->C started Mar 1, learned Mar 10
        """
        D = date
        return [
            # Original belief (later corrected)
            {
                "edge": "A->B",
                "valid_from": D(2026, 1, 1),
                "valid_to": None,
                "tx_from": D(2026, 1, 2),
                "tx_to": D(2026, 3, 10),
            },
            # Corrected record: A->B ended on Mar 1
            {
                "edge": "A->B",
                "valid_from": D(2026, 1, 1),
                "valid_to": D(2026, 3, 1),
                "tx_from": D(2026, 3, 10),
                "tx_to": None,
            },
            # New edge that replaced it
            {
                "edge": "A->C",
                "valid_from": D(2026, 3, 1),
                "valid_to": None,
                "tx_from": D(2026, 3, 10),
                "tx_to": None,
            },
        ]
    
    def test_pack_example_before_correction(self, pack_example_versions):
        """
        Valid at Mar 5, known as of Mar 5 (before correction).
        On Mar 5, we still believed A->B.
        """
        D = date
        result = visible(pack_example_versions, D(2026, 3, 5), D(2026, 3, 5))
        assert result == ["A->B"]
    
    def test_pack_example_after_correction(self, pack_example_versions):
        """
        Valid at Mar 5, known as of Mar 11 (after correction).
        After correction, we know A->C was valid on Mar 5.
        """
        D = date
        result = visible(pack_example_versions, D(2026, 3, 5), D(2026, 3, 11))
        assert result == ["A->C"]
    
    def test_pack_example_latest_knowledge(self, pack_example_versions):
        """
        Valid at Mar 5, known as of today (latest).
        Latest knowledge: A->C was valid on Mar 5.
        """
        D = date
        now = D(2026, 9, 20)
        result = visible(pack_example_versions, D(2026, 3, 5), now)
        assert result == ["A->C"]
    
    def test_pack_example_historical_graph(self, pack_example_versions):
        """
        Valid at today, known as of Mar 5.
        "What graph did we hold on Mar 5?" -> A->B
        """
        D = date
        now = D(2026, 9, 20)
        result = visible(pack_example_versions, now, D(2026, 3, 5))
        assert result == ["A->B"]
    
    def test_pack_example_exclusive_valid_to(self, pack_example_versions):
        """
        valid_to is EXCLUSIVE (half-open interval).
        At the exact moment of transition (Mar 1), A->C starts.
        """
        D = date
        now = D(2026, 9, 20)
        
        # Feb 28: still A->B
        assert visible(pack_example_versions, D(2026, 2, 28), now) == ["A->B"]
        
        # Mar 1: A->C starts (valid_to is exclusive)
        assert visible(pack_example_versions, D(2026, 3, 1), now) == ["A->C"]
        
        # Mar 2: still A->C
        assert visible(pack_example_versions, D(2026, 3, 2), now) == ["A->C"]


class TestTemporalEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_before_interval_start(self):
        """Query before any version exists."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": None,
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 5), D(2026, 1, 15))
        assert result == []
    
    def test_at_interval_start_inclusive(self):
        """Query at exact start of interval (inclusive)."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": None,
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 10), D(2026, 1, 15))
        assert result == ["X->Y"]
    
    def test_inside_interval(self):
        """Query inside the interval."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": D(2026, 1, 20),
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 15), D(2026, 1, 15))
        assert result == ["X->Y"]
    
    def test_at_interval_end_exclusive(self):
        """Query at exact end of interval (exclusive)."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": D(2026, 1, 20),
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 20), D(2026, 1, 25))
        assert result == []
    
    def test_after_interval_end(self):
        """Query after interval has closed."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": D(2026, 1, 20),
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 25), D(2026, 1, 30))
        assert result == []
    
    def test_open_ended_valid_interval(self):
        """valid_to = None means still valid."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": None,
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 12, 31), D(2026, 12, 31))
        assert result == ["X->Y"]
    
    def test_open_ended_transaction_interval(self):
        """tx_to = None means current knowledge."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": None,
             "tx_from": D(2026, 1, 10), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 15), D(2026, 12, 31))
        assert result == ["X->Y"]
    
    def test_overlapping_intervals_different_edges(self):
        """Multiple edges can be valid at the same time."""
        D = date
        versions = [
            {"edge": "A->B", "valid_from": D(2026, 1, 1), "valid_to": None,
             "tx_from": D(2026, 1, 1), "tx_to": None},
            {"edge": "B->C", "valid_from": D(2026, 1, 1), "valid_to": None,
             "tx_from": D(2026, 1, 1), "tx_to": None},
        ]
        result = visible(versions, D(2026, 1, 15), D(2026, 1, 15))
        assert result == ["A->B", "B->C"]
    
    def test_transaction_time_filters_out_future_knowledge(self):
        """known_as_of filters versions not yet recorded."""
        D = date
        versions = [
            {"edge": "X->Y", "valid_from": D(2026, 1, 10), "valid_to": None,
             "tx_from": D(2026, 1, 20), "tx_to": None},
        ]
        # Query before we learned about it
        result = visible(versions, D(2026, 1, 15), D(2026, 1, 15))
        assert result == []
        
        # Query after we learned about it
        result = visible(versions, D(2026, 1, 15), D(2026, 1, 25))
        assert result == ["X->Y"]
    
    def test_late_correction_closes_old_version(self):
        """Late correction closes transaction interval of old belief."""
        D = date
        versions = [
            # Original belief
            {"edge": "X->Y", "valid_from": D(2026, 1, 1), "valid_to": D(2026, 2, 1),
             "tx_from": D(2026, 1, 1), "tx_to": D(2026, 3, 1)},
            # Correction
            {"edge": "X->Y", "valid_from": D(2026, 1, 1), "valid_to": D(2026, 1, 15),
             "tx_from": D(2026, 3, 1), "tx_to": None},
        ]
        # Before correction: believed it was valid until Feb 1
        result = visible(versions, D(2026, 1, 20), D(2026, 2, 15))
        assert result == ["X->Y"]
        
        # After correction: know it ended Jan 15
        result = visible(versions, D(2026, 1, 20), D(2026, 3, 15))
        assert result == []


class TestTimestampVersion:
    """Test timestamp version for PostgreSQL TIMESTAMPTZ compatibility."""
    
    def test_timestamp_version_works(self):
        """Timestamp version produces same results as date version."""
        versions = [
            {
                "edge": "A->B",
                "valid_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "valid_to": None,
                "tx_from": datetime(2026, 1, 2, tzinfo=timezone.utc),
                "tx_to": datetime(2026, 3, 10, tzinfo=timezone.utc),
            },
            {
                "edge": "A->B",
                "valid_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "valid_to": datetime(2026, 3, 1, tzinfo=timezone.utc),
                "tx_from": datetime(2026, 3, 10, tzinfo=timezone.utc),
                "tx_to": None,
            },
        ]
        result = visible_with_timestamps(
            versions,
            datetime(2026, 3, 5, tzinfo=timezone.utc),
            datetime(2026, 3, 5, tzinfo=timezone.utc)
        )
        assert result == ["A->B"]
