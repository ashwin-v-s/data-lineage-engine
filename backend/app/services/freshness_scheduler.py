"""Scheduler boundary for M4 freshness evaluation.

M2 owns the durable scheduler runtime and M1 owns the deployment/runtime
constraint. No approved adapter is present in this repository, so the default
implementation is deliberately BLOCKED and never starts background work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

SCHEDULER_STATUS = "BLOCKED"
SCHEDULER_BLOCK_REASON = "M2/M1 must approve a durable scheduler adapter before scheduled evaluations can run."


@dataclass(frozen=True)
class FreshnessSchedule:
    workspace_id: str
    dataset_id: str
    cadence: str
    paused: bool


class FreshnessScheduler(Protocol):
    """Contract for a durable scheduler adapter; callbacks must use API auth/RLS."""

    def configure(self, schedule: FreshnessSchedule) -> None: ...

    def remove(self, workspace_id: str, dataset_id: str) -> None: ...


class BlockedFreshnessScheduler:
    """Fail closed until the M2/M1 runtime contract is approved and implemented."""

    status = SCHEDULER_STATUS
    block_reason = SCHEDULER_BLOCK_REASON

    def configure(self, schedule: FreshnessSchedule) -> None:
        raise RuntimeError(self.block_reason)

    def remove(self, workspace_id: str, dataset_id: str) -> None:
        raise RuntimeError(self.block_reason)


def scheduler_status(cadence: str) -> str:
    """Report schedule truth without implying a configured cadence is active."""
    return "MANUAL" if cadence == "manual" else SCHEDULER_STATUS
