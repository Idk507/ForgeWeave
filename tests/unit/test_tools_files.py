from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.tools import (
    FileTools,
    PathPolicyError,
    PatchConflictError,
    WorkspacePathGuard,
    content_hash,
    register_file_tools,
)


class FileToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_bytes(b"print('hello')\n")
        (self.root / "README.md").write_bytes(b"hello forge\nsecond line\n")
        self.tools = FileTools(WorkspacePathGuard(self.root))

    def test_path_guard_rejects_traversal_absolute_and_symlink_escape(self) -> None:
        guard = WorkspacePathGuard(self.root)
        outside = self.root.parent / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        (self.root / "link.txt").symlink_to(outside)

        self.assertEqual(guard.resolve("README.md"), self.root / "README.md")
        with self.assertRaises(PathPolicyError):
            guard.resolve("../outside.txt")
        with self.assertRaises(PathPolicyError):
            guard.resolve(str(outside))
        with self.assertRaises(PathPolicyError):
            guard.resolve("link.txt")

    def test_list_glob_read_and_search_are_bounded_to_workspace(self) -> None:
        self.assertEqual(self.tools.list_dir("."), ["README.md", "src/"])
        self.assertEqual(self.tools.glob("**/*.py"), ["src/app.py"])
        self.assertEqual(self.tools.read_text("README.md"), "hello forge\nsecond line\n")
        self.assertEqual(
            self.tools.search("f.rge"),
            [{"path": "README.md", "line": 1, "text": "hello forge"}],
        )

    def test_hash_conditional_replace_writes_and_reports_conflict(self) -> None:
        before = content_hash((self.root / "src" / "app.py").read_bytes())
        after = self.tools.replace_text(
            path="src/app.py",
            expected_hash=before,
            old="print('hello')\n",
            new="print('bye')\n",
        )

        self.assertEqual((self.root / "src" / "app.py").read_text(encoding="utf-8"), "print('bye')\n")
        self.assertNotEqual(after.before_hash, after.after_hash)

        with self.assertRaises(PatchConflictError) as conflict:
            self.tools.replace_text(
                path="src/app.py",
                expected_hash=before,
                old="print('bye')\n",
                new="print('again')\n",
            )

        self.assertEqual(conflict.exception.current_hash, after.after_hash)

    def test_replace_requires_exact_old_text_once(self) -> None:
        before = content_hash((self.root / "README.md").read_bytes())

        with self.assertRaises(PatchConflictError):
            self.tools.replace_text(path="README.md", expected_hash=before, old="missing", new="new")

    def test_file_tools_can_be_invoked_through_registry(self) -> None:
        registry = register_file_tools(WorkspacePathGuard(self.root), catalog_version="tools-v1")
        before = content_hash((self.root / "README.md").read_bytes())

        read = registry.invoke(
            tool_name="read_file",
            tool_schema_version="read-file.v1",
            arguments={"path": "README.md"},
        )
        patch = registry.invoke(
            tool_name="replace_text",
            tool_schema_version="replace-text.v1",
            arguments={"path": "README.md", "expected_hash": before, "old": "forge", "new": "weave"},
        )

        self.assertEqual(read.output, "hello forge\nsecond line\n")
        self.assertEqual(read.call.effects.reads, frozenset({"workspace"}))
        self.assertEqual(patch.output["path"], "README.md")
        self.assertEqual(patch.call.effects.writes, frozenset({"workspace"}))


if __name__ == "__main__":
    unittest.main()
