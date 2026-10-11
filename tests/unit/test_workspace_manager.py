from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from forgeweave.workspace import LockScope, WorkspaceLockStore, WorkspaceManager, WorkspacePolicyError, sanitize_branch_component


class WorkspaceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.worktrees = self.root / "worktrees"
        self.addCleanup(self._tmp.cleanup)
        self._git("init", cwd=self.repo)
        self._git("config", "user.email", "forgeweave@example.test", cwd=self.repo)
        self._git("config", "user.name", "ForgeWeave Test", cwd=self.repo)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        self._git("add", "README.md", cwd=self.repo)
        self._git("commit", "-m", "initial", cwd=self.repo)

    def test_sanitize_branch_component(self) -> None:
        self.assertEqual(sanitize_branch_component("Fix Bug!!"), "fix-bug")
        self.assertEqual(sanitize_branch_component("..."), "task")

    def test_create_worktree_uses_sanitized_fw_branch_and_path(self) -> None:
        manager = WorkspaceManager(repository_root=self.repo, worktree_root=self.worktrees)

        record = manager.create_worktree(task_id="task-123", slug="Fix Seeded Bug")

        self.assertEqual(record.branch, "fw/task-123-fix-seeded-bug")
        self.assertTrue(record.worktree_path.exists())
        self.assertTrue((record.worktree_path / "README.md").exists())
        self.assertEqual(record.base_commit, self._git("rev-parse", "HEAD", cwd=self.repo).stdout.strip())
        branch = self._git("branch", "--show-current", cwd=record.worktree_path).stdout.strip()
        self.assertEqual(branch, record.branch)


    def test_create_worktree_uses_repo_lock_and_keeps_worktree_lock(self) -> None:
        lock_store = WorkspaceLockStore.open(self.root / "locks.db")
        self.addCleanup(lock_store.close)
        manager = WorkspaceManager(repository_root=self.repo, worktree_root=self.worktrees, lock_store=lock_store)

        record = manager.create_worktree(task_id="task-123", slug="locked")

        self.assertIsNotNone(record.worktree_lock)
        self.assertIsNone(lock_store.current(scope=LockScope.REPOSITORY, target=str(self.repo.resolve())))
        active = lock_store.current(scope=LockScope.WORKTREE, target=str(record.worktree_path))
        self.assertIsNotNone(active)
        self.assertEqual(active.owner, "task-123")
    def test_create_worktree_fails_when_repo_lock_is_held(self) -> None:
        lock_store = WorkspaceLockStore.open(self.root / "locks.db")
        self.addCleanup(lock_store.close)
        held = lock_store.acquire(
            scope=LockScope.REPOSITORY,
            target=str(self.repo.resolve()),
            owner="other-task",
            ttl_seconds=60,
        )
        manager = WorkspaceManager(repository_root=self.repo, worktree_root=self.worktrees, lock_store=lock_store)

        with self.assertRaises(WorkspacePolicyError) as raised:
            manager.create_worktree(task_id="task-123", slug="blocked")

        self.assertEqual(raised.exception.code, "REPOSITORY_LOCK_HELD")
        lock_store.release(held)

    def test_rejects_dirty_source_checkout(self) -> None:
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        manager = WorkspaceManager(repository_root=self.repo, worktree_root=self.worktrees)

        with self.assertRaises(WorkspacePolicyError) as raised:
            manager.create_worktree(task_id="task-1", slug="dirty")

        self.assertEqual(raised.exception.code, "DIRTY_SOURCE_CHECKOUT")

    def test_rejects_repository_without_own_git_directory(self) -> None:
        nested = self.repo / "nested"
        nested.mkdir()

        with self.assertRaises(WorkspacePolicyError) as raised:
            WorkspaceManager(repository_root=nested, worktree_root=self.worktrees)

        self.assertEqual(raised.exception.code, "INVALID_REPOSITORY_ROOT")

    def test_rejects_existing_branch(self) -> None:
        manager = WorkspaceManager(repository_root=self.repo, worktree_root=self.worktrees)
        manager.create_worktree(task_id="task-1", slug="same")

        with self.assertRaises(WorkspacePolicyError) as raised:
            manager.create_worktree(task_id="task-1", slug="same")

        self.assertEqual(raised.exception.code, "BRANCH_ALREADY_EXISTS")

    def _git(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
