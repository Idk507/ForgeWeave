"""SQLite-backed fenced locks for repository and worktree mutations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
import sqlite3
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class LockScope(StrEnum):
    """Mutation scope protected by a workspace lock."""

    REPOSITORY = "repo"
    WORKTREE = "worktree"


class WorkspaceLockError(ValueError):
    """Raised when a workspace lock cannot be acquired, refreshed, or released."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkspaceLock(BaseModel):
    """A fenced lease over one repository or worktree target."""

    model_config = ConfigDict(frozen=True)

    lock_id: str = Field(min_length=1)
    scope: LockScope
    target: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    token: str = Field(min_length=1)
    expires_at: datetime


class WorkspaceLockStore:
    """Persist repo/worktree locks in SQLite WAL mode.

    Locks are keyed by ``(scope, target)`` and protected by an opaque token. A
    caller must present the current token to refresh or release a lock, which
    prevents stale workers from accidentally clearing a newer lease.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @classmethod
    def open(cls, path: Path) -> "WorkspaceLockStore":
        """Open a lock store and initialize the schema."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_locks (
                scope TEXT NOT NULL,
                target TEXT NOT NULL,
                lock_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY(scope, target)
            )
            """
        )
        connection.commit()
        return cls(connection)

    def close(self) -> None:
        """Close the store after checkpointing the WAL."""

        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()

    def acquire(
        self,
        *,
        scope: LockScope,
        target: str,
        owner: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> WorkspaceLock:
        """Acquire a lock or replace an expired lock for the same target."""

        checked_now = _normalize_now(now)
        self._validate_inputs(target=target, owner=owner, ttl_seconds=ttl_seconds)
        target_value = target.strip()
        lock = WorkspaceLock(
            lock_id=f"lock-{uuid4().hex}",
            scope=scope,
            target=target_value,
            owner=owner.strip(),
            token=f"token-{uuid4().hex}",
            expires_at=checked_now + timedelta(seconds=ttl_seconds),
        )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            current = self._current_row(scope=scope, target=target_value)
            if current is not None and current.expires_at > checked_now:
                raise WorkspaceLockError("LOCK_HELD", f"{scope.value} lock is held for {target_value}")
            self._connection.execute(
                """
                INSERT OR REPLACE INTO workspace_locks(scope, target, lock_id, owner, token, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                self._to_row(lock),
            )
        except Exception:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()
        return lock

    def current(self, *, scope: LockScope, target: str, now: datetime | None = None) -> WorkspaceLock | None:
        """Return the active lock for a target, or clear and return None when expired."""

        checked_now = _normalize_now(now)
        lock = self._current_row(scope=scope, target=target.strip())
        if lock is None:
            return None
        if lock.expires_at <= checked_now:
            with self._connection:
                self._connection.execute(
                    "DELETE FROM workspace_locks WHERE scope = ? AND target = ? AND token = ?",
                    (lock.scope.value, lock.target, lock.token),
                )
            return None
        return lock

    def refresh(self, lock: WorkspaceLock, *, ttl_seconds: int, now: datetime | None = None) -> WorkspaceLock:
        """Extend an active lock when the owner and token still match."""

        checked_now = _normalize_now(now)
        self._validate_inputs(target=lock.target, owner=lock.owner, ttl_seconds=ttl_seconds)
        current = self._require_matching_lock(lock, now=checked_now)
        if current.expires_at <= checked_now:
            raise WorkspaceLockError("LOCK_EXPIRED", f"{lock.scope.value} lock expired for {lock.target}")

        refreshed = current.model_copy(update={"expires_at": checked_now + timedelta(seconds=ttl_seconds)})
        with self._connection:
            self._connection.execute(
                """
                UPDATE workspace_locks
                SET expires_at = ?
                WHERE scope = ? AND target = ? AND owner = ? AND token = ?
                """,
                (
                    refreshed.expires_at.isoformat(),
                    refreshed.scope.value,
                    refreshed.target,
                    refreshed.owner,
                    refreshed.token,
                ),
            )
        return refreshed

    def release(self, lock: WorkspaceLock) -> None:
        """Release a lock only when the owner and fencing token match."""

        self._require_matching_lock(lock, now=_normalize_now(None), allow_expired=True)
        with self._connection:
            self._connection.execute(
                "DELETE FROM workspace_locks WHERE scope = ? AND target = ? AND owner = ? AND token = ?",
                (lock.scope.value, lock.target, lock.owner, lock.token),
            )

    def _require_matching_lock(
        self,
        lock: WorkspaceLock,
        *,
        now: datetime,
        allow_expired: bool = False,
    ) -> WorkspaceLock:
        current = self._current_row(scope=lock.scope, target=lock.target)
        if current is None:
            raise WorkspaceLockError("LOCK_NOT_FOUND", f"{lock.scope.value} lock is not held for {lock.target}")
        if current.owner != lock.owner or current.token != lock.token:
            raise WorkspaceLockError("LOCK_TOKEN_MISMATCH", f"{lock.scope.value} lock token mismatch for {lock.target}")
        if not allow_expired and current.expires_at <= now:
            raise WorkspaceLockError("LOCK_EXPIRED", f"{lock.scope.value} lock expired for {lock.target}")
        return current

    def _current_row(self, *, scope: LockScope, target: str) -> WorkspaceLock | None:
        row = self._connection.execute(
            """
            SELECT lock_id, scope, target, owner, token, expires_at
            FROM workspace_locks
            WHERE scope = ? AND target = ?
            """,
            (scope.value, target),
        ).fetchone()
        if row is None:
            return None
        return WorkspaceLock(
            lock_id=str(row[0]),
            scope=LockScope(str(row[1])),
            target=str(row[2]),
            owner=str(row[3]),
            token=str(row[4]),
            expires_at=datetime.fromisoformat(str(row[5])),
        )

    @staticmethod
    def _to_row(lock: WorkspaceLock) -> tuple[str, str, str, str, str, str]:
        return (
            lock.scope.value,
            lock.target,
            lock.lock_id,
            lock.owner,
            lock.token,
            lock.expires_at.isoformat(),
        )

    @staticmethod
    def _validate_inputs(*, target: str, owner: str, ttl_seconds: int) -> None:
        if not target.strip():
            raise WorkspaceLockError("INVALID_TARGET", "lock target must be non-empty")
        if not owner.strip():
            raise WorkspaceLockError("INVALID_OWNER", "lock owner must be non-empty")
        if ttl_seconds <= 0:
            raise WorkspaceLockError("INVALID_TTL", "lock ttl_seconds must be greater than zero")


def _normalize_now(now: datetime | None) -> datetime:
    checked = datetime.now(UTC) if now is None else now
    if checked.tzinfo is None:
        return checked.replace(tzinfo=UTC)
    return checked.astimezone(UTC)
