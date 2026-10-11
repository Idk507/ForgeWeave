"""Restart reconciliation for persisted tool executions."""

from __future__ import annotations

from dataclasses import dataclass

from forgeweave.contracts import ToolExecution, ToolExecutionState

from .store import EventStore


@dataclass(frozen=True)
class ToolRecoveryReport:
    """Summary of tool executions reconciled during process restart."""

    cancelled: tuple[ToolExecution, ...]
    outcome_unknown: tuple[ToolExecution, ...]
    unchanged: tuple[ToolExecution, ...]

    @property
    def requires_attention(self) -> bool:
        """Return true when at least one side effect may have happened."""

        return bool(self.outcome_unknown)


class ToolExecutionRecovery:
    """Reconcile in-flight tool execution records after a process restart.

    A call that was only requested or authorized has not crossed the dispatch
    boundary, so it can be cancelled and the agent may plan again. A call that
    was already dispatching may have produced a side effect before the crash; it
    is marked OUTCOME_UNKNOWN and must be inspected before retrying.
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def reconcile_after_restart(
        self,
        *,
        evidence: str,
        task_id: str | None = None,
        attempt_id: str | None = None,
    ) -> ToolRecoveryReport:
        """Reconcile non-terminal tool executions and return a report."""

        if not evidence.strip():
            raise ValueError("restart reconciliation evidence must not be blank")
        cancelled: list[ToolExecution] = []
        outcome_unknown: list[ToolExecution] = []
        unchanged: list[ToolExecution] = []

        for execution in self._store.list_tool_executions():
            if task_id is not None and execution.task_id != task_id:
                unchanged.append(execution)
                continue
            if attempt_id is not None and execution.attempt_id != attempt_id:
                unchanged.append(execution)
                continue
            if execution.state in {ToolExecutionState.REQUESTED, ToolExecutionState.AUTHORIZED}:
                reconciled = self._store.record_tool_execution(
                    execution.model_copy(update={"state": ToolExecutionState.CANCELLED})
                )
                cancelled.append(reconciled)
                continue
            if execution.state is ToolExecutionState.DISPATCHING:
                reconciled = self._store.record_tool_execution(
                    execution.model_copy(
                        update={
                            "state": ToolExecutionState.OUTCOME_UNKNOWN,
                            "reconciliation_evidence": evidence,
                        }
                    )
                )
                outcome_unknown.append(reconciled)
                continue
            unchanged.append(execution)

        return ToolRecoveryReport(
            cancelled=tuple(cancelled),
            outcome_unknown=tuple(outcome_unknown),
            unchanged=tuple(unchanged),
        )
