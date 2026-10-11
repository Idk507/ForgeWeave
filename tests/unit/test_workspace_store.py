from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.contracts import WorktreeState
from forgeweave.workspace import WorkspaceStore


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_record_and_get_worktree(self) -> None:
        store = WorkspaceStore.open(self.root / "workspace.db")

        record = store.record_worktree(
            worktree_id="wt-1",
            task_id="task-1",
            repository_path="C:/repo",
            worktree_path="C:/repo-wt",
            base_commit="abc123",
            branch="fw/task-1-fix",
            state=WorktreeState.ACTIVE,
            dirty=False,
        )
        loaded = store.get_worktree("wt-1")

        self.assertEqual(loaded, record)
        self.assertEqual(loaded.state, WorktreeState.ACTIVE)
        store.close()

    def test_list_worktrees_by_task(self) -> None:
        store = WorkspaceStore.open(self.root / "workspace.db")
        store.record_worktree(
            worktree_id="wt-1",
            task_id="task-1",
            repository_path="C:/repo",
            worktree_path="C:/repo-wt-1",
            base_commit="abc123",
            branch="fw/task-1-one",
            state=WorktreeState.ACTIVE,
        )
        store.record_worktree(
            worktree_id="wt-2",
            task_id="task-2",
            repository_path="C:/repo",
            worktree_path="C:/repo-wt-2",
            base_commit="abc123",
            branch="fw/task-2-two",
            state=WorktreeState.PRESERVED,
        )

        self.assertEqual([item.worktree_id for item in store.list_worktrees(task_id="task-1")], ["wt-1"])
        self.assertEqual([item.worktree_id for item in store.list_worktrees()], ["wt-1", "wt-2"])
        store.close()

    def test_update_state_preserves_identity_fields(self) -> None:
        store = WorkspaceStore.open(self.root / "workspace.db")
        store.record_worktree(
            worktree_id="wt-1",
            task_id="task-1",
            repository_path="C:/repo",
            worktree_path="C:/repo-wt",
            base_commit="abc123",
            branch="fw/task-1-fix",
            state=WorktreeState.ACTIVE,
        )

        updated = store.update_state("wt-1", state=WorktreeState.LOCKED, dirty=True)

        self.assertEqual(updated.state, WorktreeState.LOCKED)
        self.assertTrue(updated.dirty)
        self.assertEqual(updated.branch, "fw/task-1-fix")
        store.close()

    def test_rejects_duplicate_with_different_identity(self) -> None:
        store = WorkspaceStore.open(self.root / "workspace.db")
        store.record_worktree(
            worktree_id="wt-1",
            task_id="task-1",
            repository_path="C:/repo",
            worktree_path="C:/repo-wt",
            base_commit="abc123",
            branch="fw/task-1-fix",
            state=WorktreeState.ACTIVE,
        )

        with self.assertRaises(ValueError):
            store.record_worktree(
                worktree_id="wt-1",
                task_id="task-1",
                repository_path="C:/repo",
                worktree_path="C:/different",
                base_commit="abc123",
                branch="fw/task-1-fix",
                state=WorktreeState.ACTIVE,
            )
        store.close()


if __name__ == "__main__":
    unittest.main()
