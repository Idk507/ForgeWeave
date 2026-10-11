"""Workspace lease fencing checks for mutation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .locks import WorkspaceLock, WorkspaceLockError, WorkspaceLockStore


@dataclass(frozen=True)
class LeaseFenceResult:
    """Result of validating that a caller still owns a workspace lease."""

    allowed: bool
    code: str
    message: str
    lock_id: str
    owner: str
    target: str


def require_active_lease(
    store: WorkspaceLockStore,
    lock: WorkspaceLock,
    *,
    now: datetime | None = None,
) -> LeaseFenceResult:
    """Validate a lease immediately before a workspace mutation.

    The caller must present the exact owner and token it acquired. A stale,
    expired or replaced lock is rejected with structured evidence that can be
    recorded by the caller before aborting the mutation.
    """

    try:
        current = store.current(scope=lock.scope, target=lock.target, now=now)
    except WorkspaceLockError as exc:
        return _denied(lock, code=exc.code, message=exc.message)
    if current is None:
        return _denied(lock, code="LOCK_NOT_ACTIVE", message=f"{lock.scope.value} lock is not active for {lock.target}")
    if current.owner != lock.owner or current.token != lock.token:
        return _denied(lock, code="LOCK_TOKEN_MISMATCH", message=f"{lock.scope.value} lock token mismatch for {lock.target}")
    return LeaseFenceResult(
        allowed=True,
        code="LEASE_ACTIVE",
        message=f"{lock.scope.value} lease is active for {lock.target}",
        lock_id=current.lock_id,
        owner=current.owner,
        target=current.target,
    )


def assert_active_lease(
    store: WorkspaceLockStore,
    lock: WorkspaceLock,
    *,
    now: datetime | None = None,
) -> LeaseFenceResult:
    """Return active lease evidence or raise `WorkspaceLockError` when stale."""

    result = require_active_lease(store, lock, now=now)
    if not result.allowed:
        raise WorkspaceLockError(result.code, result.message)
    return result


def _denied(lock: WorkspaceLock, *, code: str, message: str) -> LeaseFenceResult:
    return LeaseFenceResult(
        allowed=False,
        code=code,
        message=message,
        lock_id=lock.lock_id,
        owner=lock.owner,
        target=lock.target,
    )
