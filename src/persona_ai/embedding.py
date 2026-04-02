from __future__ import annotations

import hashlib
from typing import List, Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> List[float]:
        raise NotImplementedError


class DeterministicHashEmbeddingProvider:
    """Deterministic local embedding for development/testing.

    This is not semantically meaningful like production embeddings, but it keeps
    interface behavior deterministic before external providers are wired.
    """

    def __init__(self, dimensions: int = 16) -> None:
        self.dimensions = max(4, dimensions)

    def embed(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: List[float] = []
        for i in range(self.dimensions):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2.0 - 1.0)
        return values
