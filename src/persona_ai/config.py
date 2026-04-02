from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryRuntimeConfig:
    working_window_k: int = 6
    working_summary_turns: int = 3
    memory_prompt_token_budget: int = 220


def estimate_token_count(text: str) -> int:
    # Lightweight estimate suitable for deterministic local budgeting.
    return max(1, len(text.split())) if text.strip() else 0
