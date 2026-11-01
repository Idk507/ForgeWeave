"""Durable workflow worker lease ownership helpers."""

from __future__ import annotations

from hashlib import sha256


def workflow_worker_lease_token(*, worker_id: str, run_id: str, step_id: str, attempt_number: int) -> str:
    """Return a stable opaque lease token for one worker-owned step attempt."""

    for label, value in (("worker_id", worker_id), ("run_id", run_id), ("step_id", step_id)):
        if not value.strip():
            raise ValueError(f"{label} must not be blank")
    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")
    payload = "|".join((worker_id, run_id, step_id, str(attempt_number))).encode("utf-8")
    return "workflow-lease:" + sha256(payload).hexdigest()
