from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import (
    EffectSet,
    EventKind,
    PolicyDecision,
    PolicyOutcome,
    ToolCall,
    ToolExecutionState,
    ToolFailure,
    ToolResult,
)
from forgeweave.events import EventStore, ToolExecutionRecorder


class ToolExecutionRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = EventStore.open(self.root / "events.db")
        self.addCleanup(self.store.close)

    def test_records_call_policy_and_result_in_event_order(self) -> None:
        recorder = ToolExecutionRecorder(self.store)
        call = ToolCall(
            call_id="call-1",
            tool_name="read_file",
            tool_schema_version="tool.v1",
            arguments={"path": "README.md"},
            argument_hash="sha256:args",
            effects=EffectSet(reads=frozenset({"README.md"})),
        )
        decision = PolicyDecision(
            decision_id="policy-1",
            task_id="task-1",
            attempt_id="attempt-1",
            tool_call_id="call-1",
            outcome=PolicyOutcome.ALLOW,
            reason="read-only",
            policy_revision="policy-v1",
        )
        result = ToolResult(call_id="call-1", output_ref="artifact://task-1/out", output_hash="sha256:out")

        recorder.record_requested(task_id="task-1", attempt_id="attempt-1", call=call)
        recorder.record_policy_decision(decision)
        recorder.mark_dispatching("call-1")
        recorder.record_result(result)

        self.assertEqual(
            [event.kind for event in self.store.list_events("task-1")],
            [EventKind.TOOL_CALL_REQUESTED, EventKind.POLICY_DECISION, EventKind.TOOL_RESULT],
        )
        execution = self.store.get_tool_execution("call-1")
        self.assertEqual(execution.state, ToolExecutionState.SUCCEEDED)
        self.assertEqual(execution.effect_hash, call.effect_hash)

    def test_records_tool_failure_as_terminal_state(self) -> None:
        recorder = ToolExecutionRecorder(self.store)
        call = self._requested_allowed_call(recorder, call_id="call-2")
        failure = ToolFailure(call_id=call.call_id, error_type="Timeout", message="timed out", retryable=True)

        recorder.mark_dispatching(call.call_id)
        recorder.record_failure(failure)

        self.assertEqual(self.store.get_tool_execution(call.call_id).state, ToolExecutionState.FAILED)
        self.assertEqual(self.store.list_events("task-1")[-1].kind, EventKind.TOOL_FAILURE)

    def test_unknown_outcome_requires_evidence_and_is_listed_for_reconciliation(self) -> None:
        recorder = ToolExecutionRecorder(self.store)
        call = self._requested_allowed_call(recorder, call_id="call-3")
        recorder.mark_dispatching(call.call_id)

        with self.assertRaises(ValueError):
            recorder.mark_outcome_unknown(call.call_id, reconciliation_evidence="")

        recorder.mark_outcome_unknown(call.call_id, reconciliation_evidence="process killed after dispatch")

        pending = recorder.reconciliation_required()
        self.assertEqual([item.execution_id for item in pending], [call.call_id])
        self.assertEqual(pending[0].state, ToolExecutionState.OUTCOME_UNKNOWN)
        self.assertEqual(len(self.store.list_events("task-1")), 2)

    def test_policy_decision_without_requested_call_is_rejected(self) -> None:
        recorder = ToolExecutionRecorder(self.store)
        decision = PolicyDecision(
            decision_id="policy-missing",
            task_id="task-1",
            attempt_id="attempt-1",
            tool_call_id="missing-call",
            outcome=PolicyOutcome.ALLOW,
            reason="unknown",
            policy_revision="policy-v1",
        )

        with self.assertRaises(KeyError):
            recorder.record_policy_decision(decision)

    def _requested_allowed_call(self, recorder: ToolExecutionRecorder, *, call_id: str) -> ToolCall:
        call = ToolCall(
            call_id=call_id,
            tool_name="shell_test",
            tool_schema_version="tool.v1",
            arguments={"argv": ["python", "-V"]},
            argument_hash=f"sha256:args-{call_id}",
            effects=EffectSet(process=frozenset({"python"})),
        )
        decision = PolicyDecision(
            decision_id=f"policy-{call_id}",
            task_id="task-1",
            attempt_id="attempt-1",
            tool_call_id=call_id,
            outcome=PolicyOutcome.ALLOW,
            reason="test command allowed",
            policy_revision="policy-v1",
        )
        recorder.record_requested(task_id="task-1", attempt_id="attempt-1", call=call)
        recorder.record_policy_decision(decision)
        return call


if __name__ == "__main__":
    unittest.main()
