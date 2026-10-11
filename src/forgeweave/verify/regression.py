"""Baseline-vs-after regression policy and retry budget.

Design adopted from codex-harness (judge the change, not legacy debt); implemented natively.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    """Normalized analyzer output. `value`/`limit` are set for numeric metrics only."""

    file: str
    analyzer: str
    rule: str
    message: str = ""
    symbol: str | None = None
    line: int = 0
    value: float | None = None
    limit: float | None = None

    @property
    def is_numeric(self) -> bool:
        return self.value is not None and self.limit is not None


def regressions(before: Iterable[Finding], after: Iterable[Finding]) -> list[Finding]:
    """Return findings in `after` that are new or worse than in `before`.

    Numeric metrics are keyed by file+analyzer+rule+symbol and block only when over the limit and
    new or increased. Other diagnostics are keyed by file+analyzer+rule+message and block per extra
    occurrence. Debt in one file or analyzer never offsets a violation in another.
    """
    before = list(before)
    after = list(after)
    found: list[Finding] = []

    old_metrics = {(f.file, f.analyzer, f.rule, f.symbol): f for f in before if f.is_numeric}
    for f in after:
        if not f.is_numeric or f.value <= f.limit:  # type: ignore[operator]
            continue
        prev = old_metrics.get((f.file, f.analyzer, f.rule, f.symbol))
        if prev is None or f.value > prev.value:  # type: ignore[operator]
            found.append(f)

    old_counts = Counter((f.file, f.analyzer, f.rule, f.message) for f in before if not f.is_numeric)
    seen: Counter[tuple[str, str, str, str]] = Counter()
    for f in after:
        if f.is_numeric:
            continue
        key = (f.file, f.analyzer, f.rule, f.message)
        seen[key] += 1
        if seen[key] > old_counts[key]:
            found.append(f)
    return found


class RetryBudget:
    """Consecutive-failure budget for one task attempt.

    Code failures consume it, a pass resets it, and infrastructure failures (analyzer crash,
    timeout, bad config) fail closed without consuming it.
    """

    def __init__(self, max_attempts: int = 3) -> None:
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be an integer >= 1")
        self.max_attempts = max_attempts
        self.failed = 0

    @property
    def exhausted(self) -> bool:
        return self.failed >= self.max_attempts

    def record_code_failure(self) -> int:
        if not self.exhausted:
            self.failed += 1
        return self.failed

    def record_pass(self) -> None:
        self.failed = 0

    def record_infrastructure_failure(self) -> None:
        """Blocks the change but leaves the budget untouched."""
