from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    VerificationWorkflowExecutorConfig,
    WorkflowDefinition,
    WorkflowExecutionContext,
    WorkflowExecutorRegistry,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    execute_verification_step,
    register_verification_workflow_executor,
    run_workflow_once,
    workflow_input_hash,
)


class VerificationWorkflowExecutorTests(unittest.TestCase):
    def test_verification_step_succeeds_when_selected_checks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _passing_repo(Path(tmp) / "repo")
            output_dir = Path(tmp) / "artifacts"

            result = execute_verification_step(
                WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=_verification_step(), attempt_number=1),
                VerificationWorkflowExecutorConfig(repo_root=root, output_dir=output_dir, task_id="task-1"),
            )

        self.assertEqual(result.status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(result.reason, "verification passed")
        self.assertEqual(result.output["command_count"], 1)  # type: ignore[index]
        self.assertEqual(result.output["failed_count"], 0)  # type: ignore[index]

    def test_verification_step_fails_when_no_checks_are_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()

            result = execute_verification_step(
                WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=_verification_step(), attempt_number=1),
                VerificationWorkflowExecutorConfig(repo_root=root, output_dir=Path(tmp) / "artifacts", task_id="task-1"),
            )

        self.assertEqual(result.status, WorkflowStepStatus.FAILED)
        self.assertEqual(result.output["command_count"], 0)  # type: ignore[index]

    def test_registered_verification_executor_integrates_with_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _passing_repo(Path(tmp) / "repo")
            store = WorkflowStore.open(Path(tmp) / "workflows.db")
            try:
                definition = WorkflowDefinition(workflow_id="wf", version=1, input_schema={}, output_schema={}, steps=(_verification_step(),))
                store.record_definition(definition)
                run = store.admit_run(WorkflowRun(run_id="run-1", workflow_id="wf", definition_hash=definition.definition_hash, input_hash=workflow_input_hash({})))
                executors = WorkflowExecutorRegistry()
                register_verification_workflow_executor(executors, VerificationWorkflowExecutorConfig(repo_root=root, output_dir=Path(tmp) / "artifacts", task_id="task-1"))

                result = run_workflow_once(store, run_id=run.run_id, executors=executors)

                self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
                self.assertEqual(store.list_attempts(run.run_id)[0].status, WorkflowStepStatus.SUCCEEDED)
            finally:
                store.close()


def _verification_step() -> WorkflowStep:
    return WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION)


def _passing_repo(root: Path) -> Path:
    tests = root / "tests"
    tests.mkdir(parents=True)
    (tests / "test_sample.py").write_text(
        "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )
    return root


if __name__ == "__main__":
    unittest.main()
