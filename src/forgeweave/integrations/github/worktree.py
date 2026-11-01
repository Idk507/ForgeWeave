"""Apply GitHub checkout plans through a guarded workspace boundary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess

from forgeweave.workspace.manager import sanitize_branch_component

from .checkout import GitHubCheckoutPlan
from .gh import GitHubCliError


@dataclass(frozen=True)
class GitCommandResult:
    """Evidence for one Git command executed by the checkout applier."""

    command: tuple[str, ...]
    cwd: Path
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class GitHubWorktreeCheckout:
    """Result of applying a commit-pinned checkout plan."""

    plan: GitHubCheckoutPlan
    repository_root: Path
    worktree_path: Path
    commands: tuple[GitCommandResult, ...]


GitRunner = Callable[[Sequence[str], Path, int], GitCommandResult]


class GitHubCheckoutApplier:
    """Apply a GitHub checkout plan with explicit path and command guards."""

    def __init__(self, *, repository_root: Path, worktree_root: Path, runner: GitRunner | None = None) -> None:
        self.repository_root = repository_root.resolve()
        self.worktree_root = worktree_root.resolve()
        self._runner = runner or _subprocess_runner
        if not (self.repository_root / ".git").exists():
            raise GitHubCliError("INVALID_REPOSITORY_ROOT", "repository root must contain .git")

    def dry_run(self, plan: GitHubCheckoutPlan) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return the planned fetch and worktree commands without executing them."""

        worktree_path = self._worktree_path(plan)
        return (plan.git_fetch_argv, _worktree_argv(plan, worktree_path))

    def apply(self, plan: GitHubCheckoutPlan, *, timeout_seconds: int = 60) -> GitHubWorktreeCheckout:
        """Fetch the PR head ref and create a detached worktree pinned to the plan SHA."""

        if timeout_seconds < 1:
            raise GitHubCliError("INVALID_TIMEOUT", "Git checkout timeout must be >= 1")
        worktree_path = self._worktree_path(plan)
        if worktree_path.exists():
            raise GitHubCliError("WORKTREE_PATH_EXISTS", f"GitHub PR worktree path already exists: {worktree_path}")
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        commands = (
            self._run(plan.git_fetch_argv, timeout_seconds=timeout_seconds),
            self._run(_worktree_argv(plan, worktree_path), timeout_seconds=timeout_seconds),
        )
        return GitHubWorktreeCheckout(plan=plan, repository_root=self.repository_root, worktree_path=worktree_path, commands=commands)

    def _worktree_path(self, plan: GitHubCheckoutPlan) -> Path:
        slug = sanitize_branch_component(f"pr-{plan.pull_number}-{plan.head_sha[:12]}")
        path = (self.worktree_root / slug).resolve()
        try:
            path.relative_to(self.worktree_root)
        except ValueError as exc:
            raise GitHubCliError("WORKTREE_ESCAPE", "GitHub PR worktree path escaped the configured root") from exc
        return path

    def _run(self, argv: tuple[str, ...], *, timeout_seconds: int) -> GitCommandResult:
        result = self._runner(argv, self.repository_root, timeout_seconds)
        if tuple(result.command) != argv:
            raise GitHubCliError("COMMAND_MISMATCH", "Git runner returned evidence for a different command")
        if result.cwd.resolve() != self.repository_root:
            raise GitHubCliError("CWD_MISMATCH", "Git runner returned evidence for a different repository root")
        if result.returncode != 0:
            raise GitHubCliError("GIT_FAILED", result.stderr.strip() or "git command failed")
        return result


def _worktree_argv(plan: GitHubCheckoutPlan, worktree_path: Path) -> tuple[str, ...]:
    return ("git", "worktree", "add", "--detach", str(worktree_path), plan.head_sha)


def _subprocess_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> GitCommandResult:
    completed = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    return GitCommandResult(command=tuple(argv), cwd=cwd, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
