"""Guarded GitHub CLI command boundary.

The wrapper intentionally starts with read-only polling operations. Publication
operations such as PR creation, branch pushes and comments need a separate
approval-aware policy path before they are exposed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
import json
import re
import subprocess
from typing import Any


class GitHubCliError(ValueError):
    """Raised when a GitHub CLI request is unsafe or malformed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class GitHubCliCommand(str, Enum):
    """Read-only GitHub operations supported by the initial wrapper."""

    ISSUE_VIEW = "issue_view"
    PR_VIEW = "pr_view"
    PR_CHECKS = "pr_checks"
    PR_COMMENTS = "pr_comments"
    RUN_VIEW = "run_view"


@dataclass(frozen=True)
class GitHubReference:
    """Normalized GitHub issue or pull request reference."""

    owner: str
    repo: str
    number: int

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class GitHubCliResult:
    """Completed GitHub CLI invocation evidence."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> dict[str, Any]:
        """Parse stdout as a JSON object."""

        value = json.loads(self.stdout or "{}")
        if not isinstance(value, dict):
            raise GitHubCliError("UNEXPECTED_JSON", "GitHub CLI output must be a JSON object")
        return value


CommandRunner = Callable[[Sequence[str], int], GitHubCliResult]


class GitHubCliRunner:
    """Small injectable runner for read-only `gh` commands."""

    def __init__(self, *, executable: str = "gh", timeout_seconds: int = 30, runner: CommandRunner | None = None) -> None:
        if not executable.strip():
            raise GitHubCliError("INVALID_EXECUTABLE", "GitHub CLI executable must not be blank")
        if timeout_seconds < 1:
            raise GitHubCliError("INVALID_TIMEOUT", "GitHub CLI timeout must be >= 1")
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._runner = runner or _subprocess_runner

    def issue_view(self, reference: GitHubReference) -> GitHubCliResult:
        return self._run(build_gh_command(GitHubCliCommand.ISSUE_VIEW, reference, executable=self._executable))

    def pr_view(self, reference: GitHubReference) -> GitHubCliResult:
        return self._run(build_gh_command(GitHubCliCommand.PR_VIEW, reference, executable=self._executable))

    def pr_checks(self, reference: GitHubReference) -> GitHubCliResult:
        return self._run(build_gh_command(GitHubCliCommand.PR_CHECKS, reference, executable=self._executable))

    def pr_comments(self, reference: GitHubReference) -> GitHubCliResult:
        return self._run(build_gh_command(GitHubCliCommand.PR_COMMENTS, reference, executable=self._executable))

    def run_view(self, *, owner: str, repo: str, run_id: int) -> GitHubCliResult:
        reference = GitHubReference(owner=owner, repo=repo, number=run_id)
        return self._run(build_gh_command(GitHubCliCommand.RUN_VIEW, reference, executable=self._executable))

    def _run(self, argv: tuple[str, ...]) -> GitHubCliResult:
        result = self._runner(argv, self._timeout_seconds)
        if tuple(result.command) != argv:
            raise GitHubCliError("COMMAND_MISMATCH", "GitHub CLI runner returned evidence for a different command")
        return result


def parse_github_reference(value: str) -> GitHubReference:
    """Parse `owner/repo#123` or GitHub issue/PR URLs into a normalized reference."""

    text = value.strip()
    if not text:
        raise GitHubCliError("EMPTY_REFERENCE", "GitHub reference must not be blank")
    shorthand = re.fullmatch(r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<number>[1-9][0-9]*)", text)
    if shorthand:
        return _reference_from_match(shorthand)
    url = re.fullmatch(
        r"https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/(?:issues|pull)/(?P<number>[1-9][0-9]*)(?:[/?#].*)?",
        text,
    )
    if url:
        return _reference_from_match(url)
    raise GitHubCliError("INVALID_REFERENCE", "expected owner/repo#number or a github.com issue/pull URL")


def build_gh_command(command: GitHubCliCommand, reference: GitHubReference, *, executable: str = "gh") -> tuple[str, ...]:
    """Build a read-only `gh` argv tuple for an admitted GitHub reference."""

    _validate_reference(reference)
    if command is GitHubCliCommand.ISSUE_VIEW:
        return (
            executable,
            "issue",
            "view",
            str(reference.number),
            "--repo",
            reference.repository,
            "--json",
            "number,title,state,author,body,url,labels,assignees,updatedAt",
        )
    if command is GitHubCliCommand.PR_VIEW:
        return (
            executable,
            "pr",
            "view",
            str(reference.number),
            "--repo",
            reference.repository,
            "--json",
            "number,title,state,author,body,url,headRefName,baseRefName,headRepository,commits,files,reviewDecision,mergeStateStatus,updatedAt",
        )
    if command is GitHubCliCommand.PR_CHECKS:
        return (executable, "pr", "checks", str(reference.number), "--repo", reference.repository, "--json", "bucket,completedAt,conclusion,name,startedAt,state,workflow")
    if command is GitHubCliCommand.PR_COMMENTS:
        return (executable, "api", f"repos/{reference.repository}/pulls/{reference.number}/comments", "--paginate")
    if command is GitHubCliCommand.RUN_VIEW:
        return (executable, "run", "view", str(reference.number), "--repo", reference.repository, "--json", "databaseId,displayTitle,event,status,conclusion,createdAt,updatedAt,url")
    raise GitHubCliError("UNSUPPORTED_COMMAND", f"unsupported GitHub CLI command: {command}")


def _reference_from_match(match: re.Match[str]) -> GitHubReference:
    return GitHubReference(owner=match.group("owner"), repo=match.group("repo"), number=int(match.group("number")))


def _validate_reference(reference: GitHubReference) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", reference.owner):
        raise GitHubCliError("INVALID_OWNER", "GitHub owner contains unsupported characters")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", reference.repo):
        raise GitHubCliError("INVALID_REPO", "GitHub repository contains unsupported characters")
    if reference.number < 1:
        raise GitHubCliError("INVALID_NUMBER", "GitHub issue, pull request or run id must be >= 1")


def _subprocess_runner(argv: Sequence[str], timeout_seconds: int) -> GitHubCliResult:
    completed = subprocess.run(list(argv), text=True, capture_output=True, timeout=timeout_seconds, check=False)
    return GitHubCliResult(command=tuple(argv), returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
