"""Approval-required GitHub publication plans.

This module prepares external-write actions as explicit plans only. It does not
execute GitHub, Git, deployment or messaging commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re

from .gh import GitHubCliError, GitHubReference

_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,160}")
_TITLE_RE = re.compile(r"[\S][\s\S]{0,199}")


class GitHubPublicationKind(str, Enum):
    """External write action kinds that require explicit approval."""

    BRANCH_PUSH = "branch_push"
    PR_CREATE = "pr_create"
    REVIEW_REPLY = "review_reply"
    DEPLOYMENT = "deployment"


@dataclass(frozen=True)
class GitHubPublicationPlan:
    """Prepared external-write command that must be separately approved."""

    kind: GitHubPublicationKind
    repository: str
    argv: tuple[str, ...]
    summary: str
    idempotency_key: str
    requires_approval: bool = True


def plan_branch_push(*, reference: GitHubReference, local_branch: str, remote_branch: str | None = None) -> GitHubPublicationPlan:
    """Plan a branch push without executing it."""

    local = _safe_branch(local_branch, field="local_branch")
    remote = _safe_branch(remote_branch or local, field="remote_branch")
    argv = ("git", "push", "origin", f"{local}:refs/heads/{remote}")
    return _plan(GitHubPublicationKind.BRANCH_PUSH, reference.repository, argv, f"Push local branch {local} to {reference.repository}:{remote}")


def plan_pr_create(*, reference: GitHubReference, head: str, base: str, title: str, body_file: str) -> GitHubPublicationPlan:
    """Plan PR creation with a body file, not inline user/model text."""

    safe_head = _safe_branch(head, field="head")
    safe_base = _safe_branch(base, field="base")
    safe_title = _safe_title(title)
    safe_body_file = _safe_body_file(body_file)
    argv = ("gh", "pr", "create", "--repo", reference.repository, "--head", safe_head, "--base", safe_base, "--title", safe_title, "--body-file", safe_body_file)
    return _plan(GitHubPublicationKind.PR_CREATE, reference.repository, argv, f"Create PR in {reference.repository} from {safe_head} into {safe_base}")


def plan_review_reply(*, reference: GitHubReference, comment_id: int, body_file: str) -> GitHubPublicationPlan:
    """Plan a review-comment reply through GitHub API without executing it."""

    if comment_id < 1:
        raise GitHubCliError("INVALID_COMMENT_ID", "comment_id must be >= 1")
    safe_body_file = _safe_body_file(body_file)
    argv = (
        "gh",
        "api",
        f"repos/{reference.repository}/pulls/{reference.number}/comments/{comment_id}/replies",
        "--method",
        "POST",
        "--input",
        safe_body_file,
    )
    return _plan(GitHubPublicationKind.REVIEW_REPLY, reference.repository, argv, f"Reply to PR review comment {comment_id} in {reference.repository}#{reference.number}")


def plan_deployment(*, reference: GitHubReference, environment: str, ref: str, payload_file: str) -> GitHubPublicationPlan:
    """Plan a GitHub deployment API request without executing it."""

    safe_environment = _safe_branch(environment, field="environment")
    safe_ref = _safe_branch(ref, field="ref")
    safe_payload_file = _safe_body_file(payload_file)
    argv = (
        "gh",
        "api",
        f"repos/{reference.repository}/deployments",
        "--method",
        "POST",
        "--field",
        f"environment={safe_environment}",
        "--field",
        f"ref={safe_ref}",
        "--input",
        safe_payload_file,
    )
    return _plan(GitHubPublicationKind.DEPLOYMENT, reference.repository, argv, f"Request deployment for {reference.repository}@{safe_ref} to {safe_environment}")


def _plan(kind: GitHubPublicationKind, repository: str, argv: tuple[str, ...], summary: str) -> GitHubPublicationPlan:
    key_material = "\0".join((kind.value, repository, *argv))
    return GitHubPublicationPlan(kind=kind, repository=repository, argv=argv, summary=summary, idempotency_key="github-publication:" + sha256(key_material.encode("utf-8")).hexdigest())


def _safe_branch(value: str, *, field: str) -> str:
    if not value or not _BRANCH_RE.fullmatch(value) or ".." in value or value.startswith(("/", "-")) or value.endswith("/"):
        raise GitHubCliError("INVALID_PUBLICATION_REF", f"unsafe publication ref in {field}")
    return value


def _safe_title(value: str) -> str:
    stripped = value.strip()
    if not _TITLE_RE.fullmatch(stripped):
        raise GitHubCliError("INVALID_PR_TITLE", "PR title must be non-empty and at most 200 characters")
    return stripped


def _safe_body_file(value: str) -> str:
    if not value or value.startswith(("-", "\0")) or "\0" in value:
        raise GitHubCliError("INVALID_BODY_FILE", "body/payload file path is unsafe")
    return value
