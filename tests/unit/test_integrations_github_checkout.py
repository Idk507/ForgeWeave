from __future__ import annotations

import unittest

from forgeweave.integrations.github import GitHubCliError, GitHubReference, checkout_plan_from_pr_view


class GitHubCheckoutPlanTests(unittest.TestCase):
    def test_builds_commit_pinned_checkout_plan_from_pr_payload(self) -> None:
        reference = GitHubReference(owner="owner", repo="repo", number=17)
        payload = {
            "number": 17,
            "baseRefName": "main",
            "headRefName": "feature/agent-fix",
            "headRepository": {"nameWithOwner": "contributor/repo"},
            "commits": [
                {"oid": "1111111111111111111111111111111111111111"},
                {"oid": "ABCDEFabcdefABCDEFabcdefABCDEFabcdef1234"},
            ],
        }

        plan = checkout_plan_from_pr_view(reference, payload)

        self.assertEqual(plan.repository, "owner/repo")
        self.assertEqual(plan.pull_number, 17)
        self.assertEqual(plan.head_sha, "abcdefabcdefabcdefabcdefabcdefabcdef1234")
        self.assertEqual(plan.base_ref, "main")
        self.assertEqual(plan.head_ref, "feature/agent-fix")
        self.assertEqual(plan.head_repository, "contributor/repo")
        self.assertEqual(plan.fetch_ref, "pull/17/head")
        self.assertEqual(plan.checkout_ref, "refs/forgeweave/pr-17-abcdefabcdef")
        self.assertEqual(plan.git_fetch_argv, ("git", "fetch", "--no-tags", "origin", "pull/17/head:refs/forgeweave/pr-17-abcdefabcdef"))
        self.assertEqual(plan.git_worktree_argv, ("git", "worktree", "add", "--detach", "<worktree-path>", "abcdefabcdefabcdefabcdefabcdefabcdef1234"))

    def test_rejects_payload_for_different_pull_request(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            checkout_plan_from_pr_view(GitHubReference(owner="owner", repo="repo", number=17), {"number": 18})

        self.assertEqual(raised.exception.code, "PR_NUMBER_MISMATCH")

    def test_requires_commits_for_exact_head_sha(self) -> None:
        payload = {"number": 17, "baseRefName": "main", "headRefName": "branch", "commits": []}

        with self.assertRaises(GitHubCliError) as raised:
            checkout_plan_from_pr_view(GitHubReference(owner="owner", repo="repo", number=17), payload)

        self.assertEqual(raised.exception.code, "MISSING_COMMITS")

    def test_rejects_malformed_head_sha(self) -> None:
        payload = {"number": 17, "baseRefName": "main", "headRefName": "branch", "commits": [{"oid": "not-a-sha"}]}

        with self.assertRaises(GitHubCliError) as raised:
            checkout_plan_from_pr_view(GitHubReference(owner="owner", repo="repo", number=17), payload)

        self.assertEqual(raised.exception.code, "MISSING_HEAD_SHA")

    def test_rejects_unsafe_refs(self) -> None:
        payload = {
            "number": 17,
            "baseRefName": "main",
            "headRefName": "../escape",
            "commits": [{"oid": "1111111111111111111111111111111111111111"}],
        }

        with self.assertRaises(GitHubCliError) as raised:
            checkout_plan_from_pr_view(GitHubReference(owner="owner", repo="repo", number=17), payload)

        self.assertEqual(raised.exception.code, "INVALID_REF")


if __name__ == "__main__":
    unittest.main()
