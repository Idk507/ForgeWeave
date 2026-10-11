"""Scripted model provider used by native loop tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ModelChunk:
    """One provider stream chunk."""

    kind: str
    content: str = ""
    call_id: str | None = None
    usage: dict[str, int] | None = None


class FakeModelProvider:
    """Deterministic provider that yields a scripted stream."""

    def __init__(self, chunks: Iterable[ModelChunk]) -> None:
        self._chunks = tuple(chunks)

    def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> Iterable[ModelChunk]:
        """Yield scripted chunks; arguments are accepted to match real providers."""

        del messages, tools, options
        yield from self._chunks
