from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    JoinMode,
    JoinPolicy,
    StepAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    WorkflowStoreError,
    workflow_input_hash,
)


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(self.root / "workflows.db")
        self.addCleanup(self.store.close)
        self.definition = _definition()

    def test_records_definition_and_admits_run_bound_to_hashes(self) -> None:
        self.store.record_definition(self.definition)
        run = WorkflowRun(
            run_id="run-1",
            workflow_id=self.definition.workflow_id,
            definition_hash=self.definition.definition_hash,
            input_hash=workflow_input_hash({"issue": 1}),
        )

        admitted = self.store.admit_run(run)

        self.assertEqual(self.store.get_definition(self.definition.definition_hash).definition_hash, self.definition.definition_hash)
        self.assertEqual(admitted.status, WorkflowRunStatus.PENDING)
        self.assertEqual(self.store.get_run("run-1"), run)

    def test_run_requires_recorded_definition(self) -> None:
        run = WorkflowRun(run_id="run-1", workflow_id="wf", definition_hash="sha256:missing", input_hash="sha256:input")

        with self.assertRaises(KeyError):
            self.store.admit_run(run)

    def test_lists_definitions_and_runs_for_inspection(self) -> None:
        run = self._admit_run()

        definitions = self.store.list_definitions()
        all_runs = self.store.list_runs()
        filtered_runs = self.store.list_runs(workflow_id=self.definition.workflow_id)
        missing_runs = self.store.list_runs(workflow_id="missing")

        self.assertEqual(definitions, (self.definition,))
        self.assertEqual(all_runs, (run,))
        self.assertEqual(filtered_runs, (run,))
        self.assertEqual(missing_runs, ())

    def test_updates_run_status_without_changing_bindings(self) -> None:
        run = self._admit_run()

        updated = self.store.update_run_status(run.run_id, WorkflowRunStatus.RUNNING)

        self.assertEqual(updated.status, WorkflowRunStatus.RUNNING)
        self.assertEqual(updated.definition_hash, run.definition_hash)
        self.assertEqual(updated.input_hash, run.input_hash)

    def test_records_step_attempt_idempotently(self) -> None:
        run = self._admit_run()
        attempt = StepAttempt(
            attempt_id="attempt-1",
            run_id=run.run_id,
            step_id="research",
            idempotency_key="run-1:research:1",
            lease_token="lease-1",
            status=WorkflowStepStatus.RUNNING,
        )

        first = self.store.record_attempt(attempt)
        second = self.store.record_attempt(attempt)

        self.assertEqual(first, attempt)
        self.assertEqual(second, attempt)
        self.assertEqual(self.store.list_attempts(run.run_id), (attempt,))

    def test_rejects_conflicting_idempotency_payload(self) -> None:
        run = self._admit_run()
        first = StepAttempt(attempt_id="attempt-1", run_id=run.run_id, step_id="research", idempotency_key="same-key")
        second = StepAttempt(attempt_id="attempt-2", run_id=run.run_id, step_id="plan", idempotency_key="same-key")
        self.store.record_attempt(first)

        with self.assertRaises(WorkflowStoreError) as raised:
            self.store.record_attempt(second)

        self.assertEqual(raised.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_updates_attempt_status_preserving_lease_and_key(self) -> None:
        run = self._admit_run()
        attempt = StepAttempt(attempt_id="attempt-1", run_id=run.run_id, step_id="research", idempotency_key="key", lease_token="lease")
        self.store.record_attempt(attempt)

        updated = self.store.update_attempt_status("attempt-1", WorkflowStepStatus.SUCCEEDED)

        self.assertEqual(updated.status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(updated.lease_token, "lease")
        self.assertEqual(updated.idempotency_key, "key")

    def _admit_run(self) -> WorkflowRun:
        self.store.record_definition(self.definition)
        run = WorkflowRun(
            run_id="run-1",
            workflow_id=self.definition.workflow_id,
            definition_hash=self.definition.definition_hash,
            input_hash=workflow_input_hash({"issue": 1}),
        )
        return self.store.admit_run(run)


def _definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf",
        version=1,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        steps=(
            WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),
            WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT, depends_on=("research",)),
            WorkflowStep(step_id="join", kind=WorkflowStepKind.JOIN, depends_on=("research", "plan"), join_policy=JoinPolicy(mode=JoinMode.ALL_SETTLED)),
        ),
    )


if __name__ == "__main__":
    unittest.main()
