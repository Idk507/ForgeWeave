"""Instruction resolution with provenance, precedence and contradiction checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from math import ceil
from typing import Any


class InstructionAuthority(StrEnum):
    """Known instruction authority tiers in descending trust order."""

    PLATFORM = "platform"
    ORGANIZATION = "organization"
    TASK = "task"
    REPOSITORY = "repository"
    SKILL = "skill"
    RETRIEVED = "retrieved"


AUTHORITY_PRECEDENCE: dict[str, int] = {
    InstructionAuthority.PLATFORM.value: 0,
    InstructionAuthority.ORGANIZATION.value: 10,
    InstructionAuthority.TASK.value: 20,
    InstructionAuthority.REPOSITORY.value: 30,
    InstructionAuthority.SKILL.value: 40,
    InstructionAuthority.RETRIEVED.value: 90,
}

PROTECTED_AUTHORITIES = frozenset(
    {
        InstructionAuthority.PLATFORM.value,
        InstructionAuthority.ORGANIZATION.value,
        InstructionAuthority.TASK.value,
        InstructionAuthority.REPOSITORY.value,
    }
)


class InstructionContradictionError(ValueError):
    """Raised when equally authoritative structured instructions disagree."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = "INSTRUCTION_CONTRADICTION"
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class InstructionSource:
    """Raw instruction text plus provenance before ordering and hashing."""

    source: str
    authority: str | InstructionAuthority
    text: str
    sensitivity: str = "normal"
    constraint_key: str | None = None
    token_estimate: int | None = None
    protected: bool | None = None


@dataclass(frozen=True)
class ResolvedInstruction:
    """Instruction selected for context assembly."""

    span_id: str
    source: str
    authority: str
    text: str
    source_hash: str
    token_estimate: int
    sensitivity: str
    protected: bool
    precedence: int
    constraint_key: str | None = None


class InstructionResolver:
    """Resolve raw guidance into a deterministic, provenance-preserving order."""

    def resolve(
        self,
        sources: list[InstructionSource] | tuple[InstructionSource, ...],
        *,
        max_instruction_tokens: int | None = None,
    ) -> tuple[ResolvedInstruction, ...]:
        """Return ordered instructions, omitting low-authority items if a size cap is set."""

        resolved = tuple(self._resolve_one(index, source) for index, source in enumerate(sources))
        self._raise_on_structured_contradictions(resolved)

        ordered = tuple(sorted(resolved, key=lambda item: (item.precedence, item.source, item.span_id)))
        if max_instruction_tokens is None:
            return ordered
        if max_instruction_tokens < 0:
            raise ValueError("max_instruction_tokens must be non-negative")

        selected: list[ResolvedInstruction] = []
        total = 0
        for item in ordered:
            if total + item.token_estimate > max_instruction_tokens:
                continue
            selected.append(item)
            total += item.token_estimate
        return tuple(selected)

    def _resolve_one(self, index: int, source: InstructionSource) -> ResolvedInstruction:
        authority = _authority_value(source.authority)
        text = source.text.strip()
        if not source.source.strip():
            raise ValueError("instruction source must not be blank")
        if not text:
            raise ValueError("instruction text must not be blank")
        token_estimate = source.token_estimate if source.token_estimate is not None else estimate_tokens(text)
        if token_estimate <= 0:
            raise ValueError("instruction token estimate must be positive")
        protected = source.protected if source.protected is not None else authority in PROTECTED_AUTHORITIES
        return ResolvedInstruction(
            span_id=f"instruction:{authority}:{_safe_id(source.source, index)}",
            source=source.source,
            authority=authority,
            text=text,
            source_hash=content_hash(text),
            token_estimate=token_estimate,
            sensitivity=source.sensitivity,
            protected=protected,
            precedence=AUTHORITY_PRECEDENCE.get(authority, 80),
            constraint_key=source.constraint_key,
        )

    @staticmethod
    def _raise_on_structured_contradictions(instructions: tuple[ResolvedInstruction, ...]) -> None:
        seen: dict[tuple[str, str], ResolvedInstruction] = {}
        for instruction in instructions:
            if instruction.constraint_key is None:
                continue
            key = (instruction.authority, instruction.constraint_key)
            previous = seen.get(key)
            if previous is None:
                seen[key] = instruction
                continue
            if previous.text != instruction.text:
                raise InstructionContradictionError(
                    "conflicting instructions share the same authority and constraint key",
                    details={
                        "authority": instruction.authority,
                        "constraint_key": instruction.constraint_key,
                        "sources": (previous.source, instruction.source),
                    },
                )


def estimate_tokens(text: str) -> int:
    """Return a conservative deterministic token estimate for budgeting."""

    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, ceil(len(stripped) / 4))


def content_hash(text: str) -> str:
    """Return a stable hash for context provenance."""

    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def _authority_value(authority: str | InstructionAuthority) -> str:
    value = authority.value if isinstance(authority, InstructionAuthority) else authority
    if not value.strip():
        raise ValueError("instruction authority must not be blank")
    return value


def _safe_id(value: str, fallback: int) -> str:
    safe = "".join(character if character.isalnum() else "-" for character in value.strip().lower()).strip("-")
    return safe or str(fallback)
