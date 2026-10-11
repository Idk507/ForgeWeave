from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from forgeweave.verify.runner import RepairGuard, VerificationCommand, VerificationRunner


class VerificationRunnerTests(unittest.TestCase):
    def test_passed_command_records_verification_run_and_output_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
            output_dir = workspace / ".fw-artifacts"

            result = VerificationRunner(output_dir=output_dir).run(
                task_id="task-1",
                command=VerificationCommand(
                    criterion_ids=("unit-tests",),
                    argv=(sys.executable, "-c", "print('ok')"),
                    cwd=workspace,
                    verifier_version="python",
                    config_hash="sha256:config",
                    environment_profile_hash="sha256:env",
                    workspace_fingerprint="sha256:workspace",
                    untracked_input_hashes={"tracked.py": "sha256:file"},
                    timeout_seconds=5,
                ),
            )

            self.assertEqual(result.run.outcome, "passed")
            self.assertEqual(result.run.exit_code, 0)
            self.assertEqual(result.stdout, "ok\n")
            self.assertEqual(result.stderr, "")
            self.assertIsNotNone(result.run.output_artifact_id)
            artifact = output_dir / f"{result.run.output_artifact_id}.txt"
            self.assertIn("stdout:\nok", artifact.read_text(encoding="utf-8"))
            self.assertTrue(result.run.whole_input_fingerprint.startswith("sha256:"))
            self.assertIsNotNone(result.run.duration_ms)
            assert result.run.duration_ms is not None
            self.assertGreaterEqual(result.run.duration_ms, 0.0)

    def test_failed_command_is_failed_not_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = VerificationRunner(output_dir=workspace / "artifacts").run(
                task_id="task-1",
                command=VerificationCommand(
                    criterion_ids=("unit-tests",),
                    argv=(sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"),
                    cwd=workspace,
                    verifier_version="python",
                    config_hash="sha256:config",
                    environment_profile_hash="sha256:env",
                    workspace_fingerprint="sha256:workspace",
                    timeout_seconds=5,
                ),
            )

            self.assertEqual(result.run.outcome, "failed")
            self.assertEqual(result.run.exit_code, 3)
            self.assertEqual(result.stdout, "bad\n")

    def test_timeout_is_inconclusive_and_caps_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = VerificationRunner(output_dir=workspace / "artifacts", output_cap_bytes=20).run(
                task_id="task-1",
                command=VerificationCommand(
                    criterion_ids=("timeout",),
                    argv=(sys.executable, "-c", "import time; print('before'); time.sleep(5)"),
                    cwd=workspace,
                    verifier_version="python",
                    config_hash="sha256:config",
                    environment_profile_hash="sha256:env",
                    workspace_fingerprint="sha256:workspace",
                    timeout_seconds=1,
                ),
            )

            self.assertEqual(result.run.outcome, "inconclusive")
            self.assertIsNone(result.run.exit_code)
            self.assertLessEqual(len(result.stdout.encode("utf-8")) + len(result.stderr.encode("utf-8")), 20)
            self.assertIsNotNone(result.run.duration_ms)


class RepairGuardTests(unittest.TestCase):
    def test_repeated_identical_failure_stops_repair(self) -> None:
        guard = RepairGuard(max_repairs=3)

        first = guard.record_failure("sha256:input", ("unit-tests",), "failed", 1)
        second = guard.record_failure("sha256:input", ("unit-tests",), "failed", 1)

        self.assertFalse(first.should_stop)
        self.assertTrue(second.should_stop)
        self.assertEqual(second.reason, "repeated-identical-failure")

    def test_global_repair_cap_stops_even_for_distinct_failures(self) -> None:
        guard = RepairGuard(max_repairs=2)

        guard.record_failure("sha256:one", ("a",), "failed", 1)
        second = guard.record_failure("sha256:two", ("b",), "failed", 2)

        self.assertTrue(second.should_stop)
        self.assertEqual(second.reason, "repair-budget-exhausted")


if __name__ == "__main__":
    unittest.main()
