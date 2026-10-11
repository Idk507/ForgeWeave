from __future__ import annotations

import unittest

from forgeweave.verify import Finding, RetryBudget, regressions


def stmt(value: float, file: str = "a.py", symbol: str = "P.process") -> Finding:
    return Finding(file, "ruff", "PLR0915", symbol=symbol, value=value, limit=50)


class RegressionTests(unittest.TestCase):
    def test_legacy_debt_does_not_block(self) -> None:
        self.assertEqual(regressions([stmt(63)], [stmt(63)]), [])

    def test_worsened_metric_blocks(self) -> None:
        self.assertEqual(len(regressions([stmt(63)], [stmt(70)])), 1)

    def test_reduced_excess_is_allowed(self) -> None:
        self.assertEqual(regressions([stmt(82)], [stmt(81)]), [])

    def test_new_over_limit_function_blocks(self) -> None:
        self.assertEqual(len(regressions([], [stmt(51)])), 1)

    def test_under_limit_never_blocks(self) -> None:
        self.assertEqual(regressions([], [stmt(50)]), [])

    def test_moved_function_is_not_a_regression(self) -> None:
        old = Finding("a.py", "ruff", "PLR0915", symbol="f", line=10, value=63, limit=50)
        new = Finding("a.py", "ruff", "PLR0915", symbol="f", line=40, value=63, limit=50)
        self.assertEqual(regressions([old], [new]), [])

    def test_extra_occurrence_of_existing_diagnostic_blocks(self) -> None:
        f401 = Finding("a.py", "ruff", "F401", message="os unused")
        self.assertEqual(regressions([f401], [f401]), [])
        self.assertEqual(len(regressions([f401], [f401, f401])), 1)

    def test_debt_in_one_file_cannot_offset_another(self) -> None:
        old = [stmt(80, file="a.py")]
        new = [stmt(60, file="a.py"), stmt(55, file="b.py")]
        self.assertEqual([f.file for f in regressions(old, new)], ["b.py"])


class RetryBudgetTests(unittest.TestCase):
    def test_exhausts_after_max_failures_and_pass_resets(self) -> None:
        b = RetryBudget(3)
        b.record_code_failure()
        b.record_code_failure()
        b.record_pass()
        self.assertEqual(b.failed, 0)
        for _ in range(5):
            b.record_code_failure()
        self.assertTrue(b.exhausted)
        self.assertEqual(b.failed, 3)

    def test_infrastructure_failure_does_not_consume(self) -> None:
        b = RetryBudget(3)
        b.record_infrastructure_failure()
        self.assertEqual(b.failed, 0)

    def test_rejects_invalid_limits(self) -> None:
        for bad in (0, True, 1.5):
            with self.assertRaises(ValueError):
                RetryBudget(bad)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
