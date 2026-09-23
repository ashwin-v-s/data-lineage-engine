"""
Temporal reference oracle (M3).
Pure Python implementation of bitemporal visibility logic.
Used to validate SQL queries via differential testing.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def visible(
    versions: List[Dict[str, Any]],
    valid_at: date,
    known_as_of: date
) -> List[str]:
    """
    Returns which edges were valid at valid_at, according to knowledge at known_as_of.
    
    Half-open intervals on both time axes:
    - valid_from <= valid_at < valid_to (or valid_to is None)
    - transaction_from <= known_as_of < transaction_to (or transaction_to is None)
    
    Args:
        versions: List of temporal version records, each with:
            - edge: str (edge identifier)
            - valid_from: date
            - valid_to: Optional[date] (None = still valid)
            - tx_from: date
            - tx_to: Optional[date] (None = current knowledge)
        valid_at: The valid time to query
        known_as_of: The transaction time to query
    
    Returns:
        Sorted list of edge identifiers that match both time constraints
    
    Examples:
        >>> D = date
        >>> versions = [
        ...     {"edge": "A->B", "valid_from": D(2026, 1, 1), "valid_to": None,
        ...      "tx_from": D(2026, 1, 2), "tx_to": D(2026, 3, 10)},
        ...     {"edge": "A->B", "valid_from": D(2026, 1, 1), "valid_to": D(2026, 3, 1),
        ...      "tx_from": D(2026, 3, 10), "tx_to": None},
        ...     {"edge": "A->C", "valid_from": D(2026, 3, 1), "valid_to": None,
        ...      "tx_from": D(2026, 3, 10), "tx_to": None},
        ... ]
        >>> visible(versions, D(2026, 3, 5), D(2026, 3, 5))
        ['A->B']
        >>> visible(versions, D(2026, 3, 5), D(2026, 3, 11))
        ['A->C']
    """
    def inside(lo: date, hi: Optional[date], t: date) -> bool:
        """Check if t is in half-open interval [lo, hi)"""
        return lo <= t and (hi is None or t < hi)
    
    matching_edges = [
        v["edge"] for v in versions
        if inside(v["valid_from"], v["valid_to"], valid_at)
        and inside(v["tx_from"], v["tx_to"], known_as_of)
    ]
    
    return sorted(matching_edges)


def visible_with_timestamps(
    versions: List[Dict[str, Any]],
    valid_at: datetime,
    known_as_of: datetime
) -> List[str]:
    """
    Timestamp version of visible() for PostgreSQL TIMESTAMPTZ compatibility.
    
    Args:
        versions: Temporal version records with datetime fields
        valid_at: The valid timestamp to query
        known_as_of: The transaction timestamp to query
    
    Returns:
        Sorted list of edge identifiers
    """
    def inside(lo: datetime, hi: Optional[datetime], t: datetime) -> bool:
        """Check if t is in half-open interval [lo, hi)"""
        return lo <= t and (hi is None or t < hi)
    
    matching_edges = [
        v["edge"] for v in versions
        if inside(v["valid_from"], v["valid_to"], valid_at)
        and inside(v["tx_from"], v["tx_to"], known_as_of)
    ]
    
    return sorted(matching_edges)
