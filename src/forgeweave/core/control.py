"""Cancellation and budget controls for native ForgeWeave loops."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Callable


class CancellationToken:
    """Shared cancellation state checked by streams, tools and loops."""

    def __init__(self) -> None:
        self._cancelled = False
        self._reason: str | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def reason(self) -> str | None:
        return self._reason

    def cancel(self, reason: str = "cancelled") -> None:
        """Mark this token cancelled; first reason wins for stable reporting."""

        if not reason.strip():
            raise ValueError("cancellation reason must not be blank")
        if not self._cancelled:
            self._cancelled = True
            self._reason = reason

    def raise_if_cancelled(self) -> None:
        """Raise `InterruptedError` when cancellation has been requested."""

        if self._cancelled:
            raise InterruptedError(self._reason or "cancelled")


class BudgetExceeded(RuntimeError):
    """Structured budget error for controller stop decisions."""

    def __init__(self, code: str, message: str, *, limit: int | float | None, actual: int | float) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.limit = limit
        self.actual = actual


@dataclass(frozen=True)
class BudgetLimits:
    """Finite limits for one task attempt. `None` means no limit in that dimension."""

    max_turns: int | None = None
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    max_delegation_depth: int | None = None
    max_context_tokens: int | None = None
    max_wall_seconds: float | None = None

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if value is None:
                continue
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be non-negative or None")


@dataclass(frozen=True)
class BudgetUsage:
    """Measured usage for a task attempt."""

    turns: int = 0
    tokens: int = 0
    tool_calls: int = 0
    delegation_depth: int = 0
    context_tokens: int = 0

    def record_turn(self) -> "BudgetUsage":
        return self._copy(turns=self.turns + 1)

    def record_model_usage(self, *, tokens: int) -> "BudgetUsage":
        if tokens < 0:
            raise ValueError("tokens must be non-negative")
        return self._copy(tokens=self.tokens + tokens)

    def record_tool_call(self) -> "BudgetUsage":
        return self._copy(tool_calls=self.tool_calls + 1)

    def with_context_tokens(self, tokens: int) -> "BudgetUsage":
        if tokens < 0:
            raise ValueError("context tokens must be non-negative")
        return self._copy(context_tokens=tokens)

    def with_delegation_depth(self, depth: int) -> "BudgetUsage":
        if depth < 0:
            raise ValueError("delegation depth must be non-negative")
        return self._copy(delegation_depth=depth)

    def _copy(self, **updates: int) -> "BudgetUsage":
        values = {
            "turns": self.turns,
            "tokens": self.tokens,
            "tool_calls": self.tool_calls,
            "delegation_depth": self.delegation_depth,
            "context_tokens": self.context_tokens,
        }
        values.update(updates)
        return BudgetUsage(**values)


class BudgetGuard:
    """Check budget usage and fail closed with structured reasons."""

    def __init__(self, limits: BudgetLimits, *, now: Callable[[], float] = monotonic) -> None:
        self._limits = limits
        self._started_at = now()

    def check(self, usage: BudgetUsage, *, now: float | None = None) -> None:
        """Raise `BudgetExceeded` if any configured limit is exceeded."""

        self._check_integer("TURN_BUDGET_EXCEEDED", "turn budget exceeded", self._limits.max_turns, usage.turns)
        self._check_integer("TOKEN_BUDGET_EXCEEDED", "token budget exceeded", self._limits.max_tokens, usage.tokens)
        self._check_integer("TOOL_CALL_BUDGET_EXCEEDED", "tool-call budget exceeded", self._limits.max_tool_calls, usage.tool_calls)
        self._check_integer(
            "DELEGATION_DEPTH_EXCEEDED",
            "delegation depth exceeded",
            self._limits.max_delegation_depth,
            usage.delegation_depth,
        )
        self._check_integer(
            "CONTEXT_BUDGET_EXCEEDED",
            "context token budget exceeded",
            self._limits.max_context_tokens,
            usage.context_tokens,
        )
        if self._limits.max_wall_seconds is not None:
            elapsed = (monotonic() if now is None else now) - self._started_at
            if elapsed > self._limits.max_wall_seconds:
                raise BudgetExceeded(
                    "WALL_TIME_BUDGET_EXCEEDED",
                    "wall-clock budget exceeded",
                    limit=self._limits.max_wall_seconds,
                    actual=elapsed,
                )

    @staticmethod
    def _check_integer(code: str, message: str, limit: int | None, actual: int) -> None:
        if limit is not None and actual > limit:
            raise BudgetExceeded(code, message, limit=limit, actual=actual)
