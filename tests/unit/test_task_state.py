from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import AttemptStatus, EventKind, TaskStatus
from forgeweave.events import EventStore
from forgeweave.task import TaskStateMachine


class TaskStateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_create_task_records_task_and_first_attempt_events(self) -> None:
        store = EventStore.open(self.root / "events.db")
        machine = TaskStateMachine(store)

        record = machine.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")

        self.assertEqual(record.task.status, TaskStatus.CREATED)
        self.assertEqual(record.current_attempt.status, AttemptStatus.PREPARING)
        self.assertEqual([event.kind for event in store.list_events("task-1")], [EventKind.TASK_CREATED, EventKind.ATTEMPT_STARTED])
        store.close()

    def test_legal_transition_updates_task_and_appends_event(self) -> None:
        store = EventStore.open(self.root / "events.db")
        machine = TaskStateMachine(store)
        machine.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")

        record = machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")

        self.assertEqual(record.task.status, TaskStatus.PREPARING)
        self.assertEqual(store.list_events("task-1")[-1].kind, EventKind.TASK_STATE_CHANGED)
        store.close()

    def test_illegal_transition_is_rejected_without_appending_event(self) -> None:
        store = EventStore.open(self.root / "events.db")
        machine = TaskStateMachine(store)
        machine.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")
        before_count = len(store.list_events("task-1"))

        with self.assertRaises(ValueError):
            machine.transition("task-1", TaskStatus.COMPLETED, reason="skip the lifecycle")

        self.assertEqual(len(store.list_events("task-1")), before_count)
        store.close()

    def test_resume_creates_new_attempt_and_preserves_prior_attempt(self) -> None:
        store = EventStore.open(self.root / "events.db")
        machine = TaskStateMachine(store)
        machine.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")
        machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
        machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
        machine.transition("task-1", TaskStatus.FAILED, reason="process killed")
        failed_attempt = machine.record("task-1").attempts["attempt-1"]

        resumed = machine.resume("task-1", new_attempt_id="attempt-2")

        self.assertEqual(failed_attempt.status, AttemptStatus.FAILED)
        self.assertEqual(resumed.current_attempt.attempt_id, "attempt-2")
        self.assertEqual(resumed.current_attempt.status, AttemptStatus.PREPARING)
        self.assertEqual(resumed.attempts["attempt-1"], failed_attempt)
        self.assertEqual(store.list_events("task-1")[-1].kind, EventKind.ATTEMPT_STARTED)
        store.close()


if __name__ == "__main__":
    unittest.main()
