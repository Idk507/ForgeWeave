from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from forgeweave.tools import TestRunnerTools, WorkspacePathGuard, register_test_runner_tool


class TestRunnerToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "pkg").mkdir()
        self.evidence = self.root / ".fw-evidence"
        self.runner = TestRunnerTools(WorkspacePathGuard(self.root), output_dir=self.evidence)

    def test_runs_test_command_and_returns_verification_evidence(self) -> None:
        result = self.runner.run_tests(
            task_id="task-1",
            criterion_ids=("unit",),
            argv=(sys.executable, "-c", "print('ok')"),
            cwd="pkg",
            timeout_seconds=5,
            verifier_version="python",
            config_hash="sha256:config",
            environment_profile_hash="sha256:env",
            workspace_fingerprint="sha256:workspace",
        )

        self.assertEqual(result.run.outcome, "passed")
        self.assertEqual(result.run.exit_code, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertTrue((self.evidence / f"{result.run.output_artifact_id}.txt").exists())

    def test_failed_test_command_is_failed_evidence(self) -> None:
        result = self.runner.run_tests(
            task_id="task-1",
            criterion_ids=("unit",),
            argv=(sys.executable, "-c", "import sys; sys.exit(2)"),
            cwd=".",
            timeout_seconds=5,
            verifier_version="python",
            config_hash="sha256:config",
            environment_profile_hash="sha256:env",
            workspace_fingerprint="sha256:workspace",
        )

        self.assertEqual(result.run.outcome, "failed")
        self.assertEqual(result.run.exit_code, 2)

    def test_cwd_escape_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.runner.run_tests(
                task_id="task-1",
                criterion_ids=("unit",),
                argv=(sys.executable, "--version"),
                cwd="../",
                timeout_seconds=5,
                verifier_version="python",
                config_hash="sha256:config",
                environment_profile_hash="sha256:env",
                workspace_fingerprint="sha256:workspace",
            )

    def test_test_runner_tool_can_be_invoked_through_registry(self) -> None:
        registry = register_test_runner_tool(WorkspacePathGuard(self.root), output_dir=self.evidence, catalog_version="tools-v1")

        invocation = registry.invoke(
            tool_name="run_tests",
            tool_schema_version="run-tests.v1",
            arguments={
                "task_id": "task-1",
                "criterion_ids": ["unit"],
                "argv": [sys.executable, "-c", "print('ok')"],
                "cwd": ".",
                "timeout_seconds": 5,
                "verifier_version": "python",
                "config_hash": "sha256:config",
                "environment_profile_hash": "sha256:env",
                "workspace_fingerprint": "sha256:workspace",
            },
        )

        self.assertEqual(invocation.output["run"]["outcome"], "passed")
        self.assertEqual(invocation.output["stdout"], "ok\n")
        self.assertEqual(invocation.call.effects.process, frozenset({"test-runner"}))


if __name__ == "__main__":
    unittest.main()
