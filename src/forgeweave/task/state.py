"""Task lifecycle rules and attempt records."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import uuid4

from forgeweave.contracts import (
    ActorKind,
    Attempt,
    AttemptStatus,
    Event,
    EventKind,
    Task,
    TaskStatus,
)
from forgeweave.events import EventStore


LEGAL_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({TaskStatus.PREPARING, TaskStatus.CANCELLED}),
    TaskStatus.PREPARING: frozenset({TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.WAITING_EXTERNAL,
            TaskStatus.VERIFYING,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.WAITING_APPROVAL: frozenset({TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.WAITING_EXTERNAL: frozenset({TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.VERIFYING: frozenset({TaskStatus.COMPLETED, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.RUNNING}),
    TaskStatus.CANCELLED: frozenset(),
}


ATTEMPT_BY_TASK_STATUS: dict[TaskStatus, AttemptStatus] = {
    TaskStatus.PREPARING: AttemptStatus.PREPARING,
    TaskStatus.RUNNING: AttemptStatus.RUNNING,
    TaskStatus.WAITING_APPROVAL: AttemptStatus.WAITING_APPROVAL,
    TaskStatus.WAITING_EXTERNAL: AttemptStatus.WAITING_EXTERNAL,
    TaskStatus.VERIFYING: AttemptStatus.VERIFYING,
    TaskStatus.COMPLETED: AttemptStatus.COMPLETED,
    TaskStatus.FAILED: AttemptStatus.FAILED,
    TaskStatus.CANCELLED: AttemptStatus.CANCELLED,
}


@dataclass(frozen=True)
class TaskRecord:
    """Current task projection kept by the task module."""

    task: Task
    attempts: dict[str, Attempt]
    current_attempt_id: str

    @property
    def current_attempt(self) -> Attempt:
        return self.attempts[self.current_attempt_id]


class TaskStateMachine:
    """Validate task lifecycle changes and append lifecycle events."""

    def __init__(self, events: EventStore) -> None:
        self._events = events
        self._records: dict[str, TaskRecord] = {}

    def create_task(self, *, task_id: str, title: str, attempt_id: str) -> TaskRecord:
        """Create a task and its first attempt."""

        if task_id in self._records:
            raise ValueError(f"task already exists: {task_id}")
        task = Task(task_id=task_id, title=title, status=TaskStatus.CREATED)
        attempt = Attempt(attempt_id=attempt_id, task_id=task_id, status=AttemptStatus.PREPARING)
        record = TaskRecord(task=task, attempts={attempt_id: attempt}, current_attempt_id=attempt_id)
        self._records[task_id] = record
        self._append_event(
            task_id,
            attempt_id,
            EventKind.TASK_CREATED,
            task_status=TaskStatus.CREATED,
            title=title,
        )
        self._append_event(task_id, attempt_id, EventKind.ATTEMPT_STARTED, attempt_status=AttemptStatus.PREPARING)
        return record

    def record(self, task_id: str) -> TaskRecord:
        """Return the current task projection."""

        try:
            return self._records[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown task: {task_id}") from exc

    def hydrate(self, record: TaskRecord) -> TaskRecord:
        """Load a projection rebuilt from durable events into this state machine.

        Hydration does not append events. It lets a fresh process resume from the
        append-only event log before validating and recording the next lifecycle
        transition.
        """

        task_id = record.task.task_id
        if task_id in self._records:
            raise ValueError(f"task already exists: {task_id}")
        self._records[task_id] = record
        return record

    def transition(self, task_id: str, status: TaskStatus, *, reason: str) -> TaskRecord:
        """Move a task to a legal next state and append an event."""

        if not reason.strip():
            raise ValueError("reason must not be blank")
        record = self.record(task_id)
        allowed = LEGAL_TRANSITIONS[record.task.status]
        if status not in allowed:
            raise ValueError(f"illegal task transition: {record.task.status.value} -> {status.value}")

        task = record.task.model_copy(update={"status": status})
        attempt_status = ATTEMPT_BY_TASK_STATUS.get(status, record.current_attempt.status)
        attempt = record.current_attempt.model_copy(update={"status": attempt_status})
        attempts = dict(record.attempts)
        attempts[attempt.attempt_id] = attempt
        updated = TaskRecord(task=task, attempts=attempts, current_attempt_id=attempt.attempt_id)
        self._records[task_id] = updated
        self._append_event(
            task_id,
            attempt.attempt_id,
            EventKind.TASK_STATE_CHANGED,
            task_status=status,
            attempt_status=attempt_status,
        )
        return updated

    def resume(self, task_id: str, *, new_attempt_id: str) -> TaskRecord:
        """Resume a failed task with a new attempt, preserving prior attempts."""

        record = self.record(task_id)
        if record.task.status is not TaskStatus.FAILED:
            raise ValueError("only failed tasks can resume in this slice")
        if new_attempt_id in record.attempts:
            raise ValueError(f"attempt already exists: {new_attempt_id}")

        attempt = Attempt(attempt_id=new_attempt_id, task_id=task_id, status=AttemptStatus.PREPARING)
        attempts = dict(record.attempts)
        attempts[new_attempt_id] = attempt
        task = record.task.model_copy(update={"status": TaskStatus.RUNNING})
        updated = TaskRecord(task=task, attempts=attempts, current_attempt_id=new_attempt_id)
        self._records[task_id] = updated
        self._append_event(
            task_id,
            new_attempt_id,
            EventKind.ATTEMPT_STARTED,
            task_status=TaskStatus.RUNNING,
            attempt_status=AttemptStatus.PREPARING,
        )
        return updated

    def _append_event(
        self,
        task_id: str,
        attempt_id: str,
        kind: EventKind,
        *,
        task_status: TaskStatus | None = None,
        attempt_status: AttemptStatus | None = None,
        title: str | None = None,
    ) -> Event:
        event = Event(
            event_id=f"evt-{uuid4().hex}",
            task_id=task_id,
            attempt_id=attempt_id,
            sequence=1,
            actor=ActorKind.SYSTEM,
            kind=kind,
            correlation_id=f"{task_id}:{attempt_id}",
            payload_ref=_payload_ref(kind, task_status=task_status, attempt_status=attempt_status, title=title),
        )
        return self._events.append(event)


def _payload_ref(
    kind: EventKind,
    *,
    task_status: TaskStatus | None = None,
    attempt_status: AttemptStatus | None = None,
    title: str | None = None,
) -> str:
    query: dict[str, str] = {}
    if task_status is not None:
        query["task_status"] = task_status.value
    if attempt_status is not None:
        query["attempt_status"] = attempt_status.value
    if title is not None:
        query["title"] = title
    suffix = urlencode(query)
    return f"inline://{kind.value}" + (f"?{suffix}" if suffix else "")
