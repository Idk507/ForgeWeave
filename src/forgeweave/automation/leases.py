"""Lease fencing helpers for workflow step attempts.

Workflow attempts may be resumed or completed by a worker after a crash or after
another worker has already taken over. These helpers make the lease token an
explicit precondition before mutating attempt state so stale workers cannot
silently overwrite newer progress.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkflowStepStatus
from .store import WorkflowStore, WorkflowStoreError


@dataclass(frozen=True)
class WorkflowStepLeaseResult:
    """Result of checking whether a step attempt lease token is still valid."""

    allowed: bool
    code: str
    message: str
    run_id: str | None = None
    step_id: str | None = None
    attempt_id: str | None = None
    lease_token: str | None = None


def require_step_lease(
    store: WorkflowStore,
    *,
    attempt_id: str,
    lease_token: str,
    worker_id: str | None = None,
) -> WorkflowStepLeaseResult:
    """Return whether ``lease_token`` may update ``attempt_id``.

    The check is intentionally side-effect free. Callers can use the structured
    denial code for logs, traces or retry decisions before choosing whether to
    raise or report a recoverable workflow conflict.
    """

    normalized_attempt_id = attempt_id.strip()
    normalized_token = lease_token.strip()
    if not normalized_attempt_id:
        return WorkflowStepLeaseResult(
            allowed=False,
            code="MISSING_ATTEMPT_ID",
            message="workflow step lease check requires a non-empty attempt id",
        )
    if not normalized_token:
        return WorkflowStepLeaseResult(
            allowed=False,
            code="MISSING_LEASE_TOKEN",
            message="workflow step lease check requires a non-empty lease token",
            attempt_id=normalized_attempt_id,
        )
    normalized_worker_id = worker_id.strip() if worker_id is not None else None
    if worker_id is not None and not normalized_worker_id:
        return WorkflowStepLeaseResult(
            allowed=False,
            code="MISSING_WORKER_ID",
            message="workflow step lease check requires a non-empty worker id when worker fencing is requested",
            attempt_id=normalized_attempt_id,
            lease_token=normalized_token,
        )

    try:
        attempt = store.get_attempt(normalized_attempt_id)
    except KeyError:
        return WorkflowStepLeaseResult(
            allowed=False,
            code="ATTEMPT_NOT_FOUND",
            message=f"workflow step attempt does not exist: {normalized_attempt_id}",
            attempt_id=normalized_attempt_id,
            lease_token=normalized_token,
        )

    if attempt.lease_token is None or not attempt.lease_token.strip():
        return WorkflowStepLeaseResult(
            allowed=False,
            code="LEASE_NOT_RECORDED",
            message=f"workflow step attempt has no recorded lease token: {normalized_attempt_id}",
            run_id=attempt.run_id,
            step_id=attempt.step_id,
            attempt_id=attempt.attempt_id,
            lease_token=normalized_token,
        )
    if attempt.lease_token != normalized_token:
        return WorkflowStepLeaseResult(
            allowed=False,
            code="LEASE_TOKEN_MISMATCH",
            message=f"workflow step attempt lease token is stale: {normalized_attempt_id}",
            run_id=attempt.run_id,
            step_id=attempt.step_id,
            attempt_id=attempt.attempt_id,
            lease_token=normalized_token,
        )
    if normalized_worker_id is not None and attempt.worker_id != normalized_worker_id:
        return WorkflowStepLeaseResult(
            allowed=False,
            code="WORKER_ID_MISMATCH",
            message=f"workflow step attempt worker owner is stale: {normalized_attempt_id}",
            run_id=attempt.run_id,
            step_id=attempt.step_id,
            attempt_id=attempt.attempt_id,
            lease_token=normalized_token,
        )
    return WorkflowStepLeaseResult(
        allowed=True,
        code="LEASE_ACTIVE",
        message=f"workflow step attempt lease token is active: {normalized_attempt_id}",
        run_id=attempt.run_id,
        step_id=attempt.step_id,
        attempt_id=attempt.attempt_id,
        lease_token=normalized_token,
    )


def assert_step_lease(
    store: WorkflowStore,
    *,
    attempt_id: str,
    lease_token: str,
    worker_id: str | None = None,
) -> WorkflowStepLeaseResult:
    """Return the active lease result or raise ``WorkflowStoreError``."""

    result = require_step_lease(store, attempt_id=attempt_id, lease_token=lease_token, worker_id=worker_id)
    if not result.allowed:
        raise WorkflowStoreError(result.code, result.message)
    return result


def update_attempt_status_with_lease(
    store: WorkflowStore,
    *,
    attempt_id: str,
    status: WorkflowStepStatus,
    lease_token: str,
    worker_id: str | None = None,
):
    """Update an attempt status only when the caller owns its active lease."""

    assert_step_lease(store, attempt_id=attempt_id, lease_token=lease_token, worker_id=worker_id)
    return store.update_attempt_status(attempt_id, status)
