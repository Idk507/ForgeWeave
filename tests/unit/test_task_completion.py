from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.core import complete_repository_task


class TaskCompletionTests(unittest.TestCase):
    def test_complete_repository_task_runs_selected_checks_and_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            result = complete_repository_task(
                task_id="task-1",
                repo_root=root,
                output_dir=root / ".fw-artifacts",
                modified_files=("src/app.py",),
                artifact_links=("artifact://task-1/diff",),
            )

            self.assertTrue(result.passed)
            self.assertTrue(result.selected_run.passed)
            self.assertTrue(result.report.passed)
            self.assertEqual(result.report.modified_files, ("src/app.py",))
            self.assertEqual(result.report.artifact_links, ("artifact://task-1/diff",))
            self.assertEqual(len(result.report.checks), 1)
            artifact_id = result.selected_run.results[0].run.output_artifact_id
            self.assertIsNotNone(artifact_id)
            assert artifact_id is not None
            self.assertTrue((root / ".fw-artifacts" / f"{artifact_id}.txt").exists())

    def test_complete_repository_task_preserves_failed_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_fail(self):\n        self.assertEqual(1, 2)\n",
                encoding="utf-8",
            )

            result = complete_repository_task(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        self.assertFalse(result.passed)
        self.assertFalse(result.selected_run.passed)
        self.assertFalse(result.report.passed)
        self.assertEqual(len(result.report.failed_checks), 1)
        self.assertEqual(result.report.failed_checks[0].outcome, "failed")

    def test_complete_repository_task_marks_empty_selection_as_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = complete_repository_task(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        self.assertFalse(result.passed)
        self.assertEqual(result.selected_run.results, ())
        self.assertIn("no verification commands were selected or run", result.report.risks)

    def test_complete_repository_task_rejects_invalid_selection_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                complete_repository_task(task_id="task-1", repo_root=Path(tmp) / "missing", output_dir=Path(tmp))


if __name__ == "__main__":
    unittest.main()
