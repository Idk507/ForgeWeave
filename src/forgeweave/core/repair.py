"""Core repair-loop stop integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from forgeweave.core.stop import StopDecision, StopReason
from forgeweave.verify import RepairGuard, VerificationResult


@dataclass
class RepairLoopController:
    """Convert verification outcomes and repair guard state into stop decisions."""

    guard: RepairGuard

    def after_verification(self, result: VerificationResult) -> StopDecision:
        """Return the next loop decision after one verification result."""

        run = result.run
        details = {
            "verification_run_id": run.run_id,
            "verification_outcome": run.outcome,
            "criterion_ids": list(run.criterion_ids),
            "output_artifact_id": run.output_artifact_id,
        }
        if run.outcome == "passed":
            self.guard.record_pass()
            return StopDecision(StopReason.FINAL_ANSWER, True, details)

        repair_decision = self.guard.record_failure(
            whole_input_fingerprint=run.whole_input_fingerprint,
            criterion_ids=run.criterion_ids,
            outcome=run.outcome,
            exit_code=run.exit_code,
        )
        details.update(
            {
                "repair_fingerprint": repair_decision.fingerprint,
                "observed_failures": repair_decision.observed_failures,
            }
        )
        if repair_decision.should_stop:
            details["repair_stop_reason"] = repair_decision.reason
            return StopDecision(StopReason.FAILED, True, details)
        return StopDecision(StopReason.CONTINUE, False, details)


@dataclass(frozen=True)
class RepairRunResult:
    """Final outcome of a bounded verify/repair orchestration run."""

    stop_decision: StopDecision
    verification_results: tuple[VerificationResult, ...]
    repair_attempts: int


@dataclass
class RepairOrchestrator:
    """Run verification and repair attempts until the repair controller stops."""

    controller: RepairLoopController

    def run(
        self,
        *,
        verify: Callable[[], VerificationResult],
        repair: Callable[[VerificationResult, StopDecision], None],
    ) -> RepairRunResult:
        """Verify, repair retryable failures, and return the terminal stop decision."""

        results: list[VerificationResult] = []
        repair_attempts = 0
        while True:
            verification = verify()
            results.append(verification)
            decision = self.controller.after_verification(verification)
            if decision.should_stop:
                return RepairRunResult(
                    stop_decision=decision,
                    verification_results=tuple(results),
                    repair_attempts=repair_attempts,
                )
            repair(verification, decision)
            repair_attempts += 1
