"""Git worktree creation with explicit repository-root safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
import subprocess

from forgeweave.workspace.locks import LockScope, WorkspaceLock, WorkspaceLockError, WorkspaceLockStore


class WorkspacePolicyError(ValueError):
    """Raised when a workspace operation is unsafe or unsupported."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WorktreeRecord:
    """Created worktree metadata for later persistence slices."""

    task_id: str
    repository_path: Path
    worktree_path: Path
    base_commit: str
    branch: str
    worktree_lock: WorkspaceLock | None = None


class WorkspaceManager:
    """Create task-owned Git worktrees from an explicit repository root."""

    def __init__(
        self,
        *,
        repository_root: Path,
        worktree_root: Path,
        lock_store: WorkspaceLockStore | None = None,
        lock_ttl_seconds: int = 300,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.worktree_root = worktree_root.resolve()
        self.lock_store = lock_store
        self.lock_ttl_seconds = lock_ttl_seconds
        if not (self.repository_root / ".git").exists():
            raise WorkspacePolicyError("INVALID_REPOSITORY_ROOT", "repository root must contain its own .git directory")
        actual = self._git("rev-parse", "--show-toplevel").stdout.strip()
        if Path(actual).resolve() != self.repository_root:
            raise WorkspacePolicyError("INVALID_REPOSITORY_ROOT", "git toplevel does not match repository_root")

    def create_worktree(self, *, task_id: str, slug: str) -> WorktreeRecord:
        """Create a linked worktree on a sanitized `fw/<task-id>-<slug>` branch."""

        safe_task = sanitize_branch_component(task_id)
        safe_slug = sanitize_branch_component(slug)
        branch = f"fw/{safe_task}-{safe_slug}"
        worktree_path = self.worktree_root / f"{safe_task}-{safe_slug}"
        repo_lock = self._acquire_lock(scope=LockScope.REPOSITORY, target=str(self.repository_root), owner=task_id)
        worktree_lock: WorkspaceLock | None = None
        try:
            self._ensure_clean_source()
            self._ensure_branch_absent(branch)
            if worktree_path.exists():
                raise WorkspacePolicyError("WORKTREE_PATH_EXISTS", f"worktree path already exists: {worktree_path}")

            resolved_worktree_path = worktree_path.resolve()
            worktree_lock = self._acquire_lock(
                scope=LockScope.WORKTREE,
                target=str(resolved_worktree_path),
                owner=task_id,
            )
            base_commit = self._git("rev-parse", "HEAD").stdout.strip()
            self.worktree_root.mkdir(parents=True, exist_ok=True)
            self._git("worktree", "add", "-b", branch, str(worktree_path), base_commit, timeout_seconds=60)
            return WorktreeRecord(
                task_id=task_id,
                repository_path=self.repository_root,
                worktree_path=resolved_worktree_path,
                base_commit=base_commit,
                branch=branch,
                worktree_lock=worktree_lock,
            )
        except Exception:
            if worktree_lock is not None:
                self._release_lock_quietly(worktree_lock)
            raise
        finally:
            if repo_lock is not None:
                self._release_lock_quietly(repo_lock)


    def _acquire_lock(self, *, scope: LockScope, target: str, owner: str) -> WorkspaceLock | None:
        if self.lock_store is None:
            return None
        try:
            return self.lock_store.acquire(
                scope=scope,
                target=target,
                owner=owner,
                ttl_seconds=self.lock_ttl_seconds,
                now=datetime.now(UTC),
            )
        except WorkspaceLockError as exc:
            code = "REPOSITORY_LOCK_HELD" if scope is LockScope.REPOSITORY else "WORKTREE_LOCK_HELD"
            if exc.code != "LOCK_HELD":
                code = "WORKSPACE_LOCK_FAILED"
            raise WorkspacePolicyError(code, exc.message) from exc

    def _release_lock_quietly(self, lock: WorkspaceLock) -> None:
        if self.lock_store is None:
            return
        try:
            self.lock_store.release(lock)
        except WorkspaceLockError:
            pass

    def _ensure_clean_source(self) -> None:
        porcelain = self._git("status", "--porcelain=v1").stdout.strip()
        if porcelain:
            raise WorkspacePolicyError("DIRTY_SOURCE_CHECKOUT", "source checkout has uncommitted changes")

    def _ensure_branch_absent(self, branch: str) -> None:
        completed = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            raise WorkspacePolicyError("BRANCH_ALREADY_EXISTS", f"branch already exists: {branch}")
        if completed.returncode not in {0, 1}:
            raise WorkspacePolicyError("GIT_FAILED", completed.stderr.strip() or "git show-ref failed")

    def _git(self, *args: str, timeout_seconds: int = 15) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise WorkspacePolicyError("GIT_FAILED", completed.stderr.strip() or f"git command failed: {' '.join(args)}")
        return completed


def sanitize_branch_component(value: str) -> str:
    """Return a conservative branch/path component."""

    lowered = value.strip().lower()
    replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
    collapsed = re.sub(r"-+", "-", replaced).strip("-")
    if not collapsed:
        return "task"
    return collapsed[:64].strip("-") or "task"
