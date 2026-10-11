from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.verify import run_selected_verification


class SelectedVerificationRunnerTests(unittest.TestCase):
    def test_runs_selected_unittest_command_and_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            output_dir = root / ".fw-artifacts"

            run = run_selected_verification(task_id="task-1", repo_root=root, output_dir=output_dir)

            self.assertTrue(run.passed)
            self.assertEqual(len(run.results), 1)
            self.assertEqual(run.results[0].run.criterion_ids, ("unittest",))
            self.assertEqual(run.results[0].run.outcome, "passed")
            self.assertIsNotNone(run.results[0].run.output_artifact_id)
            assert run.results[0].run.output_artifact_id is not None
            self.assertTrue((output_dir / f"{run.results[0].run.output_artifact_id}.txt").exists())
            self.assertIsNotNone(run.results[0].run.duration_ms)

    def test_reports_failed_selected_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_fail(self):\n        self.assertEqual(1, 2)\n",
                encoding="utf-8",
            )

            run = run_selected_verification(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        self.assertFalse(run.passed)
        self.assertEqual(len(run.failed_results), 1)
        self.assertEqual(run.failed_results[0].run.outcome, "failed")
        self.assertEqual(run.failed_results[0].run.exit_code, 1)

    def test_empty_selection_runs_no_commands_and_does_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            run = run_selected_verification(task_id="task-1", repo_root=root, output_dir=root / ".fw-artifacts")

        self.assertEqual(run.results, ())
        self.assertFalse(run.passed)

    def test_rejects_blank_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_selected_verification(task_id=" ", repo_root=Path(tmp), output_dir=Path(tmp) / ".fw-artifacts")


if __name__ == "__main__":
    unittest.main()
