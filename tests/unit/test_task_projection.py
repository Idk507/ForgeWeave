from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import AttemptStatus, EventKind, TaskStatus
from forgeweave.events import EventStore
from forgeweave.task import TaskProjectionBuilder, TaskStateMachine


class TaskProjectionBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = EventStore.open(self.root / "events.db")
        self.addCleanup(self.store.close)
        self.machine = TaskStateMachine(self.store)

    def test_rebuilds_current_task_and_attempt_status_from_events(self) -> None:
        self.machine.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")
        self.machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
        self.machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
        self.machine.transition("task-1", TaskStatus.VERIFYING, reason="run checks")

        summary = TaskProjectionBuilder(self.store).build("task-1")

        self.assertEqual(summary.record.task.title, "Fix a seeded bug")
        self.assertEqual(summary.record.task.status, TaskStatus.VERIFYING)
        self.assertEqual(summary.record.current_attempt.status, AttemptStatus.VERIFYING)
        self.assertEqual(summary.event_count, 5)
        self.assertEqual(summary.last_event_kind, EventKind.TASK_STATE_CHANGED)

    def test_rebuilds_resumed_attempt_as_current_attempt(self) -> None:
        self.machine.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")
        self.machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
        self.machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
        self.machine.transition("task-1", TaskStatus.FAILED, reason="process stopped")
        self.machine.resume("task-1", new_attempt_id="attempt-2")

        summary = TaskProjectionBuilder(self.store).build("task-1")

        self.assertEqual(summary.record.task.status, TaskStatus.RUNNING)
        self.assertEqual(summary.record.current_attempt_id, "attempt-2")
        self.assertEqual(summary.record.current_attempt.status, AttemptStatus.PREPARING)
        self.assertEqual(summary.record.attempts["attempt-1"].status, AttemptStatus.FAILED)

    def test_unknown_task_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            TaskProjectionBuilder(self.store).build("missing")


if __name__ == "__main__":
    unittest.main()
