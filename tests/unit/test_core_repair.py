from __future__ import annotations

import unittest

from forgeweave.contracts import VerificationRun
from forgeweave.core import RepairLoopController, RepairOrchestrator, StopReason
from forgeweave.verify import RepairGuard, VerificationResult


class RepairLoopControllerTests(unittest.TestCase):
    def test_passed_verification_resets_guard_and_stops_as_final_answer(self) -> None:
        guard = RepairGuard(max_repairs=2)
        guard.record_failure("sha256:before", ("unit",), "failed", 1)
        controller = RepairLoopController(guard=guard)

        decision = controller.after_verification(_result(outcome="passed", exit_code=0))
        after_reset = guard.record_failure("sha256:before", ("unit",), "failed", 1)

        self.assertEqual(decision.reason, StopReason.FINAL_ANSWER)
        self.assertTrue(decision.should_stop)
        self.assertEqual(decision.details["verification_outcome"], "passed")
        self.assertFalse(after_reset.should_stop)

    def test_failed_verification_continues_until_guard_stops(self) -> None:
        controller = RepairLoopController(guard=RepairGuard(max_repairs=3))

        first = controller.after_verification(_result(outcome="failed", exit_code=1))
        second = controller.after_verification(_result(outcome="failed", exit_code=1))

        self.assertEqual(first.reason, StopReason.CONTINUE)
        self.assertFalse(first.should_stop)
        self.assertEqual(first.details["observed_failures"], 1)
        self.assertEqual(second.reason, StopReason.FAILED)
        self.assertTrue(second.should_stop)
        self.assertEqual(second.details["repair_stop_reason"], "repeated-identical-failure")

    def test_global_repair_cap_maps_to_failed_stop_decision(self) -> None:
        controller = RepairLoopController(guard=RepairGuard(max_repairs=2))

        controller.after_verification(
            _result(outcome="failed", exit_code=1, fingerprint="sha256:first", criteria=("a",))
        )
        decision = controller.after_verification(
            _result(outcome="failed", exit_code=2, fingerprint="sha256:second", criteria=("b",))
        )

        self.assertEqual(decision.reason, StopReason.FAILED)
        self.assertTrue(decision.should_stop)
        self.assertEqual(decision.details["repair_stop_reason"], "repair-budget-exhausted")
        self.assertEqual(decision.details["observed_failures"], 2)

    def test_inconclusive_verification_uses_repair_guard(self) -> None:
        controller = RepairLoopController(guard=RepairGuard(max_repairs=1))

        decision = controller.after_verification(_result(outcome="inconclusive", exit_code=None))

        self.assertEqual(decision.reason, StopReason.FAILED)
        self.assertEqual(decision.details["verification_outcome"], "inconclusive")
        self.assertEqual(decision.details["repair_stop_reason"], "repair-budget-exhausted")


class RepairOrchestratorTests(unittest.TestCase):
    def test_verifies_repairs_then_stops_on_pass(self) -> None:
        controller = RepairLoopController(guard=RepairGuard(max_repairs=2))
        orchestrator = RepairOrchestrator(controller=controller)
        verification_results = iter([
            _result(outcome="failed", exit_code=1, run_id="verify-1"),
            _result(outcome="passed", exit_code=0, run_id="verify-2"),
        ])
        repair_calls: list[tuple[str, StopReason]] = []

        result = orchestrator.run(
            verify=lambda: next(verification_results),
            repair=lambda verification, decision: repair_calls.append(
                (verification.run.run_id, decision.reason)
            ),
        )

        self.assertEqual(result.stop_decision.reason, StopReason.FINAL_ANSWER)
        self.assertEqual(result.repair_attempts, 1)
        self.assertEqual(
            [item.run.run_id for item in result.verification_results],
            ["verify-1", "verify-2"],
        )
        self.assertEqual(repair_calls, [("verify-1", StopReason.CONTINUE)])

    def test_stops_without_repair_when_guard_blocks_first_failure(self) -> None:
        controller = RepairLoopController(guard=RepairGuard(max_repairs=1))
        orchestrator = RepairOrchestrator(controller=controller)
        repair_calls: list[str] = []

        result = orchestrator.run(
            verify=lambda: _result(outcome="failed", exit_code=1),
            repair=lambda verification, decision: repair_calls.append(verification.run.run_id),
        )

        self.assertEqual(result.stop_decision.reason, StopReason.FAILED)
        self.assertEqual(result.stop_decision.details["repair_stop_reason"], "repair-budget-exhausted")
        self.assertEqual(result.repair_attempts, 0)
        self.assertEqual(repair_calls, [])

    def test_stops_after_one_repair_on_repeated_identical_failure(self) -> None:
        controller = RepairLoopController(guard=RepairGuard(max_repairs=3))
        orchestrator = RepairOrchestrator(controller=controller)
        verification_results = iter([
            _result(outcome="failed", exit_code=1, run_id="verify-1"),
            _result(outcome="failed", exit_code=1, run_id="verify-2"),
        ])
        repair_calls: list[str] = []

        result = orchestrator.run(
            verify=lambda: next(verification_results),
            repair=lambda verification, decision: repair_calls.append(verification.run.run_id),
        )

        self.assertEqual(result.stop_decision.reason, StopReason.FAILED)
        self.assertEqual(result.stop_decision.details["repair_stop_reason"], "repeated-identical-failure")
        self.assertEqual(result.repair_attempts, 1)
        self.assertEqual(repair_calls, ["verify-1"])


def _result(
    *,
    outcome: str,
    exit_code: int | None,
    fingerprint: str = "sha256:input",
    criteria: tuple[str, ...] = ("unit",),
    run_id: str = "verify-1",
) -> VerificationResult:
    run = VerificationRun(
        run_id=run_id,
        task_id="task-1",
        criterion_ids=criteria,
        command_argv=("python", "-m", "unittest"),
        cwd="C:/workspace",
        environment_profile_hash="sha256:env",
        verifier_version="unit",
        config_hash="sha256:config",
        workspace_fingerprint="sha256:workspace",
        untracked_input_hashes={},
        timeout_seconds=5,
        exit_code=exit_code,
        output_artifact_id="artifact-1",
        outcome=outcome,  # type: ignore[arg-type]
        whole_input_fingerprint=fingerprint,
    )
    return VerificationResult(run=run, stdout="", stderr="", timed_out=outcome == "inconclusive")


if __name__ == "__main__":
    unittest.main()
