"""Task CLI projections and recovery-backed commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from forgeweave.events import EventStore
from forgeweave.tools import GitTools
from forgeweave.contracts import TaskStatus
from forgeweave.task import TaskProjectionBuilder, TaskRecoveryCoordinator, TaskResumeRecoveryReport, TaskStateMachine


@dataclass(frozen=True)
class TaskCancelView:
    """Stable projection emitted by `fw task cancel`."""

    task_id: str
    cancelled: bool
    status: str
    current_attempt_id: str
    current_attempt_status: str

    @classmethod
    def from_record(cls, task_id: str, record) -> "TaskCancelView":
        """Create a CLI-safe cancellation view from a task record."""

        return cls(
            task_id=task_id,
            cancelled=record.task.status is TaskStatus.CANCELLED,
            status=record.task.status.value,
            current_attempt_id=record.current_attempt_id,
            current_attempt_status=record.current_attempt.status.value,
        )


@dataclass(frozen=True)
class TaskDiffView:
    """Stable projection emitted by `fw task diff`."""

    repo_root: str
    patch: str
    truncated: bool
    max_bytes: int


def task_diff_from_repo(path: Path, *, max_bytes: int) -> TaskDiffView:
    """Read a bounded unstaged Git diff from an explicit repository root."""

    diff = GitTools(path).diff(max_bytes=max_bytes)
    return TaskDiffView(repo_root=str(path.resolve()), patch=diff.patch, truncated=diff.truncated, max_bytes=max_bytes)


def render_task_diff(view: TaskDiffView, *, as_json: bool) -> str:
    """Render a task diff projection for humans or machines."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    header = [
        f"Repository: {view.repo_root}",
        f"Truncated: {str(view.truncated).lower()}",
        f"Max bytes: {view.max_bytes}",
    ]
    if view.patch:
        header.extend(["Patch:", view.patch.rstrip("\n")])
    else:
        header.append("Patch: <empty>")
    return "\n".join(header)


@dataclass(frozen=True)
class TaskResumeView:
    """Stable projection emitted by `fw task resume`."""

    task_id: str
    recovered_attempt_id: str
    new_attempt_id: str
    resumed: bool
    cancelled_tool_executions: tuple[str, ...]
    unknown_tool_executions: tuple[str, ...]
    status: str
    current_attempt_id: str

    @classmethod
    def from_report(cls, report: TaskResumeRecoveryReport) -> "TaskResumeView":
        """Create a CLI-safe view from a recovery report."""

        if report.resumed_record is not None:
            status = report.resumed_record.task.status.value
            current_attempt_id = report.resumed_record.current_attempt_id
            new_attempt_id = report.resumed_record.current_attempt_id
        else:
            status = "WAITING_RECONCILIATION"
            current_attempt_id = report.recovered_attempt_id
            new_attempt_id = ""
        return cls(
            task_id=report.task_id,
            recovered_attempt_id=report.recovered_attempt_id,
            new_attempt_id=new_attempt_id,
            resumed=report.can_continue,
            cancelled_tool_executions=tuple(item.execution_id for item in report.cancelled_tool_executions),
            unknown_tool_executions=tuple(item.execution_id for item in report.unknown_tool_executions),
            status=status,
            current_attempt_id=current_attempt_id,
        )


def resume_task_from_event_store(
    path: Path,
    *,
    task_id: str,
    recovered_attempt_id: str,
    new_attempt_id: str,
    evidence: str,
) -> TaskResumeView:
    """Rebuild task state, reconcile the recovered attempt, and append resume when safe."""

    store = EventStore.open(path)
    try:
        summary = TaskProjectionBuilder(store).build(task_id)
        machine = TaskStateMachine(store)
        machine.hydrate(summary.record)
        report = TaskRecoveryCoordinator(events=store, tasks=machine).prepare_resume(
            task_id=task_id,
            recovered_attempt_id=recovered_attempt_id,
            new_attempt_id=new_attempt_id,
            evidence=evidence,
        )
        return TaskResumeView.from_report(report)
    finally:
        store.close()


def render_task_resume(view: TaskResumeView, *, as_json: bool) -> str:
    """Render a task resume result for humans or machines."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    lines = [
        f"Task: {view.task_id}",
        f"Recovered attempt: {view.recovered_attempt_id}",
        f"Resumed: {str(view.resumed).lower()}",
        f"Status: {view.status}",
        f"Current attempt: {view.current_attempt_id}",
    ]
    if view.cancelled_tool_executions:
        lines.append("Cancelled tool executions: " + ", ".join(view.cancelled_tool_executions))
    if view.unknown_tool_executions:
        lines.append("Unknown tool executions: " + ", ".join(view.unknown_tool_executions))
    return "\n".join(lines)


def cancel_task_from_event_store(path: Path, *, task_id: str, reason: str) -> TaskCancelView:
    """Rebuild task state from events and append a cancellation transition."""

    store = EventStore.open(path)
    try:
        summary = TaskProjectionBuilder(store).build(task_id)
        machine = TaskStateMachine(store)
        machine.hydrate(summary.record)
        record = machine.transition(task_id, TaskStatus.CANCELLED, reason=reason)
        return TaskCancelView.from_record(task_id, record)
    finally:
        store.close()


def render_task_cancel(view: TaskCancelView, *, as_json: bool) -> str:
    """Render a task cancellation result for humans or machines."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    return "\n".join(
        [
            f"Task: {view.task_id}",
            f"Cancelled: {str(view.cancelled).lower()}",
            f"Status: {view.status}",
            f"Current attempt: {view.current_attempt_id} ({view.current_attempt_status})",
        ]
    )
