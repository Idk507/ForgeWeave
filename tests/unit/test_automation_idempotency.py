from __future__ import annotations

import unittest

from forgeweave.automation import workflow_attempt_identity


class WorkflowIdempotencyTests(unittest.TestCase):
    def test_attempt_identity_is_deterministic(self) -> None:
        first = workflow_attempt_identity(run_id="run-1", step_id="implement", attempt_number=2)
        second = workflow_attempt_identity(run_id="run-1", step_id="implement", attempt_number=2)

        self.assertEqual(first, second)
        self.assertEqual(first.attempt_id, "run-1-implement-2")
        self.assertTrue(first.idempotency_key.startswith("workflow-step:"))

    def test_attempt_identity_rejects_bad_inputs(self) -> None:
        with self.assertRaises(ValueError):
            workflow_attempt_identity(run_id=" ", step_id="implement", attempt_number=1)
        with self.assertRaises(ValueError):
            workflow_attempt_identity(run_id="run-1", step_id="implement", attempt_number=0)


if __name__ == "__main__":
    unittest.main()
