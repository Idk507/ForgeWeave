"""Offline CLI integration against real Git repositories and workspace changes."""

from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from forgeweave.cli.app import main
from forgeweave.contracts import EventKind, ToolExecutionState
from forgeweave.events import EventStore


class NativeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.state = self.root / "state"
        self.git("init")
        self.git("config", "user.email", "test@example.test")
        self.git("config", "user.name", "Test")
        (self.repo / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_calculator.py").write_text(
            "import unittest\nfrom calculator import add\n"
            "class Tests(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n", encoding="utf-8"
        )
        self.git("add", ".")
        self.git("commit", "-m", "seeded bug")
        self.original_head = self.git("rev-parse", "HEAD")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    def run_cli(self, *options: str) -> tuple[int, dict, str]:
        out, err = StringIO(), StringIO()
        code = main([
            "run", "--prompt", "Fix addition", "--repo-root", str(self.repo),
            "--state-dir", str(self.state), "--task-id", "task-one", "--json", *options,
        ], stdout=out, stderr=err)
        return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()

    def edit_call(self, *, path: str = "calculator.py", expected_hash: str | None = None) -> str:
        return json.dumps({
            "tool_name": "replace_text", "tool_schema_version": "replace-text.v1",
            "arguments": {"path": path, "old": "a - b", "new": "a + b",
                          "expected_hash": expected_hash or "sha256:" + sha256((self.repo / "calculator.py").read_bytes()).hexdigest()},
        })

    def test_cli_fixes_and_verifies_in_owned_worktree_with_durable_events(self) -> None:
        code, result, error = self.run_cli(
            "--allow-host-execution", "--mode", "implement", "--allow-write", "calculator.py",
            "--fake-tool-call", self.edit_call(), "--fake-response", "Fixed addition", "--complete-report",
        )
        self.assertEqual(code, 0, error or str(result))
        self.assertEqual(result["task_status"], "COMPLETED")
        worktree = Path(result["worktree_path"])
        self.assertIn("a + b", (worktree / "calculator.py").read_text())
        self.assertIn("a - b", (self.repo / "calculator.py").read_text())
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original_head)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertTrue(result["final_report"]["passed"])
        self.assertEqual(result["final_report"]["modified_files"], ["calculator.py"])
        self.assertEqual(result["isolation"], "host-user")
        store = EventStore.open(self.state / "events.db")
        try:
            events = store.list_events("task-one")
            kinds = [event.kind for event in events]
            self.assertLess(kinds.index(EventKind.TOOL_CALL_REQUESTED), kinds.index(EventKind.POLICY_DECISION))
            self.assertLess(kinds.index(EventKind.POLICY_DECISION), kinds.index(EventKind.TOOL_RESULT))
            self.assertEqual(store.list_tool_executions()[0].state, ToolExecutionState.SUCCEEDED)
            intents = [store.read_payload(e.payload_ref) for e in events if e.kind is EventKind.WORKTREE_RECORDED]
            self.assertEqual([i["phase"] for i in intents], ["intent", "created"])
            self.assertEqual(intents[0]["base_commit"], self.original_head)
        finally:
            store.close()
        out = StringIO()
        self.assertEqual(main(["task", "inspect", "--state-dir", str(self.state), "--task-id", "task-one", "--json"], stdout=out), 0)
        self.assertEqual(json.loads(out.getvalue())["worktree_path"], str(worktree))

    def test_cli_rejects_duplicate_task_without_another_worktree(self) -> None:
        options = ("--allow-host-execution", "--fake-response", "Inspected")
        self.assertEqual(self.run_cli(*options)[0], 0)
        before = self.git("worktree", "list", "--porcelain")
        code, _, error = self.run_cli(*options)
        self.assertEqual(code, 1)
        self.assertIn("already exists", error)
        self.assertEqual(self.git("worktree", "list", "--porcelain"), before)

    def test_plan_mode_denies_write_even_when_path_is_listed(self) -> None:
        code, result, error = self.run_cli(
            "--allow-host-execution", "--mode", "plan", "--allow-write", "calculator.py",
            "--fake-tool-call", self.edit_call(),
        )
        self.assertNotEqual(code, 0, error)
        self.assertEqual(result["stop_reason"], "failed")
        self.assertIn("a - b", (Path(result["worktree_path"]) / "calculator.py").read_text())

    def test_host_execution_authority_is_required_before_creating_state(self) -> None:
        code, _, error = self.run_cli("--fake-response", "done")
        self.assertEqual(code, 1)
        self.assertIn("--allow-host-execution", error)
        self.assertFalse(self.state.exists())

    def test_verification_inputs_cannot_be_authorized_for_edit(self) -> None:
        code, _, error = self.run_cli("--allow-host-execution", "--mode", "implement",
                                      "--allow-write", "tests/test_calculator.py")
        self.assertEqual(code, 1)
        self.assertIn("verification inputs", error)
        self.assertFalse(self.state.exists())

    def test_dirty_checkout_and_nested_state_are_rejected_without_source_changes(self) -> None:
        (self.repo / "user.txt").write_text("keep me")
        code, _, error = self.run_cli("--allow-host-execution")
        self.assertEqual(code, 1)
        self.assertIn("uncommitted", error)
        self.assertEqual((self.repo / "user.txt").read_text(), "keep me")
        out, err = StringIO(), StringIO()
        code = main(["run", "--prompt", "Inspect", "--repo-root", str(self.repo),
                     "--state-dir", str(self.repo / ".state"), "--allow-host-execution"], stdout=out, stderr=err)
        self.assertEqual(code, 1)
        self.assertIn("outside", err.getvalue())
        self.assertFalse((self.repo / ".state").exists())


if __name__ == "__main__":
    unittest.main()
