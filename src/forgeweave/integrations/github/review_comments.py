"""GitHub pull request review-comment intake."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .gh import GitHubCliError, GitHubReference

_PATH_RE = re.compile(r"[A-Za-z0-9_./@+ -]+")
_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


@dataclass(frozen=True)
class GitHubReviewComment:
    """Normalized pull request review comment."""

    comment_id: int
    path: str
    body: str
    author: str | None
    original_commit_id: str | None
    commit_id: str | None
    line: int | None
    original_line: int | None
    outdated: bool
    url: str | None


@dataclass(frozen=True)
class ReviewCommentPlanItem:
    """Actionable planning input mapped to the current checkout when possible."""

    comment_id: int
    path: str
    target_line: int | None
    body: str
    author: str | None
    stale: bool
    reason: str
    url: str | None


@dataclass(frozen=True)
class ReviewCommentIntake:
    """Normalized review-comment intake for one pull request."""

    repository: str
    pull_number: int
    comments: tuple[GitHubReviewComment, ...]
    plan_items: tuple[ReviewCommentPlanItem, ...]


def intake_review_comments(reference: GitHubReference, payload: list[dict[str, Any]], *, current_head_sha: str | None = None) -> ReviewCommentIntake:
    """Normalize GitHub review comments into current-line planning items."""

    if current_head_sha is not None and not _SHA_RE.fullmatch(current_head_sha):
        raise GitHubCliError("INVALID_HEAD_SHA", "current_head_sha must be a 40-character SHA")
    comments = tuple(_parse_comment(item) for item in payload)
    plan_items = tuple(_plan_item(comment, current_head_sha=current_head_sha.lower() if current_head_sha else None) for comment in comments)
    return ReviewCommentIntake(repository=reference.repository, pull_number=reference.number, comments=comments, plan_items=plan_items)


def _parse_comment(item: dict[str, Any]) -> GitHubReviewComment:
    comment_id = _positive_int(item.get("id"), field="id")
    path = _safe_path(str(item.get("path") or ""))
    body = str(item.get("body") or "").strip()
    if not body:
        raise GitHubCliError("MISSING_REVIEW_BODY", "review comment body must not be empty")
    author = _author(item.get("user"))
    original_commit_id = _optional_sha(item.get("original_commit_id"), field="original_commit_id")
    commit_id = _optional_sha(item.get("commit_id"), field="commit_id")
    line = _optional_positive_int(item.get("line"), field="line")
    original_line = _optional_positive_int(item.get("original_line"), field="original_line")
    if line is None and original_line is None:
        raise GitHubCliError("MISSING_REVIEW_LINE", "review comment must include line or original_line")
    outdated = bool(item.get("outdated", False))
    url = item.get("html_url")
    return GitHubReviewComment(
        comment_id=comment_id,
        path=path,
        body=body,
        author=author,
        original_commit_id=original_commit_id,
        commit_id=commit_id,
        line=line,
        original_line=original_line,
        outdated=outdated,
        url=str(url) if url else None,
    )


def _plan_item(comment: GitHubReviewComment, *, current_head_sha: str | None) -> ReviewCommentPlanItem:
    stale_reasons: list[str] = []
    if comment.outdated:
        stale_reasons.append("outdated")
    if current_head_sha and comment.commit_id and comment.commit_id.lower() != current_head_sha:
        stale_reasons.append("commit_mismatch")
    stale = bool(stale_reasons)
    target_line = None if stale else comment.line or comment.original_line
    return ReviewCommentPlanItem(
        comment_id=comment.comment_id,
        path=comment.path,
        target_line=target_line,
        body=comment.body,
        author=comment.author,
        stale=stale,
        reason=",".join(stale_reasons) if stale_reasons else "current",
        url=comment.url,
    )


def _safe_path(value: str) -> str:
    if not value or value.startswith(("/", "\\")) or ".." in value or not _PATH_RE.fullmatch(value):
        raise GitHubCliError("INVALID_REVIEW_PATH", "review comment path is unsafe")
    return value.replace("\\", "/")


def _positive_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise GitHubCliError("INVALID_REVIEW_COMMENT", f"review comment {field} must be a positive integer")
    return value


def _optional_positive_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, field=field)


def _optional_sha(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise GitHubCliError("INVALID_REVIEW_SHA", f"review comment {field} must be a 40-character SHA")
    return value.lower()


def _author(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    login = value.get("login")
    if not isinstance(login, str) or not login.strip():
        return None
    return login.strip()
