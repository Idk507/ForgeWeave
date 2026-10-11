from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.verify import select_verification_commands


class VerificationSelectionTests(unittest.TestCase):
    def test_selects_pytest_from_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
            (root / "tests").mkdir()

            selection = select_verification_commands(root, environment_profile_hash="sha256:env")

        self.assertEqual(len(selection.commands), 1)
        self.assertEqual(selection.commands[0].argv, ("python", "-m", "pytest"))
        self.assertEqual(selection.commands[0].criterion_ids, ("pytest",))
        self.assertEqual(selection.commands[0].environment_profile_hash, "sha256:env")
        self.assertIn("pyproject.toml:[tool.pytest]", selection.sources)
        self.assertTrue(selection.config_hash.startswith("sha256:"))
        self.assertTrue(selection.workspace_fingerprint.startswith("sha256:"))

    def test_falls_back_to_unittest_when_tests_dir_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()

            selection = select_verification_commands(root)

        self.assertEqual(selection.commands[0].argv, ("python", "-m", "unittest", "discover", "-s", "tests"))
        self.assertEqual(selection.sources, ("tests/",))

    def test_adds_ruff_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n[tool.ruff]\nline-length = 120\n", encoding="utf-8")

            selection = select_verification_commands(root)

        self.assertEqual([cmd.criterion_ids[0] for cmd in selection.commands], ["pytest", "ruff"])
        self.assertEqual(selection.commands[1].argv, ("python", "-m", "ruff", "check", "."))

    def test_returns_empty_selection_when_no_config_or_tests_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            selection = select_verification_commands(Path(tmp))

        self.assertEqual(selection.commands, ())
        self.assertEqual(selection.sources, ())

    def test_rejects_bad_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                select_verification_commands(Path(tmp) / "missing")
            with self.assertRaises(ValueError):
                select_verification_commands(Path(tmp), timeout_seconds=0)
            with self.assertRaises(ValueError):
                select_verification_commands(Path(tmp), environment_profile_hash=" ")


if __name__ == "__main__":
    unittest.main()
