"""Durable task projections rebuilt from append-only lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from forgeweave.contracts import Attempt, AttemptStatus, Event, EventKind, Task, TaskStatus
from forgeweave.events import EventStore

from .state import TaskRecord


@dataclass(frozen=True)
class TaskProjectionSummary:
    """Compact status projection derived from the event log."""

    record: TaskRecord
    event_count: int
    last_event_kind: EventKind


class TaskProjectionBuilder:
    """Rebuild task state from committed lifecycle events.

    The projection is disposable: the event log is authoritative. Lifecycle
    events carry only bounded, non-secret status metadata in their payload refs.
    """

    def __init__(self, events: EventStore) -> None:
        self._events = events

    def build(self, task_id: str) -> TaskProjectionSummary:
        """Return the latest task projection for `task_id`."""

        events = self._events.list_events(task_id)
        if not events:
            raise KeyError(f"unknown task: {task_id}")

        task: Task | None = None
        attempts: dict[str, Attempt] = {}
        current_attempt_id: str | None = None

        for event in events:
            data = _payload_data(event)
            if event.kind is EventKind.TASK_CREATED:
                title = data.get("title")
                status = _task_status(data.get("task_status"), default=TaskStatus.CREATED)
                task = Task(task_id=event.task_id, title=title or event.task_id, status=status)
            elif event.kind is EventKind.ATTEMPT_STARTED:
                if task is None:
                    raise ValueError("attempt started before task creation")
                attempt_status = _attempt_status(data.get("attempt_status"), default=AttemptStatus.PREPARING)
                attempts[event.attempt_id] = Attempt(
                    attempt_id=event.attempt_id,
                    task_id=event.task_id,
                    status=attempt_status,
                )
                current_attempt_id = event.attempt_id
                task_status = data.get("task_status")
                if task_status is not None:
                    task = task.model_copy(update={"status": TaskStatus(task_status)})
            elif event.kind is EventKind.TASK_STATE_CHANGED:
                if task is None or current_attempt_id is None:
                    raise ValueError("task state changed before task creation")
                status = _task_status(data.get("task_status"), default=task.status)
                task = task.model_copy(update={"status": status})
                attempt_status = _attempt_status(data.get("attempt_status"), default=attempts[current_attempt_id].status)
                attempts[current_attempt_id] = attempts[current_attempt_id].model_copy(update={"status": attempt_status})

        if task is None or current_attempt_id is None:
            raise ValueError("task projection is incomplete")
        return TaskProjectionSummary(
            record=TaskRecord(task=task, attempts=attempts, current_attempt_id=current_attempt_id),
            event_count=len(events),
            last_event_kind=events[-1].kind,
        )


def _payload_data(event: Event) -> dict[str, str]:
    parsed = urlparse(event.payload_ref)
    if parsed.scheme != "inline":
        return {}
    return {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}


def _task_status(value: str | None, *, default: TaskStatus) -> TaskStatus:
    return TaskStatus(value) if value is not None else default


def _attempt_status(value: str | None, *, default: AttemptStatus) -> AttemptStatus:
    return AttemptStatus(value) if value is not None else default
