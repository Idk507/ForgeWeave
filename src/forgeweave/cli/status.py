"""Status projections and renderers for the minimal CLI surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from forgeweave.events import EventStore
from forgeweave.task import TaskProjectionBuilder, TaskProjectionSummary


@dataclass(frozen=True)
class TaskStatusView:
    """Stable task status projection emitted by `fw task status`."""

    task_id: str
    title: str
    status: str
    current_attempt_id: str
    current_attempt_status: str
    event_count: int
    last_event_kind: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "TaskStatusView":
        """Load a status projection from a JSON-like mapping."""

        required = {
            "task_id",
            "title",
            "status",
            "current_attempt_id",
            "current_attempt_status",
            "event_count",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"missing task status fields: {', '.join(missing)}")
        return cls(
            task_id=_string(payload["task_id"], "task_id"),
            title=_string(payload["title"], "title"),
            status=_string(payload["status"], "status"),
            current_attempt_id=_string(payload["current_attempt_id"], "current_attempt_id"),
            current_attempt_status=_string(payload["current_attempt_status"], "current_attempt_status"),
            event_count=_integer(payload["event_count"], "event_count"),
            last_event_kind=None if payload.get("last_event_kind") is None else _string(payload["last_event_kind"], "last_event_kind"),
        )

    @classmethod
    def from_projection(cls, summary: TaskProjectionSummary) -> "TaskStatusView":
        """Create a CLI status view from an event-log task projection."""

        record = summary.record
        return cls(
            task_id=record.task.task_id,
            title=record.task.title,
            status=record.task.status.value,
            current_attempt_id=record.current_attempt_id,
            current_attempt_status=record.current_attempt.status.value,
            event_count=summary.event_count,
            last_event_kind=summary.last_event_kind.value,
        )


def task_status_from_event_store(path: Path, *, task_id: str) -> TaskStatusView:
    """Load a task status projection from a ForgeWeave event store."""

    store = EventStore.open(path)
    try:
        return TaskStatusView.from_projection(TaskProjectionBuilder(store).build(task_id))
    finally:
        store.close()


def render_task_status(view: TaskStatusView, *, as_json: bool) -> str:
    """Render a task status projection for humans or machines."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    lines = [
        f"Task: {view.task_id}",
        f"Title: {view.title}",
        f"Status: {view.status}",
        f"Current attempt: {view.current_attempt_id} ({view.current_attempt_status})",
        f"Events: {view.event_count}",
    ]
    if view.last_event_kind is not None:
        lines.append(f"Last event: {view.last_event_kind}")
    return "\n".join(lines)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value
