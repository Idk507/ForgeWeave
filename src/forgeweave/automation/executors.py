"""Mediated workflow step executor registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .contracts import WorkflowStep, WorkflowStepKind, WorkflowStepStatus


class WorkflowExecutorError(ValueError):
    """Raised when a workflow step executor cannot be selected or run."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WorkflowExecutionContext:
    """Bounded context passed to one mediated workflow step executor."""

    run_id: str
    workflow_id: str
    step: WorkflowStep
    attempt_number: int


@dataclass(frozen=True)
class WorkflowExecutionResult:
    """Result returned by a mediated workflow step executor."""

    status: WorkflowStepStatus
    reason: str
    output: dict[str, Any] | None = None


WorkflowStepExecutor = Callable[[WorkflowExecutionContext], WorkflowExecutionResult]


class WorkflowExecutorRegistry:
    """Registry of explicitly mediated workflow step executors."""

    def __init__(self) -> None:
        self._executors: dict[tuple[WorkflowStepKind, str | None], WorkflowStepExecutor] = {}

    def register(self, kind: WorkflowStepKind, executor: WorkflowStepExecutor, *, capability: str | None = None) -> None:
        """Register one executor for a step kind and optional capability."""

        key = (kind, capability)
        if key in self._executors:
            label = f"{kind.value}:{capability or '*'}"
            raise WorkflowExecutorError("DUPLICATE_EXECUTOR", f"workflow executor already registered: {label}")
        self._executors[key] = executor

    def execute(self, context: WorkflowExecutionContext) -> WorkflowExecutionResult:
        """Execute one step through an explicitly registered executor."""

        executor = self._resolve(context.step)
        if executor is None:
            return WorkflowExecutionResult(
                status=WorkflowStepStatus.WAITING_EXTERNAL,
                reason=f"no mediated executor registered for {context.step.kind.value}:{context.step.capability or '*'}",
            )
        result = executor(context)
        _validate_result(result)
        return result

    def _resolve(self, step: WorkflowStep) -> WorkflowStepExecutor | None:
        return self._executors.get((step.kind, step.capability)) or self._executors.get((step.kind, None))


def _validate_result(result: WorkflowExecutionResult) -> None:
    if result.status is WorkflowStepStatus.PENDING or result.status is WorkflowStepStatus.READY:
        raise WorkflowExecutorError("INVALID_EXECUTOR_STATUS", f"executor returned non-terminal scheduling status: {result.status.value}")
    if not result.reason.strip():
        raise WorkflowExecutorError("MISSING_EXECUTOR_REASON", "executor result reason must not be blank")
