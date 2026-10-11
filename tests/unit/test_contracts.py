from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from pydantic import ValidationError

from forgeweave.contracts import (
    AcceptanceCriterion,
    AcceptanceSpec,
    ApprovalGrant,
    ApprovalScope,
    BudgetLedger,
    BudgetReservation,
    ConstraintLedger,
    ConstraintStatus,
    ContextManifest,
    ContextSpan,
    ExecutionProfile,
    FidelityMode,
    IsolationClaim,
    SummaryRecord,
    ToolExecution,
    ToolExecutionState,
    VerificationRun,
)


class OperationalContractTests(unittest.TestCase):
    def test_constraint_ledger_rejects_duplicate_active_requirements(self) -> None:
        ledger = ConstraintLedger(
            task_id="task-1",
            constraints=[
                AcceptanceCriterion(
                    criterion_id="must-test",
                    text="Run the focused test.",
                    origin="user",
                    authority="task",
                    validator="python -m unittest tests.unit.test_contracts",
                )
            ],
        )
        self.assertEqual(ledger.active_ids, frozenset({"must-test"}))

        with self.assertRaises(ValidationError):
            ConstraintLedger(
                task_id="task-1",
                constraints=[
                    AcceptanceCriterion(
                        criterion_id="same",
                        text="One",
                        origin="user",
                        authority="task",
                        validator="manual",
                    ),
                    AcceptanceCriterion(
                        criterion_id="same",
                        text="Two",
                        origin="user",
                        authority="task",
                        validator="manual",
                    ),
                ],
            )

    def test_summary_record_must_cover_protected_constraints(self) -> None:
        with self.assertRaises(ValidationError):
            SummaryRecord(
                summary_id="sum-1",
                task_id="task-1",
                source_event_range=("evt-1", "evt-9"),
                cited_decisions=["adr-000"],
                unresolved_work=[],
                changed_file_hashes={"src/a.py": "sha256:abc"},
                verification_fingerprint="sha256:verify",
                constraint_ledger_hash="sha256:ledger",
                protected_constraint_ids=["must-test"],
                covered_constraint_ids=[],
            )

    def test_context_manifest_declares_ordered_spans_and_fidelity(self) -> None:
        manifest = ContextManifest(
            request_id="req-1",
            task_id="task-1",
            attempt_id="attempt-1",
            provider="fake",
            model="scripted",
            adapter_version="v1",
            effective_policy_hash="sha256:policy",
            effective_config_hash="sha256:config",
            workspace_revision="abc123",
            catalog_version="tools-v1",
            token_estimate=120,
            fidelity=FidelityMode.REDACTED,
            spans=[
                ContextSpan(
                    span_id="span-1",
                    source="AGENTS.md",
                    source_hash="sha256:agents",
                    authority="repository",
                    sensitivity="normal",
                    token_estimate=30,
                ),
                ContextSpan(
                    span_id="span-2",
                    source="todo.md",
                    source_hash="sha256:todo",
                    authority="repository",
                    sensitivity="normal",
                    token_estimate=90,
                ),
            ],
        )

        self.assertEqual(manifest.ordered_span_ids, ("span-1", "span-2"))

    def test_approval_grant_consumption_is_action_bound(self) -> None:
        grant = ApprovalGrant(
            grant_id="grant-1",
            task_id="task-1",
            attempt_id="attempt-1",
            tool_name="shell",
            tool_schema_version="v1",
            catalog_version="tools-v1",
            argument_hash="sha256:args",
            effect_hash="sha256:effects",
            workspace_precondition_hash="sha256:workspace",
            policy_revision="policy-1",
            human_actor="user",
            scope=ApprovalScope.ONE_ACTION,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        self.assertTrue(
            grant.matches(
                tool_name="shell",
                argument_hash="sha256:args",
                effect_hash="sha256:effects",
                workspace_precondition_hash="sha256:workspace",
                policy_revision="policy-1",
                now=datetime.now(UTC),
            )
        )
        consumed = grant.consume()
        self.assertIsNotNone(consumed.consumed_at)
        self.assertFalse(
            consumed.matches(
                tool_name="shell",
                argument_hash="sha256:args",
                effect_hash="sha256:effects",
                workspace_precondition_hash="sha256:workspace",
                policy_revision="policy-1",
                now=datetime.now(UTC),
            )
        )

    def test_tool_execution_outcome_unknown_requires_reconciliation_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            ToolExecution(
                execution_id="exec-1",
                task_id="task-1",
                attempt_id="attempt-1",
                tool_name="shell",
                state=ToolExecutionState.OUTCOME_UNKNOWN,
                effect_hash="sha256:effects",
                idempotency_key="idem-1",
            )

    def test_budget_ledger_keeps_conservative_missing_usage_reservation(self) -> None:
        ledger = BudgetLedger(
            task_id="task-1",
            currency="USD",
            price_source_version="prices-v1",
            reservations=[
                BudgetReservation(
                    reservation_id="res-1",
                    purpose="model-call",
                    estimated_tokens=1000,
                    estimated_cost=0.25,
                )
            ],
        )

        self.assertEqual(ledger.remaining_reserved_cost, 0.25)
        reconciled = ledger.reconcile("res-1", actual_tokens=None, actual_cost=None)
        self.assertEqual(reconciled.remaining_reserved_cost, 0.25)
        settled = reconciled.reconcile("res-1", actual_tokens=800, actual_cost=0.2)
        self.assertEqual(settled.remaining_reserved_cost, 0.0)

    def test_execution_profile_reports_independent_isolation_claims(self) -> None:
        profile = ExecutionProfile(
            profile_id="profile-1",
            filesystem=IsolationClaim(level="workspace-write", backend="git-worktree", measured=False),
            network=IsolationClaim(level="shared-egress", backend="host", measured=False),
            credentials=IsolationClaim(level="host-user", backend="os", measured=False),
            process_tree=IsolationClaim(level="job-object", backend="windows-job-object", measured=True),
            resources=IsolationClaim(level="best-effort", backend="process", measured=False),
        )

        self.assertFalse(profile.has_measured_restricted_execution)

    def test_verification_run_fingerprint_includes_untracked_inputs(self) -> None:
        spec = AcceptanceSpec(
            spec_id="spec-1",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="unit-tests",
                    text="Focused unit tests pass.",
                    origin="todo.md",
                    authority="repository",
                    validator="python -m unittest tests.unit.test_contracts",
                )
            ],
        )
        run = VerificationRun(
            run_id="verify-1",
            task_id="task-1",
            criterion_ids=["unit-tests"],
            command_argv=("python", "-m", "unittest", "tests.unit.test_contracts"),
            cwd="C:/repo",
            environment_profile_hash="sha256:env",
            verifier_version="unittest",
            config_hash="sha256:config",
            workspace_fingerprint="sha256:tracked",
            untracked_input_hashes={"generated.txt": "sha256:input"},
            exit_code=0,
            output_artifact_id="artifact-1",
        )
        without_untracked = run.model_copy(update={"untracked_input_hashes": {}})

        self.assertEqual(spec.required_ids, frozenset({"unit-tests"}))
        self.assertNotEqual(run.whole_input_fingerprint, without_untracked.whole_input_fingerprint)


if __name__ == "__main__":
    unittest.main()
