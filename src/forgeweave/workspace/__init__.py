"""Workspace and Git worktree lifecycle primitives."""

from forgeweave.workspace.lifecycle import WorkspaceLifecycle, WorkspaceLifecycleError
from forgeweave.workspace.leases import LeaseFenceResult, assert_active_lease, require_active_lease
from forgeweave.workspace.locks import LockScope, WorkspaceLock, WorkspaceLockError, WorkspaceLockStore
from forgeweave.workspace.manager import WorktreeRecord, WorkspaceManager, WorkspacePolicyError, sanitize_branch_component
from forgeweave.workspace.store import WorkspaceStore

__all__ = [
    "LeaseFenceResult",
    "LockScope",
    "WorkspaceLifecycle",
    "WorkspaceLifecycleError",
    "WorkspaceLock",
    "WorkspaceLockError",
    "WorkspaceLockStore",
    "WorkspaceStore",
    "WorktreeRecord",
    "WorkspaceManager",
    "WorkspacePolicyError",
    "assert_active_lease",
    "require_active_lease",
    "sanitize_branch_component",
]
