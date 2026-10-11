from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from forgeweave.contracts import EffectSet, ToolCall
from forgeweave.verify import (
    AnalyzerExecutionConfig,
    AnalyzerInvocation,
    AnalyzerResult,
    Finding,
    GitSnapshotStore,
    RegressionGate,
    RetryBudget,
    VerifiedToolExecutor,
)


class VerifiedToolExecutorTests(unittest.TestCase):
    def test_read_only_tool_skips_snapshots_and_analyzers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(Path(tmp))
            analyzer = ContentAnalyzer(root / "app.py")
            executor = VerifiedToolExecutor(
                snapshot_store=GitSnapshotStore(snapshot_dir=Path(tmp) / "snapshots"),
                analyzers=(analyzer,),
                regression_gate=RegressionGate(retry_budget=RetryBudget(2)),
                analyzer_config=AnalyzerExecutionConfig(
                    repo_root=root,
                    targets=(root / "app.py",),
                    config_hash="sha256:config",
                ),
            )

            result = executor.run(call=_call(effects=EffectSet(reads=frozenset({"workspace"}))), dispatch=lambda: "read")

            self.assertEqual(result.output, "read")
            self.assertIsNone(result.gate_decision)
            self.assertIsNone(result.before_snapshot)
            self.assertEqual(analyzer.invocations, 0)

    def test_mutating_tool_snapshots_runs_analyzers_and_passes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(Path(tmp))
            app = root / "app.py"
            analyzer = ContentAnalyzer(app)
            budget = RetryBudget(2)
            executor = VerifiedToolExecutor(
                snapshot_store=GitSnapshotStore(snapshot_dir=Path(tmp) / "snapshots"),
                analyzers=(analyzer,),
                regression_gate=RegressionGate(retry_budget=budget),
                analyzer_config=AnalyzerExecutionConfig(repo_root=root, targets=(app,), config_hash="sha256:config"),
            )

            def dispatch_clean_write() -> str:
                app.write_text("print('clean after')\n", encoding="utf-8")
                return "written"

            result = executor.run(
                call=_call(effects=EffectSet(writes=frozenset({"workspace"}))),
                dispatch=dispatch_clean_write,
            )

            self.assertEqual(result.output, "written")
            self.assertEqual(result.gate_decision.outcome, "passed")
            self.assertEqual(result.before_snapshot.snapshot_id, "call-1-before")
            self.assertEqual(result.after_snapshot.snapshot_id, "call-1-after")
            self.assertEqual(analyzer.invocations, 2)
            self.assertEqual(budget.failed, 0)

    def test_mutating_tool_reports_regression_and_consumes_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(Path(tmp))
            app = root / "app.py"
            analyzer = ContentAnalyzer(app)
            budget = RetryBudget(2)
            executor = VerifiedToolExecutor(
                snapshot_store=GitSnapshotStore(snapshot_dir=Path(tmp) / "snapshots"),
                analyzers=(analyzer,),
                regression_gate=RegressionGate(retry_budget=budget),
                analyzer_config=AnalyzerExecutionConfig(repo_root=root, targets=(app,), config_hash="sha256:config"),
            )

            def dispatch_shell_edit() -> str:
                app.write_text("bad_call()\n", encoding="utf-8")
                return "shell-edited"

            result = executor.run(
                call=_call(effects=EffectSet(process=frozenset({"shell"}))),
                dispatch=dispatch_shell_edit,
            )

            self.assertEqual(result.output, "shell-edited")
            self.assertEqual(result.gate_decision.outcome, "code-regression")
            self.assertTrue(result.gate_decision.should_block)
            self.assertEqual(len(result.gate_decision.regressions), 1)
            self.assertEqual(budget.failed, 1)
            self.assertIn("+bad_call()", result.after_snapshot.patch_path.read_text(encoding="utf-8"))


class ContentAnalyzer:
    name = "ruff"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.invocations = 0

    def run(self, invocation: AnalyzerInvocation) -> AnalyzerResult:
        self.invocations += 1
        text = self.path.read_text(encoding="utf-8")
        findings = ()
        if "bad_call" in text:
            findings = (Finding(file="app.py", analyzer="ruff", rule="F401", message="bad call"),)
        return AnalyzerResult(
            analyzer="ruff",
            command_argv=("fake-ruff", "app.py"),
            cwd=str(invocation.cwd),
            findings=findings,
            exit_code=1 if findings else 0,
        )


def _repo(parent: Path) -> Path:
    root = parent / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "ForgeWeave Test")
    app = root / "app.py"
    app.write_text("print('clean before')\n", encoding="utf-8")
    _git(root, "add", "app.py")
    _git(root, "commit", "-m", "initial")
    return root


def _call(*, effects: EffectSet) -> ToolCall:
    return ToolCall(
        call_id="call-1",
        tool_name="tool",
        tool_schema_version="tool.v1",
        arguments={},
        argument_hash="sha256:args",
        effects=effects,
    )


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout


if __name__ == "__main__":
    unittest.main()
