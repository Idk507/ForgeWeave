from __future__ import annotations

from pathlib import Path
import unittest

from forgeweave.verify import AnalyzerResult, Finding, GitSnapshot, RegressionGate, RetryBudget


class RegressionGateTests(unittest.TestCase):
    def test_pass_resets_retry_budget_and_preserves_snapshot_ids(self) -> None:
        budget = RetryBudget(2)
        budget.record_code_failure()
        gate = RegressionGate(retry_budget=budget)

        decision = gate.evaluate(
            before=(_result(findings=(Finding("a.py", "ruff", "F401", message="unused"),)),),
            after=(_result(findings=(Finding("a.py", "ruff", "F401", message="unused"),)),),
            before_snapshot=_snapshot("before"),
            after_snapshot=_snapshot("after"),
        )

        self.assertEqual(decision.outcome, "passed")
        self.assertFalse(decision.should_block)
        self.assertEqual(decision.attempts_used, 0)
        self.assertEqual(budget.failed, 0)
        self.assertEqual(decision.before_snapshot_id, "before")
        self.assertEqual(decision.after_snapshot_id, "after")

    def test_code_regression_consumes_retry_budget(self) -> None:
        budget = RetryBudget(2)
        gate = RegressionGate(retry_budget=budget)

        decision = gate.evaluate(
            before=(),
            after=(_result(findings=(Finding("a.py", "ruff", "F401", message="unused"),)),),
        )

        self.assertEqual(decision.outcome, "code-regression")
        self.assertTrue(decision.should_block)
        self.assertEqual(decision.attempts_used, 1)
        self.assertFalse(decision.retry_exhausted)
        self.assertEqual(len(decision.regressions), 1)
        self.assertEqual(budget.failed, 1)

    def test_code_regression_reports_retry_exhaustion(self) -> None:
        budget = RetryBudget(1)
        gate = RegressionGate(retry_budget=budget)

        decision = gate.evaluate(
            before=(),
            after=(_result(findings=(Finding("a.py", "ruff", "F401", message="unused"),)),),
        )

        self.assertEqual(decision.outcome, "code-regression")
        self.assertTrue(decision.retry_exhausted)
        self.assertEqual(decision.attempts_used, 1)

    def test_infrastructure_failure_blocks_without_consuming_retry_budget(self) -> None:
        budget = RetryBudget(2)
        gate = RegressionGate(retry_budget=budget)

        decision = gate.evaluate(
            before=(),
            after=(
                AnalyzerResult(
                    analyzer="ruff",
                    command_argv=("ruff", "check", "a.py"),
                    cwd="C:/repo",
                    exit_code=None,
                    infrastructure_error="invalid-json",
                ),
            ),
        )

        self.assertEqual(decision.outcome, "infrastructure-failure")
        self.assertTrue(decision.should_block)
        self.assertEqual(decision.infrastructure_errors, ("ruff: invalid-json",))
        self.assertEqual(decision.attempts_used, 0)
        self.assertEqual(budget.failed, 0)


def _result(*, findings: tuple[Finding, ...]) -> AnalyzerResult:
    return AnalyzerResult(
        analyzer="ruff",
        command_argv=("ruff", "check", "a.py"),
        cwd="C:/repo",
        findings=findings,
        exit_code=1 if findings else 0,
    )


def _snapshot(snapshot_id: str) -> GitSnapshot:
    return GitSnapshot(
        snapshot_id=snapshot_id,
        repo_root=Path("C:/repo"),
        patch_path=Path("C:/snapshots") / f"{snapshot_id}.patch",
        base_commit="abc123",
        patch_hash="sha256:" + snapshot_id,
        changed_paths=("a.py",),
    )


if __name__ == "__main__":
    unittest.main()
