from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.core import complete_from_selected_verification
from forgeweave.verify import run_selected_verification


class CompletionTests(unittest.TestCase):
    def test_completion_report_uses_selected_verification_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            selected = run_selected_verification(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        report = complete_from_selected_verification(
            task_id="task-1",
            selected_run=selected,
            modified_files=("src/app.py",),
            artifact_links=("artifact://task-1/patch",),
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.modified_files, ("src/app.py",))
        self.assertEqual(len(report.checks), 1)
        self.assertEqual(report.failed_checks, ())
        self.assertEqual(report.artifact_links, ("artifact://task-1/patch",))

    def test_completion_report_keeps_failed_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_fail(self):\n        self.assertEqual(1, 2)\n",
                encoding="utf-8",
            )
            selected = run_selected_verification(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        report = complete_from_selected_verification(task_id="task-1", selected_run=selected)

        self.assertFalse(report.passed)
        self.assertEqual(len(report.failed_checks), 1)
        self.assertEqual(report.failed_checks[0].outcome, "failed")

    def test_completion_report_adds_risk_when_no_checks_ran(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = run_selected_verification(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        report = complete_from_selected_verification(task_id="task-1", selected_run=selected)

        self.assertFalse(report.passed)
        self.assertIn("no verification commands were selected or run", report.risks)

    def test_completion_rejects_task_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = run_selected_verification(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        with self.assertRaises(ValueError):
            complete_from_selected_verification(task_id="task-2", selected_run=selected)


if __name__ == "__main__":
    unittest.main()
