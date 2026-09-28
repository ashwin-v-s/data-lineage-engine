from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeEvidence:
    run_id: str
    event_type: str
    event_time: str
    job_name: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    raw_event: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    payload_hash: str = ""
    diagnostics: list[str] = field(default_factory=list)