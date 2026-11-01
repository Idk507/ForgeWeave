from __future__ import annotations

import unittest

from forgeweave.automation import (
    WorkflowStep,
    WorkflowStepKind,
    artifact_bindings_for_step,
    artifact_records_from_output,
    validate_artifact_bindings,
)


class WorkflowArtifactBindingTests(unittest.TestCase):
    def test_reads_string_and_object_artifact_bindings(self) -> None:
        step = WorkflowStep(
            step_id="implement",
            kind=WorkflowStepKind.AGENT,
            parameters={"artifacts": ["patch", {"name": "verification", "required": False}]},
        )

        bindings = artifact_bindings_for_step(step)

        self.assertEqual(bindings[0].name, "patch")
        self.assertTrue(bindings[0].required)
        self.assertEqual(bindings[1].name, "verification")
        self.assertFalse(bindings[1].required)

    def test_validates_required_artifacts_from_mapping_output(self) -> None:
        step = WorkflowStep(
            step_id="implement",
            kind=WorkflowStepKind.AGENT,
            parameters={"artifacts": ["patch"]},
        )

        result = validate_artifact_bindings(step, {"artifacts": {"patch": "artifact://patch-1"}})

        self.assertTrue(result.valid)
        self.assertEqual(result.required, ("patch",))
        self.assertEqual(result.present, ("patch",))

    def test_reports_missing_required_artifacts(self) -> None:
        step = WorkflowStep(
            step_id="implement",
            kind=WorkflowStepKind.AGENT,
            parameters={"artifacts": ["patch", "verification"]},
        )

        result = validate_artifact_bindings(step, {"artifacts": [{"name": "patch", "uri": "artifact://patch-1"}]})

        self.assertFalse(result.valid)
        self.assertEqual(result.missing, ("verification",))
        self.assertIn("verification", result.reason)


    def test_extracts_artifact_records_from_executor_output(self) -> None:
        records = artifact_records_from_output(
            run_id="run-1",
            step_id="implement",
            attempt_id="attempt-1",
            output={"artifacts": {"patch": {"uri": "artifact://patch-1", "sha256": "abc"}}},
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].run_id, "run-1")
        self.assertEqual(records[0].step_id, "implement")
        self.assertEqual(records[0].attempt_id, "attempt-1")
        self.assertEqual(records[0].name, "patch")
        self.assertEqual(records[0].uri, "artifact://patch-1")
        self.assertEqual(records[0].metadata, {"sha256": "abc"})
        self.assertTrue(records[0].artifact_id.startswith("workflow-artifact:"))

    def test_rejects_malformed_artifact_bindings(self) -> None:
        step = WorkflowStep(step_id="bad", kind=WorkflowStepKind.AGENT, parameters={"artifacts": [{"required": True}]})

        with self.assertRaises(ValueError):
            artifact_bindings_for_step(step)


if __name__ == "__main__":
    unittest.main()
