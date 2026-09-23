"""Shared contracts for Kairos (Pack Section 16). Status: PROVISIONAL until the architecture freeze.

Rule: ground-truth-only types live in contracts.truth and must never be imported by
research.reasoning or research.baselines (enforced by scripts/check_import_boundaries.py).
"""
