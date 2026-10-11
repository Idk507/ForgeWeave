from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from forgeweave.contracts import WorktreeState
from forgeweave.workspace import WorkspaceLifecycle, WorkspaceLifecycleError, WorkspaceManager, WorkspaceStore


class WorkspaceLifecycleTests(unittest.TestCase):
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
        self.store = WorkspaceStore.open(self.root / "workspace.db")
        self.addCleanup(self.store.close)
        manager = WorkspaceManager(repository_root=self.repo, worktree_root=self.worktrees)
        self.record = manager.create_worktree(task_id="task-1", slug="cleanup")
        self.worktree = self.store.record_worktree(
            worktree_id="wt-1",
            task_id="task-1",
            repository_path=str(self.record.repository_path),
            worktree_path=str(self.record.worktree_path),
            base_commit=self.record.base_commit,
            branch=self.record.branch,
            state=WorktreeState.ACTIVE,
        )
        self.lifecycle = WorkspaceLifecycle(store=self.store)

    def test_cleanup_clean_worktree_uses_git_remove_and_marks_cleaned(self) -> None:
        cleaned = self.lifecycle.cleanup(self.worktree)

        self.assertEqual(cleaned.state, WorktreeState.CLEANED)
        self.assertFalse(cleaned.dirty)
        self.assertFalse(Path(cleaned.worktree_path).exists())
        self.assertEqual(self.store.get_worktree("wt-1").state, WorktreeState.CLEANED)

    def test_cleanup_dirty_worktree_is_rejected_and_preserved(self) -> None:
        (Path(self.worktree.worktree_path) / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        with self.assertRaises(WorkspaceLifecycleError) as raised:
            self.lifecycle.cleanup(self.worktree)

        self.assertEqual(raised.exception.code, "DIRTY_WORKTREE")
        stored = self.store.get_worktree("wt-1")
        self.assertEqual(stored.state, WorktreeState.PRESERVED)
        self.assertTrue(stored.dirty)
        self.assertTrue(Path(stored.worktree_path).exists())

    def test_preserve_marks_record_without_deleting_files(self) -> None:
        preserved = self.lifecycle.preserve(self.worktree, dirty=True)

        self.assertEqual(preserved.state, WorktreeState.PRESERVED)
        self.assertTrue(preserved.dirty)
        self.assertTrue(Path(preserved.worktree_path).exists())

    def _git(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
