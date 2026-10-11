from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.verify import VerifiedExecutorConfig, VerifiedExecutorFactory, build_verified_executor


class VerifiedExecutorFactoryTests(unittest.TestCase):
    def test_builds_executor_with_resolved_repo_targets_and_ruff_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            snapshots = Path(tmp) / "snapshots"
            config = VerifiedExecutorConfig(
                repo_root=root,
                snapshot_dir=snapshots,
                targets=(Path("pkg/a.py"),),
                config_hash="sha256:config",
                retry_attempts=2,
                timeout_seconds=7,
                ruff_executable="custom-ruff",
                ruff_rules=("F", "PL"),
            )

            executor = VerifiedExecutorFactory().build(config)

            self.assertEqual(executor.snapshot_store.snapshot_dir, snapshots.resolve())
            self.assertEqual(executor.analyzer_config.repo_root, root.resolve())
            self.assertEqual(executor.analyzer_config.targets, (root.resolve() / "pkg/a.py",))
            self.assertEqual(executor.analyzer_config.timeout_seconds, 7)
            self.assertEqual(executor.analyzer_config.config_hash, "sha256:config")
            self.assertEqual(executor.regression_gate.retry_budget.max_attempts, 2)
            self.assertEqual(len(executor.analyzers), 1)
            self.assertEqual(executor.analyzers[0].executable, "custom-ruff")
            self.assertEqual(executor.analyzers[0].selected_rules, ("F", "PL"))

    def test_convenience_builder_matches_factory_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            executor = build_verified_executor(
                repo_root=root,
                snapshot_dir=Path(tmp) / "snapshots",
                targets=(Path("app.py"),),
                config_hash="sha256:config",
            )

            self.assertEqual(executor.analyzer_config.repo_root, root.resolve())
            self.assertEqual(executor.analyzer_config.targets, (root.resolve() / "app.py",))

    def test_rejects_invalid_config_before_runtime_dispatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "targets"):
            VerifiedExecutorConfig(
                repo_root=Path("C:/repo"),
                snapshot_dir=Path("C:/repo/.fw/snapshots"),
                targets=(),
                config_hash="sha256:config",
            )
        with self.assertRaisesRegex(ValueError, "retry_attempts"):
            VerifiedExecutorConfig(
                repo_root=Path("C:/repo"),
                snapshot_dir=Path("C:/repo/.fw/snapshots"),
                targets=(Path("app.py"),),
                config_hash="sha256:config",
                retry_attempts=0,
            )


if __name__ == "__main__":
    unittest.main()
