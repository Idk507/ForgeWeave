"""Pre-flight checks applied to every engine request before an engine starts."""

from __future__ import annotations

from pathlib import Path

from .contracts import EngineRequest, IsolationLevel

# Effects ForgeWeave cannot mediate when an engine uses its own native tools.
UNMEDIATED_FORBIDDEN_EFFECTS = frozenset({"browser", "mcp", "network", "publish", "credentials"})


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def validate_request(
    request: EngineRequest,
    *,
    allowed_providers: frozenset[str] | None = None,
) -> list[str]:
    """Return every violation; an empty list means the request may start."""
    problems: list[str] = []
    worktree = request.worktree.resolve()
    original = request.original_checkout.resolve()

    if not worktree.is_dir():
        problems.append("worktree does not exist")
    if worktree == original:
        problems.append("engine must run in a task worktree, not the original checkout")
    if _is_within(request.engine_home, worktree):
        problems.append("engine home must be outside the task worktree")
    if _is_within(request.engine_home, original):
        problems.append("engine home must be outside the original checkout")
    if request.engine_home.resolve() == Path.home().resolve():
        problems.append("engine home must be task-scoped, not the user's home directory")

    if request.isolation is IsolationLevel.DELEGATED_UNMEDIATED:
        if not request.delegated_opt_in:
            problems.append("delegated-unmediated mode requires explicit per-task opt-in")
        denied = sorted(request.requested_effects & UNMEDIATED_FORBIDDEN_EFFECTS)
        if denied:
            problems.append(f"effects not grantable in delegated mode: {', '.join(denied)}")

    if allowed_providers is not None and request.provider not in allowed_providers:
        problems.append(f"provider {request.provider!r} is not allowed by repository policy")
    return problems
