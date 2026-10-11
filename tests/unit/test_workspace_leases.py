from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from forgeweave.workspace import LockScope, WorkspaceLockError, WorkspaceLockStore, assert_active_lease, require_active_lease


class WorkspaceLeaseFenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.store = WorkspaceLockStore.open(self.root / "locks.db")
        self.addCleanup(self.store.close)

    def test_allows_current_owner_and_token(self) -> None:
        lock = self.store.acquire(scope=LockScope.WORKTREE, target="C:/repo-wt", owner="task-1", ttl_seconds=60, now=self.now)

        result = require_active_lease(self.store, lock, now=self.now + timedelta(seconds=1))

        self.assertTrue(result.allowed)
        self.assertEqual(result.code, "LEASE_ACTIVE")
        self.assertEqual(result.lock_id, lock.lock_id)

    def test_denies_expired_lease(self) -> None:
        lock = self.store.acquire(scope=LockScope.WORKTREE, target="C:/repo-wt", owner="task-1", ttl_seconds=10, now=self.now)

        result = require_active_lease(self.store, lock, now=self.now + timedelta(seconds=11))

        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "LOCK_NOT_ACTIVE")

    def test_denies_replaced_stale_token(self) -> None:
        first = self.store.acquire(scope=LockScope.WORKTREE, target="C:/repo-wt", owner="task-1", ttl_seconds=10, now=self.now)
        self.store.acquire(scope=LockScope.WORKTREE, target="C:/repo-wt", owner="task-2", ttl_seconds=60, now=self.now + timedelta(seconds=11))

        result = require_active_lease(self.store, first, now=self.now + timedelta(seconds=12))

        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "LOCK_TOKEN_MISMATCH")
        self.assertEqual(result.owner, "task-1")

    def test_assert_active_lease_raises_structured_error(self) -> None:
        lock = self.store.acquire(scope=LockScope.REPOSITORY, target="C:/repo", owner="task-1", ttl_seconds=10, now=self.now)

        with self.assertRaises(WorkspaceLockError) as raised:
            assert_active_lease(self.store, lock.model_copy(update={"token": "stale"}), now=self.now)

        self.assertEqual(raised.exception.code, "LOCK_TOKEN_MISMATCH")


if __name__ == "__main__":
    unittest.main()
