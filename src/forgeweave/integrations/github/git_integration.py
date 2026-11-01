"""Git branch integration and signed commit planning.

Plans in this module describe local Git mutations but do not execute them. The
execution boundary can later consume these plans only after policy approval and
fresh workspace checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re

from .gh import GitHubCliError

_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,160}")
_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
_MESSAGE_RE = re.compile(r"[\S][\s\S]{0,499}")


class GitIntegrationKind(str, Enum):
    """Local Git mutation plan kinds."""

    COMMIT = "commit"
    MERGE = "merge"
    CHERRY_PICK = "cherry_pick"


class ConflictRisk(str, Enum):
    """Static branch-integration risk classification."""

    LOW = "low"
    NEEDS_PREFLIGHT = "needs_preflight"
    HIGH = "high"


@dataclass(frozen=True)
class GitIntegrationPlan:
    """Prepared local Git mutation plan."""

    kind: GitIntegrationKind
    argv: tuple[str, ...]
    preflight_argv: tuple[tuple[str, ...], ...]
    summary: str
    idempotency_key: str
    requires_approval: bool
    signed_commit_required: bool
    conflict_risk: ConflictRisk


def plan_signed_commit(*, message: str, sign: bool = True, all_tracked: bool = True) -> GitIntegrationPlan:
    """Plan a local commit with optional signed-commit enforcement."""

    safe_message = _safe_message(message)
    argv = ["git", "commit"]
    if all_tracked:
        argv.append("-a")
    if sign:
        argv.append("-S")
    argv.extend(["-m", safe_message])
    return _plan(
        kind=GitIntegrationKind.COMMIT,
        argv=tuple(argv),
        preflight_argv=(("git", "status", "--porcelain=v1"),),
        summary="Create signed local commit" if sign else "Create unsigned local commit",
        requires_approval=True,
        signed_commit_required=sign,
        conflict_risk=ConflictRisk.LOW,
    )


def plan_branch_merge(*, base_branch: str, source_branch: str, signed_commit_required: bool = True) -> GitIntegrationPlan:
    """Plan a conflict-aware branch merge."""

    base = _safe_ref(base_branch, field="base_branch")
    source = _safe_ref(source_branch, field="source_branch")
    preflight = (
        ("git", "merge-base", "--is-ancestor", base, source),
        ("git", "merge-tree", base, source),
    )
    argv = ("git", "merge", "--no-ff", "--no-commit", source)
    return _plan(
        kind=GitIntegrationKind.MERGE,
        argv=argv,
        preflight_argv=preflight,
        summary=f"Merge {source} into {base} with conflict preflight",
        requires_approval=True,
        signed_commit_required=signed_commit_required,
        conflict_risk=ConflictRisk.NEEDS_PREFLIGHT,
    )


def plan_cherry_pick(*, commit_sha: str, signed_commit_required: bool = True) -> GitIntegrationPlan:
    """Plan a conflict-aware cherry-pick of one exact commit."""

    sha = _safe_sha(commit_sha)
    preflight = (("git", "cat-file", "-e", f"{sha}^{{commit}}"),)
    argv = ("git", "cherry-pick", "--no-commit", sha)
    return _plan(
        kind=GitIntegrationKind.CHERRY_PICK,
        argv=argv,
        preflight_argv=preflight,
        summary=f"Cherry-pick {sha[:12]} with conflict preflight",
        requires_approval=True,
        signed_commit_required=signed_commit_required,
        conflict_risk=ConflictRisk.NEEDS_PREFLIGHT,
    )


def _plan(
    *,
    kind: GitIntegrationKind,
    argv: tuple[str, ...],
    preflight_argv: tuple[tuple[str, ...], ...],
    summary: str,
    requires_approval: bool,
    signed_commit_required: bool,
    conflict_risk: ConflictRisk,
) -> GitIntegrationPlan:
    key_material = "\0".join((kind.value, *argv, *(" ".join(cmd) for cmd in preflight_argv), str(signed_commit_required)))
    return GitIntegrationPlan(
        kind=kind,
        argv=argv,
        preflight_argv=preflight_argv,
        summary=summary,
        idempotency_key="git-integration:" + sha256(key_material.encode("utf-8")).hexdigest(),
        requires_approval=requires_approval,
        signed_commit_required=signed_commit_required,
        conflict_risk=conflict_risk,
    )


def _safe_ref(value: str, *, field: str) -> str:
    if not value or not _BRANCH_RE.fullmatch(value) or ".." in value or value.startswith(("/", "-")) or value.endswith("/"):
        raise GitHubCliError("INVALID_GIT_REF", f"unsafe git ref in {field}")
    return value


def _safe_sha(value: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise GitHubCliError("INVALID_COMMIT_SHA", "commit_sha must be a 40-character SHA")
    return value.lower()


def _safe_message(value: str) -> str:
    stripped = value.strip()
    if not _MESSAGE_RE.fullmatch(stripped):
        raise GitHubCliError("INVALID_COMMIT_MESSAGE", "commit message must be non-empty and at most 500 characters")
    return stripped
