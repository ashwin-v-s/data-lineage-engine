import json

from ingestion.openlineage.normalizer import RuntimeEvidenceNormalizer


def main():
    with open("runtime_events.json", "r", encoding="utf-8") as file:
        events = [json.loads(line) for line in file if line.strip()]

    normalizer = RuntimeEvidenceNormalizer()

    evidence = normalizer.normalize_events(events)

    print(f"Raw events: {len(events)}")
    print(f"Normalized events: {len(evidence)}")

    for item in evidence:
        print()
        print("Event ID:", item.event_id)
        print("Event type:", item.event_type)
        print("Run ID:", item.run_id)
        print("Job:", item.job_name)
        print("Inputs:", item.inputs)
        print("Outputs:", item.outputs)
        print("Payload hash:", item.payload_hash)
        print("Diagnostics:", item.diagnostics)


if __name__ == "__main__":
    main()