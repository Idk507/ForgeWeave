from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from forgeweave.workspace import LockScope, WorkspaceLockError, WorkspaceLockStore


class WorkspaceLockStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def test_repo_lock_blocks_second_owner_until_expiry(self) -> None:
        store = WorkspaceLockStore.open(self.root / "locks.db")
        first = store.acquire(
            scope=LockScope.REPOSITORY,
            target="C:/repo",
            owner="task-1",
            ttl_seconds=60,
            now=self.now,
        )

        with self.assertRaises(WorkspaceLockError) as raised:
            store.acquire(
                scope=LockScope.REPOSITORY,
                target="C:/repo",
                owner="task-2",
                ttl_seconds=60,
                now=self.now + timedelta(seconds=10),
            )

        self.assertEqual(raised.exception.code, "LOCK_HELD")
        replacement = store.acquire(
            scope=LockScope.REPOSITORY,
            target="C:/repo",
            owner="task-2",
            ttl_seconds=60,
            now=self.now + timedelta(seconds=61),
        )
        self.assertNotEqual(replacement.token, first.token)
        self.assertEqual(replacement.owner, "task-2")
        store.close()

    def test_release_requires_matching_owner_and_token(self) -> None:
        store = WorkspaceLockStore.open(self.root / "locks.db")
        lock = store.acquire(
            scope=LockScope.WORKTREE,
            target="C:/repo-wt",
            owner="task-1",
            ttl_seconds=60,
            now=self.now,
        )

        with self.assertRaises(WorkspaceLockError) as raised:
            store.release(lock.model_copy(update={"token": "wrong-token"}))

        self.assertEqual(raised.exception.code, "LOCK_TOKEN_MISMATCH")
        store.release(lock)
        self.assertIsNone(store.current(scope=LockScope.WORKTREE, target="C:/repo-wt", now=self.now))
        store.close()

    def test_repo_and_worktree_scopes_do_not_conflict(self) -> None:
        store = WorkspaceLockStore.open(self.root / "locks.db")
        repo_lock = store.acquire(
            scope=LockScope.REPOSITORY,
            target="C:/same",
            owner="task-1",
            ttl_seconds=60,
            now=self.now,
        )
        worktree_lock = store.acquire(
            scope=LockScope.WORKTREE,
            target="C:/same",
            owner="task-2",
            ttl_seconds=60,
            now=self.now,
        )

        self.assertEqual(repo_lock.scope, LockScope.REPOSITORY)
        self.assertEqual(worktree_lock.scope, LockScope.WORKTREE)
        store.close()

    def test_refresh_extends_active_lock(self) -> None:
        store = WorkspaceLockStore.open(self.root / "locks.db")
        lock = store.acquire(
            scope=LockScope.WORKTREE,
            target="C:/repo-wt",
            owner="task-1",
            ttl_seconds=60,
            now=self.now,
        )

        refreshed = store.refresh(lock, ttl_seconds=120, now=self.now + timedelta(seconds=30))

        self.assertEqual(refreshed.token, lock.token)
        self.assertEqual(refreshed.expires_at, self.now + timedelta(seconds=150))
        store.close()

    def test_validation_rejects_bad_lock_inputs(self) -> None:
        store = WorkspaceLockStore.open(self.root / "locks.db")

        with self.assertRaises(WorkspaceLockError) as raised:
            store.acquire(scope=LockScope.REPOSITORY, target=" ", owner="task-1", ttl_seconds=60, now=self.now)

        self.assertEqual(raised.exception.code, "INVALID_TARGET")
        with self.assertRaises(WorkspaceLockError) as ttl_raised:
            store.acquire(scope=LockScope.REPOSITORY, target="C:/repo", owner="task-1", ttl_seconds=0, now=self.now)

        self.assertEqual(ttl_raised.exception.code, "INVALID_TTL")
        store.close()


if __name__ == "__main__":
    unittest.main()
