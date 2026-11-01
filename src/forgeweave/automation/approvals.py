"""Approval pause and resume helpers for workflow runs.

Approval steps are explicit human or external decision boundaries. The runner
records them as waiting approval and pauses the run; this module is the only
workflow automation surface that resumes or rejects those attempts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import StepAttempt, WorkflowRunStatus, WorkflowStepKind, WorkflowStepStatus
from .store import WorkflowStore, WorkflowStoreError

ApprovalAction = Literal["approve", "reject", "cancel"]


@dataclass(frozen=True)
class WorkflowApprovalResult:
    """Evidence for one approval decision applied to a workflow step."""

    run_id: str
    step_id: str
    attempt_id: str
    action: ApprovalAction
    step_status: WorkflowStepStatus
    run_status: WorkflowRunStatus
    reason: str


def approve_workflow_step(
    store: WorkflowStore,
    *,
    run_id: str,
    step_id: str,
    reason: str = "approval granted",
) -> WorkflowApprovalResult:
    """Mark a waiting approval step as succeeded and resume the run."""

    return _apply_approval_decision(store, run_id=run_id, step_id=step_id, action="approve", reason=reason)


def reject_workflow_step(
    store: WorkflowStore,
    *,
    run_id: str,
    step_id: str,
    reason: str = "approval rejected",
) -> WorkflowApprovalResult:
    """Mark a waiting approval step as failed and fail the run."""

    return _apply_approval_decision(store, run_id=run_id, step_id=step_id, action="reject", reason=reason)


def cancel_workflow_step_approval(
    store: WorkflowStore,
    *,
    run_id: str,
    step_id: str,
    reason: str = "approval cancelled",
) -> WorkflowApprovalResult:
    """Mark a waiting approval step as cancelled and cancel the run."""

    return _apply_approval_decision(store, run_id=run_id, step_id=step_id, action="cancel", reason=reason)


def _apply_approval_decision(
    store: WorkflowStore,
    *,
    run_id: str,
    step_id: str,
    action: ApprovalAction,
    reason: str,
) -> WorkflowApprovalResult:
    if not reason.strip():
        raise WorkflowStoreError("BLANK_APPROVAL_REASON", "approval decision reason must not be blank")

    run = store.get_run(run_id)
    definition = store.get_definition(run.definition_hash)
    step_by_id = {step.step_id: step for step in definition.steps}
    step = step_by_id.get(step_id)
    if step is None:
        raise WorkflowStoreError("UNKNOWN_APPROVAL_STEP", f"workflow step does not exist: {step_id}")
    if step.kind is not WorkflowStepKind.APPROVAL:
        raise WorkflowStoreError("NOT_APPROVAL_STEP", f"workflow step is not an approval boundary: {step_id}")

    attempt = _latest_attempt_for_step(store.list_attempts(run_id), step_id)
    if attempt is None:
        raise WorkflowStoreError("APPROVAL_ATTEMPT_NOT_FOUND", f"approval step has no persisted attempt: {step_id}")
    if attempt.status is not WorkflowStepStatus.WAITING_APPROVAL:
        raise WorkflowStoreError(
            "APPROVAL_NOT_WAITING",
            f"approval step is not waiting for a decision: {step_id} is {attempt.status.value}",
        )

    if action == "approve":
        step_status = WorkflowStepStatus.SUCCEEDED
        run_status = WorkflowRunStatus.RUNNING
    elif action == "reject":
        step_status = WorkflowStepStatus.FAILED
        run_status = WorkflowRunStatus.FAILED
    else:
        step_status = WorkflowStepStatus.CANCELLED
        run_status = WorkflowRunStatus.CANCELLED

    updated_attempt = store.update_attempt_status(attempt.attempt_id, step_status)
    updated_run = store.update_run_status(run_id, run_status)
    return WorkflowApprovalResult(
        run_id=updated_run.run_id,
        step_id=step_id,
        attempt_id=updated_attempt.attempt_id,
        action=action,
        step_status=updated_attempt.status,
        run_status=updated_run.status,
        reason=reason.strip(),
    )


def _latest_attempt_for_step(attempts: tuple[StepAttempt, ...], step_id: str) -> StepAttempt | None:
    latest: StepAttempt | None = None
    for attempt in attempts:
        if attempt.step_id == step_id:
            latest = attempt
    return latest
