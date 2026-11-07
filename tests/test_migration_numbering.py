"""Focused tests for the static migration-numbering continuity check.

`scripts/db/check_migrations.py` is an operator CLI, not an importable package,
so it is loaded from its path.  These tests exercise ``check_numbering`` only:
they never read the real migrations directory, never import ``verify_rls.py``
and never touch a database.

Why this matters: the chain is positional.  A branch that lost migration 0010
while keeping 0011 previously reported ``RESULT: PASS`` because no file was
duplicated — the missing number was invisible.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "db" / "check_migrations.py"
_spec = importlib.util.spec_from_file_location("kairos_check_migrations", SCRIPT)
check_migrations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_migrations)

# Deliberately contains neither "PROPOSAL ONLY" nor "NOT APPLIED", so the file
# parses as an ordinary applied migration.
MINIMAL_SQL = "BEGIN;\nSELECT 1;\nCOMMIT;\n"


def _write(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_text(MINIMAL_SQL, encoding="utf-8")
    return path


def _numbers(*numbers: int) -> list[str]:
    return [f"{number:04d}_step_{number}.sql" for number in numbers]


def _check(directory: Path):
    migrations = check_migrations._gather_migrations(directory)
    return check_migrations.check_numbering(migrations)


def test_expected_range_is_0001_through_0012():
    assert check_migrations.EXPECTED_FIRST_MIGRATION == 1
    assert check_migrations.EXPECTED_LATEST_MIGRATION == 12


def test_complete_chain_has_no_gaps(tmp_path):
    for name in _numbers(*range(1, 13)):
        _write(tmp_path, name)

    gaps, notes = _check(tmp_path)

    assert gaps == []
    assert notes == []


def test_missing_0010_is_reported_as_a_gap(tmp_path):
    """The exact local state: 0001-0009 and 0011 present, 0010 absent."""
    for number in [*range(1, 10), 11, 12]:
        _write(tmp_path, _numbers(number)[0])

    gaps, _notes = _check(tmp_path)

    assert len(gaps) == 1
    assert "0010" in gaps[0]
    assert "MISSING" in gaps[0]


def test_every_missing_number_is_reported_independently(tmp_path):
    for number in (1, 2, 5):
        _write(tmp_path, _numbers(number)[0])

    gaps, _notes = _check(tmp_path)

    reported = [gap for gap in gaps if "is MISSING" in gap]
    assert len(reported) == 9  # 3,4,6,7,8,9,10,11,12
    for number in (3, 4, 6, 7, 8, 9, 10, 11):
        assert any(f"{number:04d}" in gap for gap in reported)


def test_duplicate_number_is_reported_separately_from_a_gap(tmp_path):
    _write(tmp_path, "0001_first.sql")
    _write(tmp_path, "0001_second.sql")
    for number in range(2, 13):
        _write(tmp_path, _numbers(number)[0])

    gaps, _notes = _check(tmp_path)

    assert len(gaps) == 1
    assert "claimed by 2 files" in gaps[0]
    assert "0001_first.sql" in gaps[0] and "0001_second.sql" in gaps[0]


def test_non_conforming_filename_is_reported(tmp_path):
    for number in range(1, 12):
        _write(tmp_path, _numbers(number)[0])
    _write(tmp_path, "0012-add-role.sql")  # hyphens, not NNNN_snake.sql

    gaps, _notes = _check(tmp_path)

    assert any("does not follow the NNNN_name.sql convention" in gap for gap in gaps)


def test_number_beyond_the_expected_range_is_a_note_not_a_gap(tmp_path):
    for number in range(1, 14):
        _write(tmp_path, _numbers(number)[0])

    gaps, notes = _check(tmp_path)

    assert gaps == []
    assert any("0013" in note and "EXPECTED_LATEST_MIGRATION" in note for note in notes)


def test_real_migrations_directory_reports_complete_chain():
    """Pin the current repository state: 0001-0012 all present, no gaps."""
    migrations_dir = Path(__file__).resolve().parents[1] / "backend" / "migrations"
    if not migrations_dir.is_dir():  # pragma: no cover - defensive
        pytest.skip("migrations directory not present")

    gaps, _notes = _check(migrations_dir)

    missing_numbers = [gap for gap in gaps if "is MISSING" in gap]
    assert missing_numbers == []
    assert all("does not follow" not in gap for gap in gaps)
    assert all("claimed by" not in gap for gap in gaps)
