from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ExperimentResult:
    primary_success: bool
    latency_guardrail_ok: bool
    error_guardrail_ok: bool


@dataclass
class CanaryState:
    current_stage: int
    stages: List[int]
    pinned_version: str


class RolloutController:
    def __init__(self, stages: List[int] | None = None, pinned_version: str = "v1") -> None:
        self.state = CanaryState(current_stage=0, stages=stages or [5, 25, 50, 100], pinned_version=pinned_version)

    def can_progress(self, result: ExperimentResult) -> bool:
        return result.primary_success and result.latency_guardrail_ok and result.error_guardrail_ok

    def progress(self, result: ExperimentResult) -> int:
        if self.can_progress(result) and self.state.current_stage < len(self.state.stages) - 1:
            self.state.current_stage += 1
        return self.state.stages[self.state.current_stage]

    def rollback(self, stable_version: str) -> Dict[str, str]:
        self.state.current_stage = max(0, self.state.current_stage - 1)
        self.state.pinned_version = stable_version
        return {"action": "rollback", "target_version": stable_version, "stage": str(self.state.stages[self.state.current_stage])}
