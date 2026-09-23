from research.ground_truth.provider import PropagationLabel
from research.ground_truth.reference_interpreter import (
    ReferenceInterpreterProvider,
)


def test_reference_provider_returns_propagated():
    provider = ReferenceInterpreterProvider(
        {
            (
                "employees_a.salary",
                "out_adjusted.adjusted_salary",
            ): True
        }
    )

    result = provider.determine(
        "employees_a.salary",
        "out_adjusted.adjusted_salary",
    )

    assert result.label == PropagationLabel.PROPAGATED
    assert result.provider == "reference_interpreter"
    assert result.version == "reference-1.0"
    assert result.artifact_hash != ""


def test_reference_provider_returns_not_propagated():
    provider = ReferenceInterpreterProvider(
        {
            (
                "employees_a.salary",
                "out_adjusted.adjusted_salary",
            ): True
        }
    )

    result = provider.determine(
        "employees_a.country",
        "out_adjusted.adjusted_salary",
    )

    assert result.label == PropagationLabel.NOT_PROPAGATED


def test_same_result_has_same_hash():
    provider = ReferenceInterpreterProvider(
        {
            (
                "employees_a.salary",
                "out_adjusted.adjusted_salary",
            ): True
        }
    )

    first = provider.determine(
        "employees_a.salary",
        "out_adjusted.adjusted_salary",
    )

    second = provider.determine(
        "employees_a.salary",
        "out_adjusted.adjusted_salary",
    )

    assert first.artifact_hash == second.artifact_hash