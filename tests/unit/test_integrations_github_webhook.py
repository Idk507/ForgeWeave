from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hmac
from hashlib import sha256
import unittest

from forgeweave.integrations.github import GitHubCliError, GitHubWebhookHeaders, GitHubWebhookReplayStore, verify_github_webhook


class GitHubWebhookTests(unittest.TestCase):
    def test_verifies_signature_and_returns_payload_hash(self) -> None:
        payload = b'{"action":"opened"}'
        secret = b"secret"
        headers = _headers(payload, secret, delivery_id="delivery-1", event="pull_request")
        received_at = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

        verified = verify_github_webhook(headers=headers, payload=payload, secret=secret, received_at=received_at, allowed_events={"pull_request"})

        self.assertEqual(verified.delivery_id, "delivery-1")
        self.assertEqual(verified.event, "pull_request")
        self.assertEqual(verified.received_at, received_at)
        self.assertEqual(verified.payload_sha256, "sha256:" + sha256(payload).hexdigest())

    def test_rejects_signature_mismatch(self) -> None:
        payload = b"{}"
        headers = GitHubWebhookHeaders(delivery_id="delivery-1", event="issues", signature_256="sha256=" + "0" * 64)

        with self.assertRaises(GitHubCliError) as raised:
            verify_github_webhook(headers=headers, payload=payload, secret=b"secret")

        self.assertEqual(raised.exception.code, "WEBHOOK_SIGNATURE_MISMATCH")

    def test_rejects_malformed_signature_header(self) -> None:
        headers = GitHubWebhookHeaders(delivery_id="delivery-1", event="issues", signature_256="sha1:bad")

        with self.assertRaises(GitHubCliError) as raised:
            verify_github_webhook(headers=headers, payload=b"{}", secret=b"secret")

        self.assertEqual(raised.exception.code, "INVALID_WEBHOOK_SIGNATURE")

    def test_rejects_unallowed_event(self) -> None:
        payload = b"{}"
        secret = b"secret"
        headers = _headers(payload, secret, delivery_id="delivery-1", event="workflow_run")

        with self.assertRaises(GitHubCliError) as raised:
            verify_github_webhook(headers=headers, payload=payload, secret=secret, allowed_events={"pull_request"})

        self.assertEqual(raised.exception.code, "WEBHOOK_EVENT_NOT_ALLOWED")

    def test_replay_store_rejects_duplicate_delivery_in_window(self) -> None:
        payload = b"{}"
        secret = b"secret"
        headers = _headers(payload, secret, delivery_id="delivery-1", event="issues")
        replay_store = GitHubWebhookReplayStore()
        received_at = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

        verify_github_webhook(headers=headers, payload=payload, secret=secret, received_at=received_at, replay_store=replay_store)
        with self.assertRaises(GitHubCliError) as raised:
            verify_github_webhook(headers=headers, payload=payload, secret=secret, received_at=received_at + timedelta(minutes=1), replay_store=replay_store)

        self.assertEqual(raised.exception.code, "WEBHOOK_REPLAY")

    def test_replay_store_allows_delivery_after_window_prune(self) -> None:
        payload = b"{}"
        secret = b"secret"
        headers = _headers(payload, secret, delivery_id="delivery-1", event="issues")
        replay_store = GitHubWebhookReplayStore()
        received_at = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

        verify_github_webhook(headers=headers, payload=payload, secret=secret, received_at=received_at, replay_store=replay_store, replay_window=timedelta(minutes=5))
        verified = verify_github_webhook(headers=headers, payload=payload, secret=secret, received_at=received_at + timedelta(minutes=6), replay_store=replay_store, replay_window=timedelta(minutes=5))

        self.assertEqual(verified.delivery_id, "delivery-1")

    def test_rejects_empty_secret(self) -> None:
        with self.assertRaises(GitHubCliError) as raised:
            verify_github_webhook(headers=GitHubWebhookHeaders(delivery_id="delivery-1", event="issues", signature_256="sha256=" + "0" * 64), payload=b"{}", secret=b"")

        self.assertEqual(raised.exception.code, "MISSING_WEBHOOK_SECRET")


def _headers(payload: bytes, secret: bytes, *, delivery_id: str, event: str) -> GitHubWebhookHeaders:
    signature = "sha256=" + hmac.new(secret, payload, sha256).hexdigest()
    return GitHubWebhookHeaders(delivery_id=delivery_id, event=event, signature_256=signature)


if __name__ == "__main__":
    unittest.main()
