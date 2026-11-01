"""Signed GitHub webhook verification contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hmac
from hashlib import sha256
import re

from .gh import GitHubCliError

_DELIVERY_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_EVENT_RE = re.compile(r"[a-z0-9_.-]{1,64}")
_SIGNATURE_PREFIX = "sha256="


@dataclass(frozen=True)
class GitHubWebhookHeaders:
    """Normalized headers required to verify a GitHub webhook delivery."""

    delivery_id: str
    event: str
    signature_256: str


@dataclass(frozen=True)
class GitHubWebhookVerification:
    """Evidence returned after a signed webhook passes local verification."""

    delivery_id: str
    event: str
    received_at: datetime
    payload_sha256: str


class GitHubWebhookReplayStore:
    """In-memory delivery replay guard for tests and local single-process use."""

    def __init__(self) -> None:
        self._seen: dict[str, datetime] = {}

    def check_and_record(self, delivery_id: str, *, received_at: datetime, replay_window: timedelta) -> None:
        self.prune(now=received_at, replay_window=replay_window)
        if delivery_id in self._seen:
            raise GitHubCliError("WEBHOOK_REPLAY", "GitHub webhook delivery was already accepted in the replay window")
        self._seen[delivery_id] = received_at

    def prune(self, *, now: datetime, replay_window: timedelta) -> None:
        cutoff = now - replay_window
        self._seen = {delivery_id: seen_at for delivery_id, seen_at in self._seen.items() if seen_at >= cutoff}


def verify_github_webhook(
    *,
    headers: GitHubWebhookHeaders,
    payload: bytes,
    secret: bytes,
    received_at: datetime | None = None,
    replay_store: GitHubWebhookReplayStore | None = None,
    replay_window: timedelta = timedelta(minutes=10),
    allowed_events: set[str] | None = None,
) -> GitHubWebhookVerification:
    """Verify a GitHub webhook signature and replay boundary."""

    now = _utc(received_at or datetime.now(UTC))
    _validate_headers(headers)
    if not secret:
        raise GitHubCliError("MISSING_WEBHOOK_SECRET", "GitHub webhook secret must not be empty")
    if replay_window.total_seconds() < 1:
        raise GitHubCliError("INVALID_REPLAY_WINDOW", "GitHub webhook replay window must be positive")
    if allowed_events is not None and headers.event not in allowed_events:
        raise GitHubCliError("WEBHOOK_EVENT_NOT_ALLOWED", "GitHub webhook event is not allowed for this receiver")
    expected = _SIGNATURE_PREFIX + hmac.new(secret, payload, sha256).hexdigest()
    if not hmac.compare_digest(expected, headers.signature_256):
        raise GitHubCliError("WEBHOOK_SIGNATURE_MISMATCH", "GitHub webhook signature does not match payload")
    if replay_store is not None:
        replay_store.check_and_record(headers.delivery_id, received_at=now, replay_window=replay_window)
    return GitHubWebhookVerification(
        delivery_id=headers.delivery_id,
        event=headers.event,
        received_at=now,
        payload_sha256="sha256:" + sha256(payload).hexdigest(),
    )


def _validate_headers(headers: GitHubWebhookHeaders) -> None:
    if not _DELIVERY_RE.fullmatch(headers.delivery_id):
        raise GitHubCliError("INVALID_DELIVERY_ID", "GitHub webhook delivery id is missing or unsafe")
    if not _EVENT_RE.fullmatch(headers.event):
        raise GitHubCliError("INVALID_WEBHOOK_EVENT", "GitHub webhook event is missing or unsafe")
    if not headers.signature_256.startswith(_SIGNATURE_PREFIX):
        raise GitHubCliError("INVALID_WEBHOOK_SIGNATURE", "GitHub webhook signature must use sha256")
    digest = headers.signature_256[len(_SIGNATURE_PREFIX) :]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise GitHubCliError("INVALID_WEBHOOK_SIGNATURE", "GitHub webhook signature digest is malformed")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
