"""Contracts for optional delegated engines (plan.md section 4.1)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class IsolationLevel(str, Enum):
    """How much of the engine's activity ForgeWeave's policy gateway can authorize."""

    MEDIATED = "mediated"
    DELEGATED_UNMEDIATED = "delegated-unmediated"


class EngineUnavailable(RuntimeError):
    """Raised when an engine extra is missing, mismatched or unsafe to run."""


class EngineRequest(BaseModel):
    """One ForgeWeave task handed to an engine; one task maps to one worktree."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    task_id: str
    attempt_id: str
    session_id: str
    prompt: str
    worktree: Path
    original_checkout: Path
    engine_home: Path
    isolation: IsolationLevel
    delegated_opt_in: bool = False
    requested_effects: frozenset[str] = frozenset()
    provider: str | None = None
    model: str | None = None


class EngineEvent(BaseModel):
    """Imported engine observation. Always untrusted; never a policy input."""

    engine: str
    sequence: int
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    trusted: Literal[False] = False


class EngineResult(BaseModel):
    """Outcome reported by an engine. The claim is not completion; the verifier decides."""

    status: Literal["completed", "failed", "cancelled"]
    claimed_final_response: str | None = None
    finish_reason: str | None = None
    engine_session_id: str | None = None
    events: list[EngineEvent] = Field(default_factory=list)
    authoritative: Literal[False] = False


OnEvent = Callable[[EngineEvent], None]


class CancelToken:
    """Minimal cancellation flag shared between the task controller and an engine."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class DelegatedEngine(Protocol):
    """Backend that runs a whole task outside ForgeWeave's native loop."""

    name: str
    isolation: IsolationLevel

    def check_available(self) -> None:
        """Raise EngineUnavailable if the engine cannot be run safely."""

    async def run(self, request: EngineRequest, on_event: OnEvent, cancel: CancelToken) -> EngineResult:
        """Run the task and stream imported events; must stop promptly on cancel."""
