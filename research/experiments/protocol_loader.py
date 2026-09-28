"""Protocol loader and validator.

Loads research/protocol/v1.yaml and enforces:
  - A real (non-plumbing) experiment cannot run while required fields are TBD.
  - Plumbing mode may proceed despite TBD values (with an explicit warning).
  - The validator reports exactly which fields are TBD, not just "protocol incomplete".

Standard library only — no PyYAML dependency.
The YAML parser here is minimal: it handles only the flat/nested key:value
structure of v1.yaml.  It is NOT a general-purpose YAML parser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Fields that MUST be resolved before a real (non-plumbing) run.
# TBD values in these fields block execution.
# ---------------------------------------------------------------------------
REQUIRED_FOR_REAL_RUN: Tuple[str, ...] = (
    "benchmark_version",
    "sql_subset",
    "splits.development",
    "splits.validation",
    "splits.held_out",
    "contribution_semantics",
    "prediction_unit_universe",
    "loss.master_seed",
    "loss.replicates",
    "loss.rounding_rule",
    "metrics.primary",
    "metrics.confidence_interval",
    "aggregation",
    "stopping_rule",
    "exclusion_rules",
)

_TBD = "TBD"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ProtocolValidationResult:
    ok: bool
    tbd_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def raise_if_blocking(self, plumbing: bool) -> None:
        """Raise if TBD fields exist and we are not in plumbing mode."""
        if self.tbd_fields and not plumbing:
            joined = "\n  - ".join(self.tbd_fields)
            raise ProtocolBlockedError(
                f"Cannot run a real experiment: {len(self.tbd_fields)} required protocol "
                f"field(s) are still TBD:\n  - {joined}\n"
                "Resolve these values before running without --plumbing."
            )


class ProtocolBlockedError(RuntimeError):
    """Raised when a required protocol field is TBD and plumbing mode is off."""


# ---------------------------------------------------------------------------
# Minimal YAML loader (standard library only)
# ---------------------------------------------------------------------------

def _load_yaml(text: str) -> Dict[str, Any]:
    """Parse the flat/nested structure of v1.yaml without PyYAML.

    Supports:
      key: value
      key: [v1, v2, v3]   (inline lists)
      nested:
        key: value
    Does not support: anchors, multi-doc, block sequences, quoted strings
    with special chars, or anything else not in v1.yaml.
    """
    root: Dict[str, Any] = {}
    # Stack entries: (indent_of_key, dict_at_this_level)
    stack: List[Tuple[int, Dict[str, Any]]] = [(-1, root)]

    for raw_line in text.splitlines():
        # Strip comments and trailing whitespace
        line = raw_line.split("#")[0].rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if ":" not in stripped:
            continue

        key, _, rest = stripped.partition(":")
        key = key.strip()
        value_str = rest.strip()

        # Pop stack entries whose indent is >= current indent
        # (we want the nearest ancestor with a strictly smaller indent)
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()

        parent = stack[-1][1]

        if not value_str:
            # Nested mapping block — push a new child dict
            child: Dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        elif value_str.startswith("[") and value_str.endswith("]"):
            # Inline list
            items = [
                v.strip().strip('"').strip("'")
                for v in value_str[1:-1].split(",")
                if v.strip()
            ]
            parent[key] = items
        else:
            # Scalar value
            val = value_str.strip('"').strip("'")
            parent[key] = val

    return root


def _get_nested(d: Dict[str, Any], dotted: str) -> Any:
    """Retrieve a value from a nested dict using dotted key notation."""
    keys = dotted.split(".")
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_protocol(path: str = "research/protocol/v1.yaml") -> Dict[str, Any]:
    """Load the protocol YAML into a plain dict."""
    text = Path(path).read_text(encoding="utf-8")
    return _load_yaml(text)


def validate_protocol(protocol: Dict[str, Any]) -> ProtocolValidationResult:
    """Check required-for-real-run fields for TBD values.

    Returns a ProtocolValidationResult listing every TBD field found.
    Does NOT raise; the caller decides whether to block or warn.
    """
    tbd: List[str] = []
    for dotted in REQUIRED_FOR_REAL_RUN:
        val = _get_nested(protocol, dotted)
        if val is None or str(val).strip().upper() == _TBD:
            tbd.append(dotted)

    warnings: List[str] = []
    if tbd:
        warnings.append(
            f"{len(tbd)} required field(s) are TBD. "
            "A real experiment cannot run until they are resolved."
        )

    return ProtocolValidationResult(ok=len(tbd) == 0, tbd_fields=tbd, warnings=warnings)
