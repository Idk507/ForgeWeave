"""Workflow restart recovery helpers.

Recovery is intentionally conservative: after a process crash, attempts that were
persisted as RUNNING may have already submitted side effects. They are therefore
moved to WAITING_EXTERNAL for inspection rather than replayed automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkflowRunStatus, WorkflowStepStatus
from .store import WorkflowStore, WorkflowStoreError


@dataclass(frozen=True)
class WorkflowRecoveryAttention:
    """One persisted attempt requiring operator or higher-level recovery attention."""

    attempt_id: str
    run_id: str
    step_id: str
    previous_status: WorkflowStepStatus
    recovered_status: WorkflowStepStatus
    reason: str


@dataclass(frozen=True)
class WorkflowRecoveryResult:
    """Result of reconciling a workflow run after restart."""

    run_id: str
    run_status: WorkflowRunStatus
    attentions: tuple[WorkflowRecoveryAttention, ...]


def recover_workflow_after_restart(
    store: WorkflowStore,
    *,
    run_id: str,
    max_attempts: int,
    mark_waiting_external: bool = True,
) -> WorkflowRecoveryResult:
    """Reconcile in-flight attempts after a restart without replaying effects."""

    if max_attempts < 0:
        raise WorkflowStoreError("INVALID_RECOVERY_BOUND", "max_attempts must be >= 0")
    run = store.get_run(run_id)
    in_flight = tuple(attempt for attempt in store.list_attempts(run_id) if attempt.status is WorkflowStepStatus.RUNNING)
    if len(in_flight) > max_attempts:
        raise WorkflowStoreError(
            "RECOVERY_BOUND_EXCEEDED",
            f"workflow run {run_id} has {len(in_flight)} in-flight attempts, exceeding bound {max_attempts}",
        )
    attentions: list[WorkflowRecoveryAttention] = []
    for attempt in in_flight:
        recovered_status = WorkflowStepStatus.WAITING_EXTERNAL if mark_waiting_external else attempt.status
        if mark_waiting_external:
            store.update_attempt_status(attempt.attempt_id, recovered_status)
        attentions.append(
            WorkflowRecoveryAttention(
                attempt_id=attempt.attempt_id,
                run_id=attempt.run_id,
                step_id=attempt.step_id,
                previous_status=attempt.status,
                recovered_status=recovered_status,
                reason="attempt was running during restart; external outcome requires inspection",
            )
        )
    if mark_waiting_external and attentions and run.status is WorkflowRunStatus.RUNNING:
        run = store.update_run_status(run_id, WorkflowRunStatus.WAITING_EXTERNAL)
    else:
        run = store.get_run(run_id)
    return WorkflowRecoveryResult(run_id=run.run_id, run_status=run.status, attentions=tuple(attentions))
