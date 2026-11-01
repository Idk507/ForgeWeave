from __future__ import annotations

import unittest

from forgeweave.integrations.github import GitHubCliCommand, GitHubCliError, GitHubReference, build_gh_command, intake_review_comments

HEAD = "abcdefabcdefabcdefabcdefabcdefabcdef1234"


class GitHubReviewCommentIntakeTests(unittest.TestCase):
    def test_builds_read_only_review_comments_command(self) -> None:
        command = build_gh_command(GitHubCliCommand.PR_COMMENTS, GitHubReference(owner="owner", repo="repo", number=17))

        self.assertEqual(command, ("gh", "api", "repos/owner/repo/pulls/17/comments", "--paginate"))

    def test_maps_current_review_comment_to_plan_item(self) -> None:
        reference = GitHubReference(owner="owner", repo="repo", number=17)
        payload = [
            {
                "id": 10,
                "path": "src/app.py",
                "body": "Please handle the empty input case.",
                "user": {"login": "reviewer"},
                "commit_id": HEAD,
                "original_commit_id": HEAD,
                "line": 42,
                "original_line": 40,
                "html_url": "https://github.com/owner/repo/pull/17#discussion_r10",
            }
        ]

        intake = intake_review_comments(reference, payload, current_head_sha=HEAD)

        self.assertEqual(intake.repository, "owner/repo")
        self.assertEqual(intake.pull_number, 17)
        self.assertEqual(len(intake.comments), 1)
        self.assertEqual(intake.plan_items[0].path, "src/app.py")
        self.assertEqual(intake.plan_items[0].target_line, 42)
        self.assertFalse(intake.plan_items[0].stale)
        self.assertEqual(intake.plan_items[0].reason, "current")
        self.assertEqual(intake.plan_items[0].author, "reviewer")

    def test_marks_outdated_comment_as_stale_without_current_line(self) -> None:
        payload = [_comment(outdated=True)]

        intake = intake_review_comments(GitHubReference(owner="owner", repo="repo", number=17), payload, current_head_sha=HEAD)

        self.assertTrue(intake.plan_items[0].stale)
        self.assertIsNone(intake.plan_items[0].target_line)
        self.assertEqual(intake.plan_items[0].reason, "outdated")

    def test_marks_commit_mismatch_as_stale(self) -> None:
        payload = [_comment(commit_id="1111111111111111111111111111111111111111")]

        intake = intake_review_comments(GitHubReference(owner="owner", repo="repo", number=17), payload, current_head_sha=HEAD)

        self.assertTrue(intake.plan_items[0].stale)
        self.assertEqual(intake.plan_items[0].reason, "commit_mismatch")

    def test_rejects_unsafe_comment_path(self) -> None:
        payload = [_comment(path="../secrets.txt")]

        with self.assertRaises(GitHubCliError) as raised:
            intake_review_comments(GitHubReference(owner="owner", repo="repo", number=17), payload)

        self.assertEqual(raised.exception.code, "INVALID_REVIEW_PATH")

    def test_rejects_comment_without_line(self) -> None:
        payload = [_comment(line=None, original_line=None)]

        with self.assertRaises(GitHubCliError) as raised:
            intake_review_comments(GitHubReference(owner="owner", repo="repo", number=17), payload)

        self.assertEqual(raised.exception.code, "MISSING_REVIEW_LINE")

    def test_rejects_invalid_current_head_sha(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            intake_review_comments(GitHubReference(owner="owner", repo="repo", number=17), [_comment()], current_head_sha="bad")

        self.assertEqual(raised.exception.code, "INVALID_HEAD_SHA")


def _comment(*, path="src/app.py", line=10, original_line=9, commit_id=HEAD, outdated=False):
    return {
        "id": 1,
        "path": path,
        "body": "fix this",
        "user": {"login": "reviewer"},
        "commit_id": commit_id,
        "original_commit_id": HEAD,
        "line": line,
        "original_line": original_line,
        "outdated": outdated,
    }


if __name__ == "__main__":
    unittest.main()
