from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.integrations.github import GitCommandResult, GitHubCheckoutApplier, GitHubCheckoutPlan, GitHubCliError


class GitHubCheckoutApplierTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.worktrees = self.root / "worktrees"
        self.plan = GitHubCheckoutPlan(
            repository="owner/repo",
            pull_number=17,
            head_sha="abcdefabcdefabcdefabcdefabcdefabcdef1234",
            base_ref="main",
            head_ref="feature",
            head_repository="owner/repo",
            fetch_ref="pull/17/head",
            checkout_ref="refs/forgeweave/pr-17-abcdefabcdef",
        )

    def test_dry_run_returns_fetch_and_worktree_commands_without_running(self) -> None:
        calls: list[tuple[tuple[str, ...], Path, int]] = []
        applier = GitHubCheckoutApplier(repository_root=self.repo, worktree_root=self.worktrees, runner=lambda argv, cwd, timeout: calls.append((tuple(argv), cwd, timeout)) or _ok(argv, cwd))

        commands = applier.dry_run(self.plan)

        self.assertEqual(calls, [])
        self.assertEqual(commands[0], ("git", "fetch", "--no-tags", "origin", "pull/17/head:refs/forgeweave/pr-17-abcdefabcdef"))
        self.assertEqual(commands[1], ("git", "worktree", "add", "--detach", str((self.worktrees / "pr-17-abcdefabcdef").resolve()), self.plan.head_sha))

    def test_apply_runs_fetch_then_detached_worktree_with_evidence(self) -> None:
        calls: list[tuple[tuple[str, ...], Path, int]] = []

        def runner(argv, cwd, timeout):
            calls.append((tuple(argv), cwd, timeout))
            return _ok(argv, cwd)

        applier = GitHubCheckoutApplier(repository_root=self.repo, worktree_root=self.worktrees, runner=runner)

        checkout = applier.apply(self.plan, timeout_seconds=12)

        self.assertEqual(checkout.worktree_path, (self.worktrees / "pr-17-abcdefabcdef").resolve())
        self.assertEqual(len(checkout.commands), 2)
        self.assertEqual([call[0][:3] for call in calls], [("git", "fetch", "--no-tags"), ("git", "worktree", "add")])
        self.assertTrue(all(call[1] == self.repo.resolve() for call in calls))
        self.assertTrue(all(call[2] == 12 for call in calls))

    def test_rejects_existing_worktree_path_before_running_commands(self) -> None:
        target = self.worktrees / "pr-17-abcdefabcdef"
        target.mkdir(parents=True)
        calls: list[tuple[str, ...]] = []
        applier = GitHubCheckoutApplier(repository_root=self.repo, worktree_root=self.worktrees, runner=lambda argv, cwd, timeout: calls.append(tuple(argv)) or _ok(argv, cwd))

        with self.assertRaises(GitHubCliError) as raised:
            applier.apply(self.plan)

        self.assertEqual(raised.exception.code, "WORKTREE_PATH_EXISTS")
        self.assertEqual(calls, [])

    def test_rejects_git_failure_and_stops_after_fetch(self) -> None:
        calls: list[tuple[str, ...]] = []

        def runner(argv, cwd, timeout):
            calls.append(tuple(argv))
            return GitCommandResult(command=tuple(argv), cwd=cwd, returncode=2, stderr="fetch failed")

        applier = GitHubCheckoutApplier(repository_root=self.repo, worktree_root=self.worktrees, runner=runner)

        with self.assertRaises(GitHubCliError) as raised:
            applier.apply(self.plan)

        self.assertEqual(raised.exception.code, "GIT_FAILED")
        self.assertEqual(len(calls), 1)

    def test_rejects_mismatched_command_evidence(self) -> None:
        applier = GitHubCheckoutApplier(
            repository_root=self.repo,
            worktree_root=self.worktrees,
            runner=lambda _argv, cwd, _timeout: GitCommandResult(command=("git", "status"), cwd=cwd, returncode=0),
        )

        with self.assertRaises(GitHubCliError) as raised:
            applier.apply(self.plan)

        self.assertEqual(raised.exception.code, "COMMAND_MISMATCH")

    def test_requires_repository_root_with_git_directory(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            GitHubCheckoutApplier(repository_root=self.root / "missing", worktree_root=self.worktrees)

        self.assertEqual(raised.exception.code, "INVALID_REPOSITORY_ROOT")


def _ok(argv, cwd: Path) -> GitCommandResult:
    return GitCommandResult(command=tuple(argv), cwd=cwd, returncode=0, stdout="ok")


if __name__ == "__main__":
    unittest.main()
