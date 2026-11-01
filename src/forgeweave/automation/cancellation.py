"""Bounded workflow cancellation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkflowRunStatus, WorkflowStepStatus
from .store import WorkflowStore, WorkflowStoreError

_CANCELLABLE_ATTEMPT_STATUSES = {
    WorkflowStepStatus.PENDING,
    WorkflowStepStatus.READY,
    WorkflowStepStatus.RUNNING,
    WorkflowStepStatus.WAITING_APPROVAL,
    WorkflowStepStatus.WAITING_EXTERNAL,
}
_TERMINAL_RUN_STATUSES = {WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED}


@dataclass(frozen=True)
class WorkflowCancellationResult:
    """Result of cancelling one workflow run within an explicit bound."""

    run_id: str
    run_status: WorkflowRunStatus
    cancelled_attempt_ids: tuple[str, ...]
    reason: str


def cancel_workflow_run(
    store: WorkflowStore,
    *,
    run_id: str,
    reason: str,
    max_attempts: int,
) -> WorkflowCancellationResult:
    """Cancel a workflow run and at most ``max_attempts`` active attempts."""

    if not reason.strip():
        raise WorkflowStoreError("BLANK_CANCELLATION_REASON", "workflow cancellation reason must not be blank")
    if max_attempts < 0:
        raise WorkflowStoreError("INVALID_CANCELLATION_BOUND", "max_attempts must be >= 0")
    run = store.get_run(run_id)
    if run.status in _TERMINAL_RUN_STATUSES:
        raise WorkflowStoreError("RUN_ALREADY_TERMINAL", f"workflow run {run_id} is already {run.status.value}")
    cancellable = tuple(
        attempt
        for attempt in store.list_attempts(run_id)
        if attempt.status in _CANCELLABLE_ATTEMPT_STATUSES
    )
    if len(cancellable) > max_attempts:
        raise WorkflowStoreError(
            "CANCELLATION_BOUND_EXCEEDED",
            f"workflow run {run_id} has {len(cancellable)} cancellable attempts, exceeding bound {max_attempts}",
        )
    cancelled_ids: list[str] = []
    for attempt in cancellable:
        updated = store.update_attempt_status(attempt.attempt_id, WorkflowStepStatus.CANCELLED)
        cancelled_ids.append(updated.attempt_id)
    cancelled_run = store.update_run_status(run_id, WorkflowRunStatus.CANCELLED)
    return WorkflowCancellationResult(
        run_id=cancelled_run.run_id,
        run_status=cancelled_run.status,
        cancelled_attempt_ids=tuple(cancelled_ids),
        reason=reason.strip(),
    )
