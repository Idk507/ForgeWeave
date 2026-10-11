"""Git status, diff and guarded commit tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
from typing import Iterable

from forgeweave.contracts import EffectSet, ToolSpec

from .registry import ToolRegistry


class GitPolicyError(ValueError):
    """Raised when a Git request is unsafe or outside the explicit repository."""


@dataclass(frozen=True)
class GitStatus:
    """Parsed `git status --porcelain` projection."""

    branch: str
    dirty: bool
    changed_paths: tuple[str, ...]
    porcelain: tuple[str, ...]


@dataclass(frozen=True)
class GitDiff:
    """Bounded Git diff output."""

    patch: str
    truncated: bool


@dataclass(frozen=True)
class GitCommit:
    """Result from a guarded local commit."""

    commit_hash: str
    message: str
    paths: tuple[str, ...]


class GitTools:
    """Git operations scoped to one explicit repository root."""

    def __init__(self, repository_root: Path) -> None:
        self.root = repository_root.resolve()
        if not (self.root / ".git").exists():
            raise GitPolicyError("repository root must contain its own .git directory")
        actual = self._git("rev-parse", "--show-toplevel").stdout.strip()
        if Path(actual).resolve() != self.root:
            raise GitPolicyError("git toplevel does not match the explicit repository root")

    def status(self) -> GitStatus:
        """Return branch and porcelain status without mutating the repository."""

        branch = self._git("branch", "--show-current").stdout.strip() or "HEAD"
        porcelain_lines = tuple(line for line in self._git("status", "--porcelain=v1").stdout.splitlines() if line)
        changed_paths = tuple(_porcelain_path(line) for line in porcelain_lines)
        return GitStatus(branch=branch, dirty=bool(porcelain_lines), changed_paths=changed_paths, porcelain=porcelain_lines)

    def diff(self, *, max_bytes: int = 200_000) -> GitDiff:
        """Return a bounded patch for unstaged workspace changes."""

        if max_bytes < 1:
            raise GitPolicyError("max_bytes must be >= 1")
        patch = self._git("diff", "--no-ext-diff", "--", timeout_seconds=30).stdout
        encoded = patch.encode("utf-8")
        if len(encoded) <= max_bytes:
            return GitDiff(patch=patch, truncated=False)
        return GitDiff(patch=encoded[:max_bytes].decode("utf-8", errors="ignore"), truncated=True)

    def commit(self, *, message: str, paths: Iterable[str], allow_mutation: bool = False) -> GitCommit:
        """Create a local commit only when explicit mutation is allowed."""

        if not allow_mutation:
            raise GitPolicyError("git commit requires allow_mutation=True")
        cleaned_message = message.strip()
        if not cleaned_message:
            raise GitPolicyError("commit message must not be blank")
        selected_paths = tuple(paths)
        if not selected_paths:
            raise GitPolicyError("commit paths must not be empty")
        for path in selected_paths:
            _validate_relative_path(path)

        self._git("add", "--", *selected_paths)
        self._git("commit", "-m", cleaned_message)
        commit_hash = self._git("rev-parse", "HEAD").stdout.strip()
        return GitCommit(commit_hash=commit_hash, message=cleaned_message, paths=selected_paths)

    def _git(self, *args: str, timeout_seconds: int = 15) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise GitPolicyError(completed.stderr.strip() or f"git command failed: {' '.join(args)}")
        return completed


def register_git_tools(repository_root: Path, *, catalog_version: str) -> ToolRegistry:
    """Return a registry populated with Git status/diff/commit tools."""

    git = GitTools(repository_root)
    registry = ToolRegistry(catalog_version=catalog_version)
    registry.register(
        ToolSpec(
            name="git_status",
            description="Read Git branch and porcelain status for the task repository.",
            input_schema={"type": "object", "required": [], "properties": {}},
            effects=EffectSet(reads=frozenset({"git"})),
            schema_version="git-status.v1",
        ),
        lambda arguments: asdict(git.status()),
    )
    registry.register(
        ToolSpec(
            name="git_diff",
            description="Read a bounded unstaged Git diff.",
            input_schema={
                "type": "object",
                "required": [],
                "properties": {"max_bytes": {"type": "integer"}},
            },
            effects=EffectSet(reads=frozenset({"git"})),
            schema_version="git-diff.v1",
        ),
        lambda arguments: asdict(git.diff(max_bytes=arguments.get("max_bytes", 200_000))),
    )
    registry.register(
        ToolSpec(
            name="git_commit",
            description="Create a local Git commit from explicit paths when mutation is allowed.",
            input_schema={
                "type": "object",
                "required": ["message", "paths", "allow_mutation"],
                "properties": {
                    "message": {"type": "string"},
                    "paths": {"type": "array"},
                    "allow_mutation": {"type": "boolean"},
                },
            },
            effects=EffectSet(writes=frozenset({"git"}), process=frozenset({"git"})),
            schema_version="git-commit.v1",
        ),
        lambda arguments: asdict(
            git.commit(message=arguments["message"], paths=arguments["paths"], allow_mutation=arguments["allow_mutation"])
        ),
    )
    return registry


def _porcelain_path(line: str) -> str:
    value = line[3:] if len(line) > 3 else line
    if " -> " in value:
        value = value.split(" -> ", 1)[1]
    return value.strip()


def _validate_relative_path(path: str) -> None:
    if not path.strip() or Path(path).is_absolute():
        raise GitPolicyError("commit paths must be relative")
    if any(part in {"", ".", ".."} or ":" in part for part in Path(path).parts):
        raise GitPolicyError("commit path contains a forbidden component")
