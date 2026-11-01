"""Workflow idempotency key helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class WorkflowAttemptIdentity:
    """Stable identity for one workflow step attempt."""

    attempt_id: str
    idempotency_key: str
    attempt_number: int


def workflow_attempt_identity(*, run_id: str, step_id: str, attempt_number: int) -> WorkflowAttemptIdentity:
    """Return deterministic attempt identity for a run/step/attempt number."""

    for label, value in (("run_id", run_id), ("step_id", step_id)):
        if not value.strip():
            raise ValueError(f"{label} must not be blank")
    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")
    attempt_id = f"{run_id}-{step_id}-{attempt_number}"
    digest = sha256(f"{run_id}|{step_id}|{attempt_number}".encode("utf-8")).hexdigest()
    return WorkflowAttemptIdentity(
        attempt_id=attempt_id,
        idempotency_key=f"workflow-step:{digest}",
        attempt_number=attempt_number,
    )
