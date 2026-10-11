"""Behavior tests for the engines package using fake vendor SDK objects (no vendor install needed)."""

from __future__ import annotations

import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from forgeweave.engines import (
    CancelToken,
    EngineEvent,
    EngineRequest,
    EngineUnavailable,
    IsolationLevel,
    get_engine,
    validate_request,
)
from forgeweave.engines.general import AppServerEngine, JsonRpcEngine


def make_request(root: Path, **overrides: object) -> EngineRequest:
    checkout = root / "repo"
    worktree = root / "repo-wt"
    home = root / "engine-home"
    for p in (checkout, worktree, home):
        p.mkdir(exist_ok=True)
    data: dict[str, object] = dict(
        task_id="t1",
        attempt_id="a1",
        session_id="s1",
        prompt="fix the bug",
        worktree=worktree,
        original_checkout=checkout,
        engine_home=home,
        isolation=IsolationLevel.DELEGATED_UNMEDIATED,
        delegated_opt_in=True,
    )
    data.update(overrides)
    return EngineRequest(**data)  # type: ignore[arg-type]


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_valid_request_has_no_violations(self) -> None:
        self.assertEqual(validate_request(make_request(self.root)), [])

    def test_original_checkout_is_refused(self) -> None:
        req = make_request(self.root)
        same = req.model_copy(update={"worktree": req.original_checkout})
        self.assertTrue(any("original checkout" in p for p in validate_request(same)))

    def test_delegated_requires_opt_in_and_forbids_external_effects(self) -> None:
        req = make_request(self.root, delegated_opt_in=False, requested_effects=frozenset({"browser", "publish"}))
        problems = validate_request(req)
        self.assertTrue(any("opt-in" in p for p in problems))
        self.assertTrue(any("browser" in p and "publish" in p for p in problems))

    def test_engine_home_inside_worktree_is_refused(self) -> None:
        req = make_request(self.root)
        inner = req.worktree / ".dsh"
        inner.mkdir()
        bad = req.model_copy(update={"engine_home": inner})
        self.assertTrue(any("outside the task worktree" in p for p in validate_request(bad)))

    def test_disallowed_provider_is_refused(self) -> None:
        req = make_request(self.root, provider="deepseek-official")
        self.assertTrue(validate_request(req, allowed_providers=frozenset({"openai"})))


class ContractTests(unittest.TestCase):
    def test_engine_events_cannot_be_marked_trusted(self) -> None:
        with self.assertRaises(ValidationError):
            EngineEvent(engine="x", sequence=0, kind="k", trusted=True)  # type: ignore[arg-type]

    def test_native_is_not_an_engine(self) -> None:
        with self.assertRaises(ValueError):
            get_engine("native")

    def test_unknown_engine(self) -> None:
        with self.assertRaises(EngineUnavailable):
            get_engine("nope")

    def test_registry_uses_generic_engine_names(self) -> None:
        jsonrpc = get_engine("jsonrpc", harness_factory=FakeHarness, upload_disabled_attested=True)
        appserver = get_engine("appserver", approval_mode="manual", client_factory=object())
        self.assertIsInstance(jsonrpc, JsonRpcEngine)
        self.assertIsInstance(appserver, AppServerEngine)
        with self.assertRaises(EngineUnavailable):
            get_engine("deepseek")
        with self.assertRaises(EngineUnavailable):
            get_engine("codex")


class FakeHarness:
    closed = False

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def run(self, prompt: str, session_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            session_id=session_id,
            final_response="done",
            finish_reason="completed",
            events=[{"type": "turn/end"}],
        )

    def close(self) -> None:
        FakeHarness.closed = True


class JsonRpcEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_refuses_without_upload_attestation(self) -> None:
        with self.assertRaises(EngineUnavailable):
            JsonRpcEngine(harness_factory=FakeHarness).check_available()

    def test_unavailable_when_official_sdk_missing(self) -> None:
        # No vendor packages are installed in the test environment.
        with self.assertRaises(EngineUnavailable):
            JsonRpcEngine(upload_disabled_attested=True).check_available()

    def test_run_imports_untrusted_events_and_claim_is_not_authoritative(self) -> None:
        engine = JsonRpcEngine(harness_factory=FakeHarness, upload_disabled_attested=True)
        seen: list[EngineEvent] = []
        result = asyncio.run(engine.run(make_request(self.root), seen.append, CancelToken()))
        self.assertEqual(result.status, "completed")
        self.assertFalse(result.authoritative)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].trusted)

    def test_uses_sandboxed_profile_and_task_scoped_home(self) -> None:
        captured: dict[str, object] = {}

        class Capturing(FakeHarness):
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)
                super().__init__(**kwargs)

        engine = JsonRpcEngine(harness_factory=Capturing, upload_disabled_attested=True)
        req = make_request(self.root)
        asyncio.run(engine.run(req, lambda e: None, CancelToken()))
        self.assertEqual(captured["profile"], "sdk")
        self.assertEqual(captured["dsh_home"], str(req.engine_home))
        self.assertEqual(captured["cwd"], str(req.worktree))


class FakeTurn:
    def __init__(self, blocking: bool) -> None:
        self._blocking = blocking
        self._stop = threading.Event()
        self.interrupted = False

    def run(self) -> SimpleNamespace:
        if self._blocking:
            self._stop.wait(timeout=5)
        status = "interrupted" if self.interrupted else "completed"
        return SimpleNamespace(status=status, final_response="ok", items=["item-1"])

    def interrupt(self) -> None:
        self.interrupted = True
        self._stop.set()


def fake_appserver(blocking: bool) -> object:
    class Thread:
        id = "thr_1"

        def turn(self, prompt: str) -> FakeTurn:
            return FakeTurn(blocking)

    class Client:
        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def thread_start(self, **kwargs: object) -> Thread:
            Client.kwargs = kwargs  # type: ignore[attr-defined]
            return Thread()

    fake_appserver.client = Client  # type: ignore[attr-defined]
    return Client


class AppServerEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_requires_explicit_approval_mode(self) -> None:
        with self.assertRaises(EngineUnavailable):
            AppServerEngine(client_factory=fake_appserver(False), sandbox="workspace-write").check_available()

    def test_run_confines_to_worktree_and_imports_events(self) -> None:
        client = fake_appserver(False)
        engine = AppServerEngine(approval_mode="manual", client_factory=client, sandbox="workspace-write")
        req = make_request(self.root)
        result = asyncio.run(engine.run(req, lambda e: None, CancelToken()))
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.engine_session_id, "thr_1")
        self.assertEqual(client.kwargs["cwd"], str(req.worktree))  # type: ignore[attr-defined]
        self.assertEqual(client.kwargs["sandbox"], "workspace-write")  # type: ignore[attr-defined]
        self.assertFalse(result.events[0].trusted)

    def test_cancellation_interrupts_running_turn(self) -> None:
        engine = AppServerEngine(approval_mode="manual", client_factory=fake_appserver(True), sandbox="workspace-write")
        cancel = CancelToken()

        async def scenario() -> object:
            task = asyncio.create_task(engine.run(make_request(self.root), lambda e: None, cancel))
            await asyncio.sleep(0.3)
            cancel.cancel()
            return await asyncio.wait_for(task, timeout=5)

        result = asyncio.run(scenario())
        self.assertEqual(result.status, "cancelled")  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
