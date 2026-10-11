"""Safe preservation and cleanup lifecycle for task-owned Git worktrees."""

from __future__ import annotations

from pathlib import Path
import subprocess

from forgeweave.contracts import Worktree, WorktreeState
from forgeweave.workspace.store import WorkspaceStore


class WorkspaceLifecycleError(ValueError):
    """Raised when preserving or cleaning a task worktree is unsafe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkspaceLifecycle:
    """Preserve and clean task-owned worktrees through explicit lifecycle states."""

    def __init__(self, *, store: WorkspaceStore) -> None:
        self.store = store

    def preserve(self, worktree: Worktree, *, dirty: bool | None = None) -> Worktree:
        """Mark a worktree as preserved without deleting files."""

        actual_dirty = self.is_dirty(worktree) if dirty is None and Path(worktree.worktree_path).exists() else bool(dirty)
        return self.store.update_state(worktree.worktree_id, state=WorktreeState.PRESERVED, dirty=actual_dirty)

    def cleanup(self, worktree: Worktree) -> Worktree:
        """Remove a clean worktree using `git worktree remove` and mark it cleaned.

        Dirty worktrees are preserved instead of deleted so interrupted or failed
        work remains inspectable and recoverable.
        """

        path = Path(worktree.worktree_path)
        if not path.exists():
            return self.store.update_state(worktree.worktree_id, state=WorktreeState.CLEANED, dirty=False)
        if self.is_dirty(worktree):
            self.store.update_state(worktree.worktree_id, state=WorktreeState.PRESERVED, dirty=True)
            raise WorkspaceLifecycleError("DIRTY_WORKTREE", f"worktree has uncommitted changes: {path}")

        self._git(worktree, "worktree", "remove", str(path), timeout_seconds=60)
        self._git(worktree, "worktree", "prune", timeout_seconds=30)
        return self.store.update_state(worktree.worktree_id, state=WorktreeState.CLEANED, dirty=False)

    def is_dirty(self, worktree: Worktree) -> bool:
        """Return whether a worktree has uncommitted changes."""

        path = Path(worktree.worktree_path)
        if not path.exists():
            return False
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if completed.returncode != 0:
            raise WorkspaceLifecycleError("GIT_FAILED", completed.stderr.strip() or "git status failed")
        return bool(completed.stdout.strip())

    def _git(self, worktree: Worktree, *args: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=Path(worktree.repository_path),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise WorkspaceLifecycleError("GIT_FAILED", completed.stderr.strip() or f"git command failed: {' '.join(args)}")
        return completed
