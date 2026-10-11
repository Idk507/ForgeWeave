from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from forgeweave.tools import GitPolicyError, GitTools, register_git_tools


class GitToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._git("init")
        self._git("config", "user.email", "forgeweave@example.test")
        self._git("config", "user.name", "ForgeWeave Test")
        (self.root / "tracked.txt").write_text("one\n", encoding="utf-8")
        self._git("add", "tracked.txt")
        self._git("commit", "-m", "initial")
        self.git = GitTools(self.root)

    def test_status_reports_branch_dirty_and_porcelain_entries(self) -> None:
        (self.root / "tracked.txt").write_text("two\n", encoding="utf-8")
        (self.root / "new.txt").write_text("new\n", encoding="utf-8")

        status = self.git.status()

        self.assertTrue(status.dirty)
        self.assertIn("tracked.txt", status.changed_paths)
        self.assertIn("new.txt", status.changed_paths)
        self.assertEqual(status.branch, "master")

    def test_diff_returns_bounded_patch(self) -> None:
        (self.root / "tracked.txt").write_text("two\n", encoding="utf-8")

        diff = self.git.diff(max_bytes=10_000)

        self.assertIn("-one", diff.patch)
        self.assertIn("+two", diff.patch)
        self.assertFalse(diff.truncated)

    def test_diff_caps_large_output(self) -> None:
        (self.root / "tracked.txt").write_text("x" * 2000, encoding="utf-8")

        diff = self.git.diff(max_bytes=64)

        self.assertLessEqual(len(diff.patch.encode("utf-8")), 64)
        self.assertTrue(diff.truncated)

    def test_commit_requires_explicit_allow_mutation(self) -> None:
        (self.root / "tracked.txt").write_text("two\n", encoding="utf-8")

        with self.assertRaises(GitPolicyError):
            self.git.commit(message="update", paths=("tracked.txt",))

        commit = self.git.commit(message="update", paths=("tracked.txt",), allow_mutation=True)

        self.assertEqual(commit.message, "update")
        self.assertTrue(commit.commit_hash)
        self.assertFalse(self.git.status().dirty)

    def test_rejects_repository_without_own_git_directory(self) -> None:
        outside = self.root / "nested"
        outside.mkdir()

        with self.assertRaises(GitPolicyError):
            GitTools(outside)

    def test_git_tools_can_be_invoked_through_registry_for_read_only_status(self) -> None:
        registry = register_git_tools(self.root, catalog_version="tools-v1")

        invocation = registry.invoke(tool_name="git_status", tool_schema_version="git-status.v1", arguments={})

        self.assertEqual(invocation.output["dirty"], False)
        self.assertEqual(invocation.call.effects.reads, frozenset({"git"}))

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
