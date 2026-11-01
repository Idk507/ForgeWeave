from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    StepAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    WorkflowStoreError,
    assert_step_lease,
    require_step_lease,
    update_attempt_status_with_lease,
    workflow_input_hash,
)


class WorkflowLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)
        definition = WorkflowDefinition(
            workflow_id="wf-lease",
            version=1,
            input_schema={},
            output_schema={},
            steps=(WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION),),
        )
        self.store.record_definition(definition)
        self.run = self.store.admit_run(
            WorkflowRun(
                run_id="run-lease",
                workflow_id=definition.workflow_id,
                definition_hash=definition.definition_hash,
                input_hash=workflow_input_hash({}),
            )
        )

    def test_matching_lease_token_allows_attempt_update(self) -> None:
        self._record_attempt("lease-1")

        result = require_step_lease(self.store, attempt_id="attempt-1", lease_token="lease-1")
        updated = update_attempt_status_with_lease(
            self.store,
            attempt_id="attempt-1",
            status=WorkflowStepStatus.SUCCEEDED,
            lease_token="lease-1",
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.code, "LEASE_ACTIVE")
        self.assertEqual(updated.status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(updated.lease_token, "lease-1")

    def test_mismatched_lease_token_denies_stale_worker(self) -> None:
        self._record_attempt("lease-1")

        result = require_step_lease(self.store, attempt_id="attempt-1", lease_token="lease-2")

        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "LEASE_TOKEN_MISMATCH")
        with self.assertRaises(WorkflowStoreError) as raised:
            assert_step_lease(self.store, attempt_id="attempt-1", lease_token="lease-2")
        self.assertEqual(raised.exception.code, "LEASE_TOKEN_MISMATCH")
        self.assertEqual(self.store.get_attempt("attempt-1").status, WorkflowStepStatus.WAITING_EXTERNAL)

    def test_missing_recorded_lease_token_denies_fenced_update(self) -> None:
        self._record_attempt(None)

        result = require_step_lease(self.store, attempt_id="attempt-1", lease_token="lease-1")

        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "LEASE_NOT_RECORDED")
        with self.assertRaises(WorkflowStoreError):
            update_attempt_status_with_lease(
                self.store,
                attempt_id="attempt-1",
                status=WorkflowStepStatus.SUCCEEDED,
                lease_token="lease-1",
            )

    def test_unknown_attempt_denies_lease_check(self) -> None:
        result = require_step_lease(self.store, attempt_id="missing", lease_token="lease-1")

        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "ATTEMPT_NOT_FOUND")

    def test_blank_inputs_return_structured_denials(self) -> None:
        missing_attempt = require_step_lease(self.store, attempt_id=" ", lease_token="lease-1")
        missing_token = require_step_lease(self.store, attempt_id="attempt-1", lease_token=" ")

        self.assertEqual(missing_attempt.code, "MISSING_ATTEMPT_ID")
        self.assertEqual(missing_token.code, "MISSING_LEASE_TOKEN")


    def test_matching_worker_id_allows_worker_owned_attempt_update(self) -> None:
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-worker",
                run_id=self.run.run_id,
                step_id="verify",
                idempotency_key="run-lease:verify:worker",
                lease_token="lease-worker",
                worker_id="worker-1",
                status=WorkflowStepStatus.WAITING_EXTERNAL,
            )
        )

        result = require_step_lease(
            self.store,
            attempt_id="attempt-worker",
            lease_token="lease-worker",
            worker_id="worker-1",
        )
        updated = update_attempt_status_with_lease(
            self.store,
            attempt_id="attempt-worker",
            status=WorkflowStepStatus.SUCCEEDED,
            lease_token="lease-worker",
            worker_id="worker-1",
        )

        self.assertTrue(result.allowed)
        self.assertEqual(updated.worker_id, "worker-1")
        self.assertEqual(updated.status, WorkflowStepStatus.SUCCEEDED)

    def test_mismatched_worker_id_denies_stale_worker_owner(self) -> None:
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-worker",
                run_id=self.run.run_id,
                step_id="verify",
                idempotency_key="run-lease:verify:worker",
                lease_token="lease-worker",
                worker_id="worker-1",
                status=WorkflowStepStatus.WAITING_EXTERNAL,
            )
        )

        result = require_step_lease(
            self.store,
            attempt_id="attempt-worker",
            lease_token="lease-worker",
            worker_id="worker-2",
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "WORKER_ID_MISMATCH")

    def _record_attempt(self, lease_token: str | None) -> None:
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-1",
                run_id=self.run.run_id,
                step_id="verify",
                idempotency_key="run-lease:verify:1",
                lease_token=lease_token,
                status=WorkflowStepStatus.WAITING_EXTERNAL,
            )
        )


if __name__ == "__main__":
    unittest.main()
