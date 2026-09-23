from pathlib import Path


FORBIDDEN_IMPORTS = {
    "sqlglot",
    "ingestion",
    "research.reasoning",
    "research.baselines",
}


def test_ground_truth_does_not_import_prediction_modules():
    ground_truth_dir = Path("research/ground_truth")

    for path in ground_truth_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")

        for forbidden in FORBIDDEN_IMPORTS:
            assert f"import {forbidden}" not in source
            assert f"from {forbidden}" not in source