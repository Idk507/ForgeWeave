"""Analyzer regression gate decisions for repair-loop integration."""

from __future__ import annotations

from dataclasses import dataclass

from forgeweave.verify.analyzers import AnalyzerResult
from forgeweave.verify.regression import Finding, RetryBudget, regressions
from forgeweave.verify.snapshots import GitSnapshot


@dataclass(frozen=True)
class RegressionGateDecision:
    """Decision after comparing before/after analyzer findings."""

    outcome: str
    regressions: tuple[Finding, ...]
    infrastructure_errors: tuple[str, ...]
    attempts_used: int
    retry_exhausted: bool
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None

    @property
    def should_block(self) -> bool:
        """Return true when the change must not pass verification."""

        return self.outcome != "passed"


class RegressionGate:
    """Apply baseline-vs-after analyzer results to a retry budget."""

    def __init__(self, *, retry_budget: RetryBudget) -> None:
        self.retry_budget = retry_budget

    def evaluate(
        self,
        *,
        before: tuple[AnalyzerResult, ...],
        after: tuple[AnalyzerResult, ...],
        before_snapshot: GitSnapshot | None = None,
        after_snapshot: GitSnapshot | None = None,
    ) -> RegressionGateDecision:
        """Return pass, code-regression or infrastructure-failure decision."""

        infrastructure_errors = tuple(
            _infrastructure_error(result)
            for result in (*before, *after)
            if result.is_infrastructure_failure
        )
        if infrastructure_errors:
            self.retry_budget.record_infrastructure_failure()
            return RegressionGateDecision(
                outcome="infrastructure-failure",
                regressions=(),
                infrastructure_errors=infrastructure_errors,
                attempts_used=self.retry_budget.failed,
                retry_exhausted=self.retry_budget.exhausted,
                before_snapshot_id=_snapshot_id(before_snapshot),
                after_snapshot_id=_snapshot_id(after_snapshot),
            )

        found = tuple(regressions(_findings(before), _findings(after)))
        if found:
            attempts = self.retry_budget.record_code_failure()
            return RegressionGateDecision(
                outcome="code-regression",
                regressions=found,
                infrastructure_errors=(),
                attempts_used=attempts,
                retry_exhausted=self.retry_budget.exhausted,
                before_snapshot_id=_snapshot_id(before_snapshot),
                after_snapshot_id=_snapshot_id(after_snapshot),
            )

        self.retry_budget.record_pass()
        return RegressionGateDecision(
            outcome="passed",
            regressions=(),
            infrastructure_errors=(),
            attempts_used=self.retry_budget.failed,
            retry_exhausted=self.retry_budget.exhausted,
            before_snapshot_id=_snapshot_id(before_snapshot),
            after_snapshot_id=_snapshot_id(after_snapshot),
        )


def _findings(results: tuple[AnalyzerResult, ...]) -> tuple[Finding, ...]:
    return tuple(finding for result in results for finding in result.findings)


def _infrastructure_error(result: AnalyzerResult) -> str:
    reason = result.infrastructure_error or "timeout" if result.timed_out else result.infrastructure_error
    if reason is None:
        reason = "unknown-infrastructure-failure"
    return f"{result.analyzer}: {reason}"


def _snapshot_id(snapshot: GitSnapshot | None) -> str | None:
    return None if snapshot is None else snapshot.snapshot_id
