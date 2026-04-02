from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol, runtime_checkable


@dataclass
class PluginManifest:
    name: str
    version: str
    required_fields: list[str]
    min_confidence_threshold: float
    host_compatibility: list[str]


@dataclass
class DialogEvent:
    session_id: str
    user_id: str
    turn_id: int
    payload: Dict[str, Any]


@dataclass
class ProfileUpdateEvent:
    user_id: str
    field_name: str
    old_value: Any
    new_value: Any


@runtime_checkable
class PersonaPlugin(Protocol):
    def manifest(self) -> PluginManifest: ...

    def on_profile_ready(self, profile: Dict[str, Any]) -> None: ...

    def on_dialog_turn(self, event: DialogEvent) -> None: ...

    def on_profile_update(self, event: ProfileUpdateEvent) -> None: ...


@runtime_checkable
class HostAdapter(Protocol):
    def load_profile(self, user_id: str) -> Dict[str, Any]: ...

    def get_session_context(self, session_id: str) -> Dict[str, Any]: ...

    def register_event_listener(self, event_name: str, callback: Any) -> None: ...

    def append_telemetry(self, event_name: str, payload: Dict[str, Any]) -> None: ...
