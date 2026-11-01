from __future__ import annotations

import unittest

from forgeweave.integrations.github import GitHubCliCommand, GitHubCliError, GitHubCliResult, GitHubCliRunner, GitHubReference, build_gh_command, parse_github_reference


class GitHubCliTests(unittest.TestCase):
    def test_parse_shorthand_reference(self) -> None:
        reference = parse_github_reference("openai/codex#123")

        self.assertEqual(reference, GitHubReference(owner="openai", repo="codex", number=123))
        self.assertEqual(reference.repository, "openai/codex")

    def test_parse_issue_and_pull_urls(self) -> None:
        issue = parse_github_reference("https://github.com/openai/codex/issues/42")
        pull = parse_github_reference("https://github.com/openai/codex/pull/43/files")

        self.assertEqual(issue.number, 42)
        self.assertEqual(pull.number, 43)
        self.assertEqual(pull.repository, "openai/codex")

    def test_invalid_reference_is_rejected(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            parse_github_reference("https://example.com/openai/codex/issues/1")

        self.assertEqual(raised.exception.code, "INVALID_REFERENCE")

    def test_builds_read_only_issue_view_command(self) -> None:
        command = build_gh_command(GitHubCliCommand.ISSUE_VIEW, GitHubReference(owner="owner", repo="repo", number=7))

        self.assertEqual(command[:4], ("gh", "issue", "view", "7"))
        self.assertIn("--repo", command)
        self.assertIn("owner/repo", command)
        self.assertIn("--json", command)

    def test_builds_read_only_pr_and_ci_commands(self) -> None:
        reference = GitHubReference(owner="owner", repo="repo", number=9)

        self.assertEqual(build_gh_command(GitHubCliCommand.PR_VIEW, reference)[:4], ("gh", "pr", "view", "9"))
        self.assertEqual(build_gh_command(GitHubCliCommand.PR_CHECKS, reference)[:4], ("gh", "pr", "checks", "9"))
        self.assertEqual(build_gh_command(GitHubCliCommand.RUN_VIEW, reference)[:4], ("gh", "run", "view", "9"))

    def test_rejects_invalid_reference_parts_before_command_build(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            build_gh_command(GitHubCliCommand.ISSUE_VIEW, GitHubReference(owner="bad/name", repo="repo", number=1))

        self.assertEqual(raised.exception.code, "INVALID_OWNER")

    def test_runner_uses_injected_command_runner_and_preserves_evidence(self) -> None:
        calls: list[tuple[tuple[str, ...], int]] = []

        def fake_runner(argv, timeout_seconds):
            calls.append((tuple(argv), timeout_seconds))
            return GitHubCliResult(command=tuple(argv), returncode=0, stdout='{"number": 1}', stderr="")

        runner = GitHubCliRunner(executable="gh-test", timeout_seconds=5, runner=fake_runner)
        result = runner.issue_view(GitHubReference(owner="owner", repo="repo", number=1))

        self.assertEqual(calls, [(("gh-test", "issue", "view", "1", "--repo", "owner/repo", "--json", "number,title,state,author,body,url,labels,assignees,updatedAt"), 5)])
        self.assertEqual(result.json(), {"number": 1})

    def test_runner_rejects_mismatched_command_evidence(self) -> None:
        runner = GitHubCliRunner(runner=lambda _argv, _timeout: GitHubCliResult(command=("gh", "pr", "create"), returncode=0, stdout="{}", stderr=""))

        with self.assertRaises(GitHubCliError) as raised:
            runner.pr_view(GitHubReference(owner="owner", repo="repo", number=1))

        self.assertEqual(raised.exception.code, "COMMAND_MISMATCH")


if __name__ == "__main__":
    unittest.main()
