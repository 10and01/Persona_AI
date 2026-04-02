from __future__ import annotations

from typing import Any, Dict

from .plugin_contract import DialogEvent, PersonaPlugin, PluginManifest, ProfileUpdateEvent


class ResponseStylePlugin(PersonaPlugin):
    """Reference plugin that consumes contract-compliant profile fields."""

    def __init__(self) -> None:
        self.active_style = "default"

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="response-style-plugin",
            version="0.1.0",
            required_fields=["response_style"],
            min_confidence_threshold=0.7,
            host_compatibility=["*"],
        )

    def on_profile_ready(self, profile: Dict[str, Any]) -> None:
        style = profile.get("response_style")
        if isinstance(style, dict):
            self.active_style = style.get("value", "default")

    def on_dialog_turn(self, event: DialogEvent) -> None:
        _ = event

    def on_profile_update(self, event: ProfileUpdateEvent) -> None:
        if event.field_name == "response_style":
            self.active_style = event.new_value
