from ingestion.openlineage.normalizer import RuntimeEvidenceNormalizer


def make_event():
    return {
        "eventType": "COMPLETE",
        "eventTime": "2026-09-23T10:00:00+00:00",
        "run": {
            "runId": "run-001"
        },
        "job": {
            "namespace": "kairos",
            "name": "employee_salary_adjustment"
        },
        "inputs": [
            {
                "namespace": "postgresql://localhost:5432/kairos",
                "name": "employees_a"
            }
        ],
        "outputs": [
            {
                "namespace": "postgresql://localhost:5432/kairos",
                "name": "out_adjusted"
            }
        ]
    }


def test_normalizes_event():
    normalizer = RuntimeEvidenceNormalizer()

    evidence = normalizer.normalize(make_event())

    assert evidence is not None
    assert evidence.run_id == "run-001"
    assert evidence.event_type == "COMPLETE"
    assert evidence.job_name == "employee_salary_adjustment"

    assert len(evidence.inputs) == 1
    assert len(evidence.outputs) == 1

    assert evidence.raw_event["eventType"] == "COMPLETE"
    assert evidence.payload_hash != ""
    assert evidence.event_id != ""


def test_duplicate_event_is_ignored():
    normalizer = RuntimeEvidenceNormalizer()

    event = make_event()

    first = normalizer.normalize(event)
    second = normalizer.normalize(event)

    assert first is not None
    assert second is None
    
def test_retry_with_same_payload_is_deduplicated():
    normalizer = RuntimeEvidenceNormalizer()

    event = make_event()

    first = normalizer.normalize(event)
    retry = normalizer.normalize(event.copy())

    assert first is not None
    assert retry is None


def test_out_of_order_events_are_preserved():
    normalizer = RuntimeEvidenceNormalizer()

    complete_event = make_event()

    start_event = {
        "eventType": "START",
        "eventTime": "2026-09-23T09:59:00+00:00",
        "run": {
            "runId": "run-001"
        },
        "job": {
            "namespace": "kairos",
            "name": "employee_salary_adjustment"
        },
    }

    # COMPLETE arrives before START.
    complete = normalizer.normalize(complete_event)
    start = normalizer.normalize(start_event)

    assert complete is not None
    assert start is not None

    assert complete.event_type == "COMPLETE"
    assert start.event_type == "START"

    assert complete.run_id == start.run_id
    
def test_missing_events_do_not_create_negative_evidence():
    normalizer = RuntimeEvidenceNormalizer()

    result = normalizer.normalize_events([])

    assert result == []