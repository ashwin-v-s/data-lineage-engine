from research.ground_truth.provider import (
    GroundTruthProvider,
    GroundTruthResult,
    PropagationLabel,
)


def test_propagation_labels_exist():
    assert PropagationLabel.PROPAGATED.value == "PROPAGATED"
    assert PropagationLabel.NOT_PROPAGATED.value == "NOT_PROPAGATED"


def test_ground_truth_result():
    result = GroundTruthResult(
        source_column="employees_a.salary",
        target_column="out_adjusted.adjusted_salary",
        label=PropagationLabel.PROPAGATED,
        provider="reference_interpreter",
        version="1.0",
        artifact_hash="abc123",
    )

    assert result.source_column == "employees_a.salary"
    assert result.target_column == "out_adjusted.adjusted_salary"
    assert result.label == PropagationLabel.PROPAGATED
    assert result.provider == "reference_interpreter"
    assert result.version == "1.0"
    assert result.artifact_hash == "abc123"


def test_provider_is_abstract():
    assert GroundTruthProvider.__abstractmethods__