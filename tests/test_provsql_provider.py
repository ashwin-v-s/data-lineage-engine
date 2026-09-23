from research.ground_truth.provider import PropagationLabel
from research.ground_truth.provsql_provider import ProvSQLProvider


def test_provsql_provider_propagated():
    artifact = {
        "propagated_pairs": [
            ["country", "adjusted_salary"],
            ["salary", "adjusted_salary"],
        ]
    }

    provider = ProvSQLProvider(artifact)

    result = provider.determine("salary", "adjusted_salary")

    assert result.label == PropagationLabel.PROPAGATED
    assert result.provider == "provsql"
    assert result.version == "provsql-1.4.0"
    assert result.artifact_hash


def test_provsql_provider_not_propagated():
    artifact = {
        "propagated_pairs": [
            ["country", "adjusted_salary"],
            ["salary", "adjusted_salary"],
        ]
    }

    provider = ProvSQLProvider(artifact)

    result = provider.determine("name", "adjusted_salary")

    assert result.label == PropagationLabel.NOT_PROPAGATED
    assert result.provider == "provsql"
    assert result.artifact_hash
