from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    JoinMode,
    JoinPolicy,
    WorkflowDefinition,
    WorkflowExecutionResult,
    WorkflowExecutorRegistry,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    run_workflow_once,
    workflow_input_hash,
)


class WorkflowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)

    def test_records_ready_agent_step_as_waiting_external_without_execution(self) -> None:
        run = self._admit(_definition_with_join())

        result = run_workflow_once(self.store, run_id=run.run_id)

        attempts = self.store.list_attempts(run.run_id)
        self.assertEqual(result.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(result.ready_before, ("research",))
        self.assertEqual(len(result.recorded_steps), 1)
        self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.WAITING_EXTERNAL)
        self.assertFalse(result.execution_started)
        self.assertEqual(attempts[0].step_id, "research")
        self.assertEqual(attempts[0].status, WorkflowStepStatus.WAITING_EXTERNAL)

    def test_completes_join_step_when_dependencies_succeeded(self) -> None:
        run = self._admit(_definition_with_join())
        self.store.record_attempt(_attempt(run.run_id, "research", WorkflowStepStatus.SUCCEEDED))
        self.store.record_attempt(_attempt(run.run_id, "plan", WorkflowStepStatus.SUCCEEDED))

        result = run_workflow_once(self.store, run_id=run.run_id)

        attempts = self.store.list_attempts(run.run_id)
        self.assertEqual(result.ready_before, ("join",))
        self.assertEqual(result.recorded_steps[0].step_id, "join")
        self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(attempts[-1].status, WorkflowStepStatus.SUCCEEDED)

    def test_marks_run_succeeded_after_all_steps_are_complete(self) -> None:
        run = self._admit(_single_step_definition())
        self.store.record_attempt(_attempt(run.run_id, "verify", WorkflowStepStatus.SUCCEEDED))

        result = run_workflow_once(self.store, run_id=run.run_id)

        self.assertEqual(result.run_status, WorkflowRunStatus.SUCCEEDED)
        self.assertEqual(result.recorded_steps, ())
        self.assertEqual(self.store.get_run(run.run_id).status, WorkflowRunStatus.SUCCEEDED)

    def test_failed_step_marks_run_failed(self) -> None:
        run = self._admit(_single_step_definition())
        self.store.record_attempt(_attempt(run.run_id, "verify", WorkflowStepStatus.FAILED))

        result = run_workflow_once(self.store, run_id=run.run_id)

        self.assertEqual(result.run_status, WorkflowRunStatus.FAILED)
        self.assertEqual(self.store.get_run(run.run_id).status, WorkflowRunStatus.FAILED)

    def test_retryable_failed_step_records_next_attempt(self) -> None:
        run = self._admit(_retryable_step_definition())
        self.store.record_attempt(_attempt(run.run_id, "verify", WorkflowStepStatus.FAILED))

        result = run_workflow_once(self.store, run_id=run.run_id)

        attempts = self.store.list_attempts(run.run_id)
        self.assertEqual(result.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(result.ready_before, ("verify",))
        self.assertEqual(result.recorded_steps[0].attempt_id, "run-1-verify-2")
        self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.WAITING_EXTERNAL)
        self.assertIn("retry 2", result.recorded_steps[0].reason)
        self.assertEqual(len(attempts), 2)

    def test_registered_executor_can_complete_ready_step(self) -> None:
        run = self._admit(_single_step_definition())
        executors = WorkflowExecutorRegistry()
        executors.register(
            WorkflowStepKind.VERIFICATION,
            lambda _context: WorkflowExecutionResult(status=WorkflowStepStatus.SUCCEEDED, reason="verified by test executor"),
        )

        result = run_workflow_once(self.store, run_id=run.run_id, executors=executors)

        attempts = self.store.list_attempts(run.run_id)
        self.assertEqual(result.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(result.recorded_steps[0].reason, "verified by test executor")
        self.assertEqual(attempts[0].status, WorkflowStepStatus.SUCCEEDED)

    def _admit(self, definition: WorkflowDefinition) -> WorkflowRun:
        self.store.record_definition(definition)
        return self.store.admit_run(
            WorkflowRun(
                run_id="run-1",
                workflow_id=definition.workflow_id,
                definition_hash=definition.definition_hash,
                input_hash=workflow_input_hash({}),
            )
        )


def _definition_with_join() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf-runner",
        version=1,
        input_schema={},
        output_schema={},
        steps=(
            WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),
            WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT, depends_on=("research",)),
            WorkflowStep(step_id="join", kind=WorkflowStepKind.JOIN, depends_on=("research", "plan"), join_policy=JoinPolicy(mode=JoinMode.ALL_SUCCESS)),
        ),
    )


def _single_step_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf-single",
        version=1,
        input_schema={},
        output_schema={},
        steps=(WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION),),
    )


def _retryable_step_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf-retry",
        version=1,
        input_schema={},
        output_schema={},
        steps=(WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION, max_attempts=2),),
    )


def _attempt(run_id: str, step_id: str, status: WorkflowStepStatus):
    from forgeweave.automation import StepAttempt

    return StepAttempt(
        attempt_id=f"{run_id}-{step_id}-seed",
        run_id=run_id,
        step_id=step_id,
        idempotency_key=f"{run_id}:{step_id}:seed",
        status=status,
    )


if __name__ == "__main__":
    unittest.main()
