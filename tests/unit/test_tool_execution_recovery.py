from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import EffectSet, PolicyDecision, PolicyOutcome, ToolCall, ToolExecutionState, ToolResult
from forgeweave.events import EventStore, ToolExecutionRecorder, ToolExecutionRecovery


class ToolExecutionRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = EventStore.open(self.root / "events.db")
        self.addCleanup(self.store.close)
        self.recorder = ToolExecutionRecorder(self.store)

    def test_restart_reconciliation_cancels_not_dispatched_and_marks_dispatching_unknown(self) -> None:
        requested = self._requested_call("requested-call")
        authorized = self._authorized_call("authorized-call")
        dispatching = self._authorized_call("dispatching-call")
        self.recorder.mark_dispatching(dispatching.call_id)
        succeeded = self._authorized_call("succeeded-call")
        self.recorder.mark_dispatching(succeeded.call_id)
        self.recorder.record_result(ToolResult(call_id=succeeded.call_id, output_ref="artifact://task/out", output_hash="sha256:out"))

        report = ToolExecutionRecovery(self.store).reconcile_after_restart(evidence="process restarted after crash")

        self.assertEqual({item.execution_id for item in report.cancelled}, {requested.call_id, authorized.call_id})
        self.assertEqual([item.execution_id for item in report.outcome_unknown], [dispatching.call_id])
        self.assertTrue(report.requires_attention)
        self.assertEqual(self.store.get_tool_execution(requested.call_id).state, ToolExecutionState.CANCELLED)
        self.assertEqual(self.store.get_tool_execution(authorized.call_id).state, ToolExecutionState.CANCELLED)
        unknown = self.store.get_tool_execution(dispatching.call_id)
        self.assertEqual(unknown.state, ToolExecutionState.OUTCOME_UNKNOWN)
        self.assertEqual(unknown.reconciliation_evidence, "process restarted after crash")
        self.assertEqual(self.store.get_tool_execution(succeeded.call_id).state, ToolExecutionState.SUCCEEDED)

    def test_restart_reconciliation_can_be_scoped_to_attempt(self) -> None:
        scoped = self._authorized_call("scoped-call", task_id="task-1", attempt_id="attempt-1")
        other = self._authorized_call("other-call", task_id="task-1", attempt_id="attempt-2")

        report = ToolExecutionRecovery(self.store).reconcile_after_restart(
            evidence="recover attempt-1",
            task_id="task-1",
            attempt_id="attempt-1",
        )

        self.assertEqual([item.execution_id for item in report.cancelled], [scoped.call_id])
        self.assertEqual(self.store.get_tool_execution(scoped.call_id).state, ToolExecutionState.CANCELLED)
        self.assertEqual(self.store.get_tool_execution(other.call_id).state, ToolExecutionState.AUTHORIZED)

    def test_restart_reconciliation_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            ToolExecutionRecovery(self.store).reconcile_after_restart(evidence=" ")

    def _requested_call(self, call_id: str, *, task_id: str = "task-1", attempt_id: str = "attempt-1") -> ToolCall:
        call = ToolCall(
            call_id=call_id,
            tool_name="write_text",
            tool_schema_version="tool.v1",
            arguments={"path": "out.txt"},
            argument_hash=f"sha256:args-{call_id}",
            effects=EffectSet(writes=frozenset({"workspace"})),
        )
        self.recorder.record_requested(task_id=task_id, attempt_id=attempt_id, call=call)
        return call

    def _authorized_call(self, call_id: str, *, task_id: str = "task-1", attempt_id: str = "attempt-1") -> ToolCall:
        call = self._requested_call(call_id, task_id=task_id, attempt_id=attempt_id)
        self.recorder.record_policy_decision(
            PolicyDecision(
                decision_id=f"policy-{call_id}",
                task_id=task_id,
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
