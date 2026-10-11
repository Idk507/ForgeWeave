from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import EffectSet, PolicyDecision, PolicyOutcome, TaskStatus, ToolCall, ToolExecutionState
from forgeweave.events import EventStore, ToolExecutionRecorder
from forgeweave.task import TaskRecoveryCoordinator, TaskStateMachine


class TaskRecoveryCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = EventStore.open(self.root / "events.db")
        self.addCleanup(self.store.close)
        self.tasks = TaskStateMachine(self.store)
        self.tool_recorder = ToolExecutionRecorder(self.store)

    def test_prepare_resume_cancels_not_dispatched_calls_and_starts_new_attempt(self) -> None:
        self._failed_task()
        authorized = self._authorized_call("authorized-call")

        report = TaskRecoveryCoordinator(events=self.store, tasks=self.tasks).prepare_resume(
            task_id="task-1",
            recovered_attempt_id="attempt-1",
            new_attempt_id="attempt-2",
            evidence="resume after process restart",
        )

        self.assertTrue(report.can_continue)
        self.assertEqual([item.execution_id for item in report.cancelled_tool_executions], [authorized.call_id])
        self.assertEqual(report.unknown_tool_executions, ())
        self.assertIsNotNone(report.resumed_record)
        assert report.resumed_record is not None
        self.assertEqual(report.resumed_record.task.status, TaskStatus.RUNNING)
        self.assertEqual(report.resumed_record.current_attempt_id, "attempt-2")
        self.assertEqual(self.store.get_tool_execution(authorized.call_id).state, ToolExecutionState.CANCELLED)

    def test_prepare_resume_blocks_when_dispatching_call_has_unknown_outcome(self) -> None:
        self._failed_task()
        dispatching = self._authorized_call("dispatching-call")
        self.tool_recorder.mark_dispatching(dispatching.call_id)

        report = TaskRecoveryCoordinator(events=self.store, tasks=self.tasks).prepare_resume(
            task_id="task-1",
            recovered_attempt_id="attempt-1",
            new_attempt_id="attempt-2",
            evidence="crashed during dispatch",
        )

        self.assertFalse(report.can_continue)
        self.assertIsNone(report.resumed_record)
        self.assertEqual([item.execution_id for item in report.unknown_tool_executions], [dispatching.call_id])
        self.assertEqual(self.tasks.record("task-1").current_attempt_id, "attempt-1")
        self.assertEqual(self.store.get_tool_execution(dispatching.call_id).state, ToolExecutionState.OUTCOME_UNKNOWN)

    def test_prepare_resume_only_reconciles_requested_attempt(self) -> None:
        self._failed_task()
        scoped = self._authorized_call("scoped-call", attempt_id="attempt-1")
        other = self._authorized_call("other-call", attempt_id="attempt-other")

        report = TaskRecoveryCoordinator(events=self.store, tasks=self.tasks).prepare_resume(
            task_id="task-1",
            recovered_attempt_id="attempt-1",
            new_attempt_id="attempt-2",
            evidence="resume scoped attempt",
        )

        self.assertTrue(report.can_continue)
        self.assertEqual(self.store.get_tool_execution(scoped.call_id).state, ToolExecutionState.CANCELLED)
        self.assertEqual(self.store.get_tool_execution(other.call_id).state, ToolExecutionState.AUTHORIZED)

    def _failed_task(self) -> None:
        self.tasks.create_task(task_id="task-1", title="Fix a seeded bug", attempt_id="attempt-1")
        self.tasks.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
        self.tasks.transition("task-1", TaskStatus.RUNNING, reason="start loop")
        self.tasks.transition("task-1", TaskStatus.FAILED, reason="process stopped")

    def _authorized_call(self, call_id: str, *, attempt_id: str = "attempt-1") -> ToolCall:
        call = ToolCall(
            call_id=call_id,
            tool_name="write_text",
            tool_schema_version="tool.v1",
            arguments={"path": "out.txt"},
            argument_hash=f"sha256:args-{call_id}",
            effects=EffectSet(writes=frozenset({"workspace"})),
        )
        self.tool_recorder.record_requested(task_id="task-1", attempt_id=attempt_id, call=call)
        self.tool_recorder.record_policy_decision(
            PolicyDecision(
                decision_id=f"policy-{call_id}",
                task_id="task-1",
                attempt_id=attempt_id,
                tool_call_id=call_id,
                outcome=PolicyOutcome.ALLOW,
                reason="allowed",
                policy_revision="policy-v1",
            )
        )
        return call


if __name__ == "__main__":
    unittest.main()
