from __future__ import annotations

import unittest

from forgeweave.integrations.github import (
    GitHubCliError,
    GitHubPublicationKind,
    GitHubReference,
    plan_branch_push,
    plan_deployment,
    plan_pr_create,
    plan_review_reply,
)


class GitHubPublicationPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = GitHubReference(owner="owner", repo="repo", number=17)

    def test_branch_push_plan_requires_approval_and_is_idempotent(self) -> None:
        first = plan_branch_push(reference=self.reference, local_branch="fw/task-1", remote_branch="fw/task-1")
        second = plan_branch_push(reference=self.reference, local_branch="fw/task-1", remote_branch="fw/task-1")

        self.assertEqual(first.kind, GitHubPublicationKind.BRANCH_PUSH)
        self.assertTrue(first.requires_approval)
        self.assertEqual(first.argv, ("git", "push", "origin", "fw/task-1:refs/heads/fw/task-1"))
        self.assertEqual(first.idempotency_key, second.idempotency_key)
        self.assertTrue(first.idempotency_key.startswith("github-publication:"))

    def test_pr_create_uses_body_file_and_safe_refs(self) -> None:
        plan = plan_pr_create(reference=self.reference, head="fw/task-1", base="main", title="Fix parser regression", body_file="C:/tmp/pr-body.md")

        self.assertEqual(plan.kind, GitHubPublicationKind.PR_CREATE)
        self.assertEqual(
            plan.argv,
            (
                "gh",
                "pr",
                "create",
                "--repo",
                "owner/repo",
                "--head",
                "fw/task-1",
                "--base",
                "main",
                "--title",
                "Fix parser regression",
                "--body-file",
                "C:/tmp/pr-body.md",
            ),
        )

    def test_review_reply_uses_api_post_with_input_file(self) -> None:
        plan = plan_review_reply(reference=self.reference, comment_id=99, body_file="reply.json")

        self.assertEqual(plan.kind, GitHubPublicationKind.REVIEW_REPLY)
        self.assertEqual(plan.argv, ("gh", "api", "repos/owner/repo/pulls/17/comments/99/replies", "--method", "POST", "--input", "reply.json"))

    def test_deployment_uses_api_post_with_environment_ref_and_payload_file(self) -> None:
        plan = plan_deployment(reference=self.reference, environment="staging", ref="fw/task-1", payload_file="deployment.json")

        self.assertEqual(plan.kind, GitHubPublicationKind.DEPLOYMENT)
        self.assertEqual(
            plan.argv,
            (
                "gh",
                "api",
                "repos/owner/repo/deployments",
                "--method",
                "POST",
                "--field",
                "environment=staging",
                "--field",
                "ref=fw/task-1",
                "--input",
                "deployment.json",
            ),
        )

    def test_rejects_unsafe_publication_ref(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_branch_push(reference=self.reference, local_branch="../escape")

        self.assertEqual(raised.exception.code, "INVALID_PUBLICATION_REF")

    def test_rejects_empty_pr_title(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_pr_create(reference=self.reference, head="fw/task", base="main", title="   ", body_file="body.md")

        self.assertEqual(raised.exception.code, "INVALID_PR_TITLE")

    def test_rejects_body_file_that_looks_like_option(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_review_reply(reference=self.reference, comment_id=1, body_file="--raw-field=body=oops")

        self.assertEqual(raised.exception.code, "INVALID_BODY_FILE")

    def test_rejects_invalid_comment_id(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            plan_review_reply(reference=self.reference, comment_id=0, body_file="reply.json")

        self.assertEqual(raised.exception.code, "INVALID_COMMENT_ID")


if __name__ == "__main__":
    unittest.main()
