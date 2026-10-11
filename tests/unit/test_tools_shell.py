from __future__ import annotations

from pathlib import Path
import sys
import threading
import time
import tempfile
import unittest

from forgeweave.core import CancellationToken
from forgeweave.tools import ShellPolicyError, ShellTools, WorkspacePathGuard, register_shell_tool


class ShellToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "work").mkdir()
        self.shell = ShellTools(WorkspacePathGuard(self.root))

    def test_runs_argv_in_workspace_cwd(self) -> None:
        result = self.shell.run(
            argv=(sys.executable, "-c", "from pathlib import Path; print(Path.cwd().name)"),
            cwd="work",
            timeout_seconds=5,
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "work\n")
        self.assertFalse(result.timed_out)

    def test_nonzero_exit_is_reported_without_exception(self) -> None:
        result = self.shell.run(
            argv=(sys.executable, "-c", "import sys; print('bad'); sys.exit(7)"),
            cwd=".",
            timeout_seconds=5,
        )

        self.assertEqual(result.exit_code, 7)
        self.assertEqual(result.stdout, "bad\n")

    def test_timeout_is_structured(self) -> None:
        result = self.shell.run(
            argv=(sys.executable, "-c", "import time; print('before'); time.sleep(5)"),
            cwd=".",
            timeout_seconds=1,
        )

        self.assertIsNone(result.exit_code)
        self.assertTrue(result.timed_out)

    def test_output_is_capped_across_stdout_and_stderr(self) -> None:
        result = self.shell.run(
            argv=(sys.executable, "-c", "print('abcdef'); import sys; print('ghijkl', file=sys.stderr)"),
            cwd=".",
            timeout_seconds=5,
            output_cap_bytes=8,
        )

        total = len(result.stdout.encode("utf-8")) + len(result.stderr.encode("utf-8"))
        self.assertLessEqual(total, 8)
        self.assertTrue(result.output_truncated)

    def test_environment_allowlist_does_not_inherit_unlisted_values(self) -> None:
        result = self.shell.run(
            argv=(sys.executable, "-c", "import os; print(os.environ.get('ALLOWED')); print(os.environ.get('BLOCKED'))"),
            cwd=".",
            timeout_seconds=5,
            env={"ALLOWED": "yes", "BLOCKED": "no"},
            env_allowlist=frozenset({"ALLOWED"}),
        )

        self.assertEqual(result.stdout, "yes\nNone\n")

    def test_rejects_shell_string_and_escaped_cwd(self) -> None:
        with self.assertRaises(ShellPolicyError):
            self.shell.run(argv=(), cwd=".", timeout_seconds=5)
        with self.assertRaises(ShellPolicyError):
            self.shell.run(argv=(sys.executable, "--version"), cwd="../", timeout_seconds=5)


    def test_cancellation_during_dispatch_terminates_subprocess(self) -> None:
        token = CancellationToken()

        def cancel_later() -> None:
            time.sleep(0.2)
            token.cancel("user stopped")

        thread = threading.Thread(target=cancel_later)
        thread.start()
        try:
            result = self.shell.run(
                argv=(sys.executable, "-c", "import time; print('started', flush=True); time.sleep(10)"),
                cwd=".",
                timeout_seconds=5,
                cancellation=token,
            )
        finally:
            thread.join(timeout=2)

        self.assertIsNone(result.exit_code)
        self.assertTrue(result.cancelled)
        self.assertFalse(result.timed_out)

    def test_cancellation_before_dispatch_blocks_subprocess(self) -> None:
        token = CancellationToken()
        token.cancel("user stopped")

        with self.assertRaises(InterruptedError):
            self.shell.run(argv=(sys.executable, "--version"), cwd=".", timeout_seconds=5, cancellation=token)

    def test_shell_tool_can_be_invoked_through_registry(self) -> None:
        registry = register_shell_tool(WorkspacePathGuard(self.root), catalog_version="tools-v1")

        invocation = registry.invoke(
            tool_name="run_shell",
            tool_schema_version="run-shell.v1",
            arguments={"argv": [sys.executable, "-c", "print('ok')"], "cwd": ".", "timeout_seconds": 5},
        )

        self.assertEqual(invocation.output["exit_code"], 0)
        self.assertEqual(invocation.output["stdout"], "ok\n")
        self.assertEqual(invocation.call.effects.process, frozenset({"subprocess"}))


if __name__ == "__main__":
    unittest.main()
