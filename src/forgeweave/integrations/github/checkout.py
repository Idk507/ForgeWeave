"""Commit-pinned checkout planning for GitHub pull requests."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .gh import GitHubCliError, GitHubReference


_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
_REF_RE = re.compile(r"[A-Za-z0-9._/-]+")


@dataclass(frozen=True)
class GitHubCheckoutPlan:
    """Auditable plan for checking out a GitHub pull request at one exact commit."""

    repository: str
    pull_number: int
    head_sha: str
    base_ref: str
    head_ref: str
    head_repository: str
    fetch_ref: str
    checkout_ref: str

    @property
    def git_fetch_argv(self) -> tuple[str, ...]:
        """Return a read-only fetch command for the exact head ref."""

        return ("git", "fetch", "--no-tags", "origin", f"{self.fetch_ref}:{self.checkout_ref}")

    @property
    def git_worktree_argv(self) -> tuple[str, ...]:
        """Return a worktree add command pinned to the exact head SHA."""

        return ("git", "worktree", "add", "--detach", "<worktree-path>", self.head_sha)


def checkout_plan_from_pr_view(reference: GitHubReference, payload: dict[str, Any]) -> GitHubCheckoutPlan:
    """Create a commit-pinned checkout plan from `gh pr view --json ...` output."""

    _require_matching_number(reference, payload)
    head_sha = _head_sha(payload).lower()
    base_ref = _safe_ref(str(payload.get("baseRefName") or ""), field="baseRefName")
    head_ref = _safe_ref(str(payload.get("headRefName") or ""), field="headRefName")
    head_repository = _head_repository(reference, payload)
    fetch_ref = f"pull/{reference.number}/head"
    checkout_ref = f"refs/forgeweave/pr-{reference.number}-{head_sha[:12]}"
    return GitHubCheckoutPlan(
        repository=reference.repository,
        pull_number=reference.number,
        head_sha=head_sha,
        base_ref=base_ref,
        head_ref=head_ref,
        head_repository=head_repository,
        fetch_ref=fetch_ref,
        checkout_ref=checkout_ref,
    )


def _require_matching_number(reference: GitHubReference, payload: dict[str, Any]) -> None:
    number = payload.get("number")
    if number != reference.number:
        raise GitHubCliError("PR_NUMBER_MISMATCH", "PR payload number does not match the requested reference")


def _head_sha(payload: dict[str, Any]) -> str:
    commits = payload.get("commits")
    if not isinstance(commits, list) or not commits:
        raise GitHubCliError("MISSING_COMMITS", "PR payload must include at least one commit")
    last = commits[-1]
    if not isinstance(last, dict):
        raise GitHubCliError("INVALID_COMMIT", "PR commit entries must be JSON objects")
    candidates = (last.get("oid"), last.get("sha"))
    for candidate in candidates:
        if isinstance(candidate, str) and _SHA_RE.fullmatch(candidate):
            return candidate
    raise GitHubCliError("MISSING_HEAD_SHA", "last PR commit must include a 40-character oid or sha")


def _safe_ref(value: str, *, field: str) -> str:
    if not value or not _REF_RE.fullmatch(value) or ".." in value or value.startswith(("/", "-")) or value.endswith("/"):
        raise GitHubCliError("INVALID_REF", f"unsafe GitHub ref in {field}")
    return value


def _head_repository(reference: GitHubReference, payload: dict[str, Any]) -> str:
    raw = payload.get("headRepository")
    if raw is None:
        return reference.repository
    if not isinstance(raw, dict):
        raise GitHubCliError("INVALID_HEAD_REPOSITORY", "headRepository must be a JSON object when present")
    name_with_owner = raw.get("nameWithOwner")
    if name_with_owner is None:
        return reference.repository
    if not isinstance(name_with_owner, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name_with_owner):
        raise GitHubCliError("INVALID_HEAD_REPOSITORY", "headRepository.nameWithOwner is not a safe repository name")
    return name_with_owner
