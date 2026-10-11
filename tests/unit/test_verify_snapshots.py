from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from forgeweave.verify import GitSnapshotStore


class GitSnapshotStoreTests(unittest.TestCase):
    def test_claim_captures_shell_edits_in_git_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            _git(root, "init")
            _git(root, "config", "user.email", "test@example.com")
            _git(root, "config", "user.name", "ForgeWeave Test")
            tracked = root / "app.py"
            tracked.write_text("print('before')\n", encoding="utf-8")
            _git(root, "add", "app.py")
            _git(root, "commit", "-m", "initial")
            tracked.write_text("print('after')\n", encoding="utf-8")
            store = GitSnapshotStore(snapshot_dir=Path(tmp) / "snapshots")

            snapshot = store.claim(repo_root=root, snapshot_id="step-1-before-repair")

            patch = snapshot.patch_path.read_text(encoding="utf-8")
            self.assertIn("# forgeweave-git-snapshot-v1", patch)
            self.assertIn("app.py", snapshot.changed_paths)
            self.assertIn("-print('before')", patch)
            self.assertIn("+print('after')", patch)
            self.assertTrue(snapshot.patch_hash.startswith("sha256:"))

    def test_duplicate_claim_returns_existing_snapshot_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            _git(root, "init")
            _git(root, "config", "user.email", "test@example.com")
            _git(root, "config", "user.name", "ForgeWeave Test")
            tracked = root / "app.py"
            tracked.write_text("print('before')\n", encoding="utf-8")
            _git(root, "add", "app.py")
            _git(root, "commit", "-m", "initial")
            tracked.write_text("print('first')\n", encoding="utf-8")
            store = GitSnapshotStore(snapshot_dir=Path(tmp) / "snapshots")

            first = store.claim(repo_root=root, snapshot_id="same-step")
            tracked.write_text("print('second')\n", encoding="utf-8")
            second = store.claim(repo_root=root, snapshot_id="same-step")

            self.assertEqual(first.patch_hash, second.patch_hash)
            patch = second.patch_path.read_text(encoding="utf-8")
            self.assertIn("+print('first')", patch)
            self.assertNotIn("+print('second')", patch)


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout


if __name__ == "__main__":
    unittest.main()
