import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def build_event(case: dict) -> dict:
    case_id = case["case_id"]
    target_dataset = case.get("target_dataset", "unknown")

    return {
        "eventType": "COMPLETE",
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "run": {
            "runId": f"synthetic-{uuid.uuid5(uuid.NAMESPACE_URL, case_id)}"
        },
        "job": {
            "name": case_id
        },
        "inputs": [
            {
                "namespace": "synthetic://kairos",
                "name": target_dataset
            }
        ],
        "outputs": [
            {
                "namespace": "synthetic://kairos",
                "name": f"{case_id}:output"
            }
        ],
        "producer": "kairos-m2-synthetic-runtime",
        "synthetic": True
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic OpenLineage-shaped runtime events."
    )
    parser.add_argument(
        "corpus_dir",
        type=Path,
        help="Directory containing SQL corpus JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/synthetic_runtime_events.json"),
    )
    args = parser.parse_args()

    events = []

    for path in sorted(args.corpus_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            case = json.load(file)

        if case.get("case_id", "").startswith("UNSUPPORTED_"):
            continue

        events.append(build_event(case))

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "synthetic": True,
                "description": (
                    "SYNTHETIC - shaped like OpenLineage, "
                    "not from a live pipeline."
                ),
                "events": events,
            },
            file,
            indent=2,
        )

    print(
        f"Generated {len(events)} synthetic runtime events -> "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
