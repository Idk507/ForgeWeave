from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStore,
    WorkflowStoreError,
    require_run_bindings,
    workflow_input_hash,
)


class WorkflowBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)
        self.definition = WorkflowDefinition(
            workflow_id="wf-bind",
            version=1,
            input_schema={},
            output_schema={},
            steps=(WorkflowStep(step_id="step", kind=WorkflowStepKind.AGENT),),
        )
        self.store.record_definition(self.definition)
        self.run = self.store.admit_run(
            WorkflowRun(
                run_id="run-bind",
                workflow_id=self.definition.workflow_id,
                definition_hash=self.definition.definition_hash,
                input_hash=workflow_input_hash({"issue": 1}),
            )
        )

    def test_accepts_matching_definition_and_input_hashes(self) -> None:
        result = require_run_bindings(
            self.store,
            run_id=self.run.run_id,
            expected_definition_hash=self.definition.definition_hash,
            expected_input_hash=workflow_input_hash({"issue": 1}),
        )

        self.assertEqual(result.definition_hash, self.definition.definition_hash)
        self.assertEqual(result.input_hash, workflow_input_hash({"issue": 1}))

    def test_rejects_changed_definition_hash(self) -> None:
        with self.assertRaises(WorkflowStoreError) as raised:
            require_run_bindings(self.store, run_id=self.run.run_id, expected_definition_hash="sha256:changed")

        self.assertEqual(raised.exception.code, "DEFINITION_CHANGED")

    def test_rejects_changed_input_hash(self) -> None:
        with self.assertRaises(WorkflowStoreError) as raised:
            require_run_bindings(self.store, run_id=self.run.run_id, expected_input_hash=workflow_input_hash({"issue": 2}))

        self.assertEqual(raised.exception.code, "INPUT_CHANGED")


if __name__ == "__main__":
    unittest.main()
