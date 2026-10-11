"""Structured stop decisions for native agent loops."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from forgeweave.contracts import PolicyOutcome
from forgeweave.core.control import BudgetExceeded, CancellationToken


class StopReason(StrEnum):
    """Canonical reasons a core loop step stops or continues."""

    CONTINUE = "continue"
    FINAL_ANSWER = "final_answer"
    WAITING_APPROVAL = "waiting_approval"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"
    FAILED = "failed"


@dataclass(frozen=True)
class StopDecision:
    """Decision emitted after evaluating one loop stop condition."""

    reason: StopReason
    should_stop: bool
    details: dict[str, Any]


class StopEvaluator:
    """Map loop state and structured errors into canonical stop decisions."""

    def after_model_turn(self, *, text: str, tool_request_count: int, pending_approval: bool) -> StopDecision:
        """Evaluate whether a model turn ended with a final answer or needs more work."""

        if pending_approval:
            return StopDecision(StopReason.WAITING_APPROVAL, True, {})
        if tool_request_count > 0:
            return StopDecision(StopReason.CONTINUE, False, {"tool_request_count": tool_request_count})
        if text.strip():
            return StopDecision(StopReason.FINAL_ANSWER, True, {})
        return StopDecision(StopReason.FAILED, True, {"message": "model produced neither text nor tool requests"})

    def after_policy_decisions(self, outcomes: Iterable[PolicyOutcome]) -> StopDecision:
        """Stop when any policy decision requires human approval."""

        if any(outcome is PolicyOutcome.ASK for outcome in outcomes):
            return StopDecision(StopReason.WAITING_APPROVAL, True, {})
        return StopDecision(StopReason.CONTINUE, False, {})

    def from_cancellation(self, token: CancellationToken) -> StopDecision:
        """Return a cancellation stop decision when the token has been cancelled."""

        if token.cancelled:
            return StopDecision(StopReason.CANCELLED, True, {"message": token.reason or "cancelled"})
        return StopDecision(StopReason.CONTINUE, False, {})

    def from_budget_error(self, error: BudgetExceeded) -> StopDecision:
        """Convert a budget exception into a stable stop decision."""

        return StopDecision(
            StopReason.BUDGET_EXCEEDED,
            True,
            {
                "code": error.code,
                "message": error.message,
                "limit": error.limit,
                "actual": error.actual,
            },
        )
