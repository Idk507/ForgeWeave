from __future__ import annotations

import unittest

from forgeweave.integrations.github import ConflictRisk, GitHubCliError, GitIntegrationKind, plan_branch_merge, plan_cherry_pick, plan_signed_commit


class GitIntegrationPlanTests(unittest.TestCase):
    def test_signed_commit_plan_requires_approval_and_signing(self) -> None:
        plan = plan_signed_commit(message="Fix parser regression")

        self.assertEqual(plan.kind, GitIntegrationKind.COMMIT)
        self.assertEqual(plan.argv, ("git", "commit", "-a", "-S", "-m", "Fix parser regression"))
        self.assertEqual(plan.preflight_argv, (("git", "status", "--porcelain=v1"),))
        self.assertTrue(plan.requires_approval)
        self.assertTrue(plan.signed_commit_required)
        self.assertEqual(plan.conflict_risk, ConflictRisk.LOW)
        self.assertTrue(plan.idempotency_key.startswith("git-integration:"))

    def test_unsigned_commit_plan_is_explicit(self) -> None:
        plan = plan_signed_commit(message="WIP checkpoint", sign=False, all_tracked=False)

        self.assertEqual(plan.argv, ("git", "commit", "-m", "WIP checkpoint"))
        self.assertFalse(plan.signed_commit_required)

    def test_branch_merge_plan_includes_ancestry_and_merge_tree_preflight(self) -> None:
        plan = plan_branch_merge(base_branch="main", source_branch="fw/task-1")

        self.assertEqual(plan.kind, GitIntegrationKind.MERGE)
        self.assertEqual(plan.argv, ("git", "merge", "--no-ff", "--no-commit", "fw/task-1"))
        self.assertEqual(
            plan.preflight_argv,
            (("git", "merge-base", "--is-ancestor", "main", "fw/task-1"), ("git", "merge-tree", "main", "fw/task-1")),
        )
        self.assertEqual(plan.conflict_risk, ConflictRisk.NEEDS_PREFLIGHT)
        self.assertTrue(plan.signed_commit_required)

    def test_cherry_pick_plan_requires_exact_commit(self) -> None:
        plan = plan_cherry_pick(commit_sha="ABCDEFabcdefABCDEFabcdefABCDEFabcdef1234")

        self.assertEqual(plan.kind, GitIntegrationKind.CHERRY_PICK)
        self.assertEqual(plan.argv, ("git", "cherry-pick", "--no-commit", "abcdefabcdefabcdefabcdefabcdefabcdef1234"))
        self.assertEqual(plan.preflight_argv, (("git", "cat-file", "-e", "abcdefabcdefabcdefabcdefabcdefabcdef1234^{commit}"),))

    def test_rejects_unsafe_branch_ref(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_branch_merge(base_branch="main", source_branch="../escape")

        self.assertEqual(raised.exception.code, "INVALID_GIT_REF")

    def test_rejects_invalid_commit_sha(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_cherry_pick(commit_sha="not-a-sha")

        self.assertEqual(raised.exception.code, "INVALID_COMMIT_SHA")

    def test_rejects_blank_commit_message(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_signed_commit(message="   ")

        self.assertEqual(raised.exception.code, "INVALID_COMMIT_MESSAGE")


if __name__ == "__main__":
    unittest.main()
