"""Task-level recovery coordination before resume."""

from __future__ import annotations

from dataclasses import dataclass

from forgeweave.contracts import ToolExecution
from forgeweave.events import EventStore, ToolExecutionRecovery

from .state import TaskRecord, TaskStateMachine


@dataclass(frozen=True)
class TaskResumeRecoveryReport:
    """Outcome of reconciling a failed attempt before task resume."""

    task_id: str
    recovered_attempt_id: str
    cancelled_tool_executions: tuple[ToolExecution, ...]
    unknown_tool_executions: tuple[ToolExecution, ...]
    resumed_record: TaskRecord | None = None

    @property
    def can_continue(self) -> bool:
        """Return true when no ambiguous side effects block resume."""

        return self.resumed_record is not None and not self.unknown_tool_executions


class TaskRecoveryCoordinator:
    """Coordinate tool restart reconciliation with task resume.

    Resuming a task is only safe after the previous attempt's tool execution
    projections are reconciled. Calls that never reached dispatch are cancelled.
    Calls that were dispatching at crash time are parked as OUTCOME_UNKNOWN and
    block automatic resume so a human or recovery subsystem can inspect them.
    """

    def __init__(self, *, events: EventStore, tasks: TaskStateMachine) -> None:
        self._tool_recovery = ToolExecutionRecovery(events)
        self._tasks = tasks

    def prepare_resume(
        self,
        *,
        task_id: str,
        recovered_attempt_id: str,
        new_attempt_id: str,
        evidence: str,
    ) -> TaskResumeRecoveryReport:
        """Reconcile a failed attempt, then resume only when no side effect is ambiguous."""

        report = self._tool_recovery.reconcile_after_restart(
            evidence=evidence,
            task_id=task_id,
            attempt_id=recovered_attempt_id,
        )
        if report.requires_attention:
            return TaskResumeRecoveryReport(
                task_id=task_id,
                recovered_attempt_id=recovered_attempt_id,
                cancelled_tool_executions=report.cancelled,
                unknown_tool_executions=report.outcome_unknown,
                resumed_record=None,
            )

        resumed = self._tasks.resume(task_id, new_attempt_id=new_attempt_id)
        return TaskResumeRecoveryReport(
            task_id=task_id,
            recovered_attempt_id=recovered_attempt_id,
            cancelled_tool_executions=report.cancelled,
            unknown_tool_executions=(),
            resumed_record=resumed,
        )
