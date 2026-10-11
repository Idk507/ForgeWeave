from __future__ import annotations

import unittest

from forgeweave.automation import (
    WorkflowExecutionContext,
    WorkflowExecutionResult,
    WorkflowExecutorError,
    WorkflowExecutorRegistry,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
)


class WorkflowExecutorRegistryTests(unittest.TestCase):
    def test_registered_executor_runs_for_kind_and_capability(self) -> None:
        registry = WorkflowExecutorRegistry()
        step = WorkflowStep(step_id="implement", kind=WorkflowStepKind.AGENT, capability="implement")
        registry.register(
            WorkflowStepKind.AGENT,
            lambda context: WorkflowExecutionResult(status=WorkflowStepStatus.SUCCEEDED, reason=f"ran {context.step.step_id}"),
            capability="implement",
        )

        result = registry.execute(WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=step, attempt_number=1))

        self.assertEqual(result.status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(result.reason, "ran implement")

    def test_missing_executor_returns_waiting_external(self) -> None:
        registry = WorkflowExecutorRegistry()
        step = WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT, capability="research")

        result = registry.execute(WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=step, attempt_number=1))

        self.assertEqual(result.status, WorkflowStepStatus.WAITING_EXTERNAL)
        self.assertIn("no mediated executor", result.reason)

    def test_rejects_invalid_executor_status(self) -> None:
        registry = WorkflowExecutorRegistry()
        step = WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT)
        registry.register(
            WorkflowStepKind.AGENT,
            lambda _context: WorkflowExecutionResult(status=WorkflowStepStatus.READY, reason="bad"),
        )

        with self.assertRaises(WorkflowExecutorError) as raised:
            registry.execute(WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=step, attempt_number=1))

        self.assertEqual(raised.exception.code, "INVALID_EXECUTOR_STATUS")


if __name__ == "__main__":
    unittest.main()
