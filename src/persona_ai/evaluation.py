from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class OfflineMetrics:
    profile_accuracy: float
    calibration_error: float
    drift_precision: float
    constraint_adherence: float


@dataclass
class GateThresholds:
    min_accuracy: float = 0.80
    max_calibration_error: float = 0.08
    min_drift_precision: float = 0.85
    min_constraint_adherence: float = 0.99


def evaluate_offline(metrics: OfflineMetrics, thresholds: GateThresholds) -> Dict[str, bool]:
    return {
        "accuracy": metrics.profile_accuracy >= thresholds.min_accuracy,
        "calibration": metrics.calibration_error <= thresholds.max_calibration_error,
        "drift": metrics.drift_precision >= thresholds.min_drift_precision,
        "constraints": metrics.constraint_adherence >= thresholds.min_constraint_adherence,
    }


def offline_gate_passed(metrics: OfflineMetrics, thresholds: GateThresholds) -> bool:
    checks = evaluate_offline(metrics, thresholds)
    return all(checks.values())
