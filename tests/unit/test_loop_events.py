from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.contracts import ActorKind, EventKind
from forgeweave.core import StopDecision, StopReason
from forgeweave.events import EventStore, LoopEventRecorder


class LoopEventRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = EventStore.open(self.root / "events.db")
        self.addCleanup(self.store.close)

    def test_records_loop_start_and_end_in_append_order(self) -> None:
        recorder = LoopEventRecorder(self.store)

        started = recorder.record_loop_started(
            task_id="task-1",
            attempt_id="attempt-1",
            correlation_id="corr-1",
            diagnostics_ref="diagnostics://task-1/attempt-1/start",
        )
        ended = recorder.record_loop_ended(
            task_id="task-1",
            attempt_id="attempt-1",
            correlation_id="corr-1",
            stop_decision=StopDecision(StopReason.FINAL_ANSWER, True, {"message": "done"}),
            diagnostics_ref="diagnostics://task-1/attempt-1/end",
        )

        events = self.store.list_events("task-1")
        self.assertEqual([event.event_id for event in events], [started.event_id, ended.event_id])
        self.assertEqual([event.sequence for event in events], [1, 2])
        self.assertEqual([event.kind for event in events], [EventKind.STEP_RECORDED, EventKind.STEP_RECORDED])
        self.assertEqual([event.actor for event in events], [ActorKind.SYSTEM, ActorKind.SYSTEM])
        self.assertEqual(events[0].payload_ref, "loop-started://diagnostics://task-1/attempt-1/start")
        self.assertEqual(events[1].payload_ref, "loop-ended://final_answer/diagnostics://task-1/attempt-1/end")

    def test_rejects_blank_diagnostics_ref(self) -> None:
        recorder = LoopEventRecorder(self.store)

        with self.assertRaises(ValueError):
            recorder.record_loop_started(
                task_id="task-1",
                attempt_id="attempt-1",
                correlation_id="corr-1",
                diagnostics_ref=" ",
            )


if __name__ == "__main__":
    unittest.main()
