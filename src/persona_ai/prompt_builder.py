from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .config import estimate_token_count


@dataclass(frozen=True)
class PromptSection:
    name: str
    lines: List[str]


class PromptBuilder:
    def __init__(self, token_budget: int = 220, max_episodic_items: int = 3) -> None:
        self.token_budget = token_budget
        self.max_episodic_items = max_episodic_items

    def build(
        self,
        *,
        semantic_facts: Iterable[str],
        episodic_facts: Iterable[str],
        working_summary: str,
    ) -> str:
        semantic = self._suppress_outliers(list(semantic_facts))
        episodic = self._dedupe(list(episodic_facts))[: self.max_episodic_items]

        sections: List[PromptSection] = []
        if semantic:
            sections.append(PromptSection(name="Long-term profile", lines=semantic))
        if episodic:
            sections.append(PromptSection(name="Relevant episodic history", lines=episodic))
        if working_summary:
            sections.append(PromptSection(name="Current working-memory summary", lines=[working_summary]))

        if not sections:
            return ""

        lines = ["Use the following memory context when it is relevant and safe."]
        for section in sections:
            lines.append(f"{section.name}: " + " | ".join(section.lines))

        prompt = "\n".join(lines)
        return self._truncate(prompt)

    def _suppress_outliers(self, facts: List[str]) -> List[str]:
        # Simple anti-pollution strategy: suppress one-off minority statements for same field.
        grouped: dict[str, List[str]] = {}
        for fact in facts:
            name = fact.split("=", 1)[0].strip().lower()
            grouped.setdefault(name, []).append(fact)

        kept: List[str] = []
        for _, values in grouped.items():
            if len(values) <= 1:
                kept.extend(values)
                continue
            counts: dict[str, int] = {}
            for item in values:
                counts[item] = counts.get(item, 0) + 1
            ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
            kept.append(ranked[0][0])
        return kept

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in items:
            key = item.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    def _truncate(self, prompt: str) -> str:
        if self.token_budget <= 0:
            return ""
        if estimate_token_count(prompt) <= self.token_budget:
            return prompt
        words = prompt.split()
        return " ".join(words[: self.token_budget])
