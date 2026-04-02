from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .plugin_contract import HostAdapter


@dataclass
class ComplianceReport:
    compatible: bool
    errors: List[str]


REQUIRED_METHODS = [
    "load_profile",
    "get_session_context",
    "register_event_listener",
    "append_telemetry",
]


def validate_host_adapter(adapter: Any) -> ComplianceReport:
    errors: List[str] = []

    for method in REQUIRED_METHODS:
        if not hasattr(adapter, method) or not callable(getattr(adapter, method)):
            errors.append(f"missing required method: {method}")

    if not errors:
        try:
            profile = adapter.load_profile("u-1")
            if not isinstance(profile, dict):
                errors.append("load_profile must return dict schema")
        except Exception as ex:
            errors.append(f"load_profile raised: {ex}")

    return ComplianceReport(compatible=not errors, errors=errors)
