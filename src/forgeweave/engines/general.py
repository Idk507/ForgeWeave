"""Optional delegated engines. Vendor SDKs load lazily; this module has no vendor name.

JSON-RPC stdio adapter uses `deepseek-harness-sdk` (extra `engine-deepseek`).
App-server adapter uses `openai-codex` (extra `engine-codex`).
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import threading
from typing import Any, Callable

from ._events import import_events
from .contracts import (
    CancelToken,
    EngineRequest,
    EngineResult,
    EngineUnavailable,
    IsolationLevel,
    OnEvent,
)


class JsonRpcEngine:
    """Runs one task through `dsh --profile sdk` with the full sandboxed tool roster."""

    name = "jsonrpc"
    isolation = IsolationLevel.DELEGATED_UNMEDIATED

    def __init__(
        self,
        *,
        profile: str = "sdk",
        patches: tuple[str, ...] = (),
        upload_disabled_attested: bool = False,
        harness_factory: Callable[..., Any] | None = None,
    ) -> None:
        # `sdk-minimal` pins danger-full-access, so the sandboxed `sdk` profile is the default.
        self._profile = profile
        self._patches = patches
        # The session-log upload patch must be confirmed against `dsh --dump-config` (spike M0.14a).
        self._upload_disabled_attested = upload_disabled_attested
        self._factory = harness_factory

    def check_available(self) -> None:
        if self._factory is None:
            self._check_official_sdk()
        if not self._upload_disabled_attested:
            raise EngineUnavailable(
                "session-log upload is not attested as disabled; refusing to send task data to the runtime"
            )

    @staticmethod
    def _check_official_sdk() -> None:
        if importlib.util.find_spec("deepseek_harness_runtime") is None:
            raise EngineUnavailable(
                "deepseek-harness-runtime-bin is not installed; the importable name "
                "'deepseek_harness' may belong to the unrelated 'deepseek-harness' package"
            )
        try:
            module = importlib.import_module("deepseek_harness")
        except ImportError as exc:
            raise EngineUnavailable("deepseek-harness-sdk is not installed") from exc
        cls = getattr(module, "DeepSeekHarness", None)
        if cls is None or "dsh_home" not in inspect.signature(cls.__init__).parameters:
            raise EngineUnavailable("installed 'deepseek_harness' is not the official deepseek-harness-sdk")

    def _create(self, request: EngineRequest) -> Any:
        factory = self._factory
        if factory is None:
            factory = importlib.import_module("deepseek_harness").DeepSeekHarness
        kwargs: dict[str, Any] = {
            "dsh_home": str(request.engine_home),
            "cwd": str(request.worktree),
            "profile": self._profile,
            "patches": self._patches,
        }
        if request.provider:
            kwargs["provider"] = request.provider
        if request.model:
            kwargs["model"] = request.model
        return factory(**kwargs)

    async def run(self, request: EngineRequest, on_event: OnEvent, cancel: CancelToken) -> EngineResult:
        self.check_available()
        harness = self._create(request)
        job = asyncio.create_task(asyncio.to_thread(harness.run, request.prompt, session_id=request.session_id))
        try:
            while not job.done():
                if cancel.cancelled:
                    await asyncio.to_thread(harness.close)
                    return EngineResult(status="cancelled")
                await asyncio.wait({job}, timeout=0.1)
            try:
                result = job.result()
            except Exception as exc:  # engine failures are observations, not crashes
                return EngineResult(status="failed", finish_reason=f"exception: {type(exc).__name__}")
            events = import_events(self.name, list(getattr(result, "events", []) or []), "session-event")
            for event in events:
                on_event(event)
            reason = getattr(result, "finish_reason", None)
            return EngineResult(
                status="completed" if reason == "completed" else "failed",
                claimed_final_response=getattr(result, "final_response", None),
                finish_reason=reason,
                engine_session_id=getattr(result, "session_id", None),
                events=events,
            )
        finally:
            if not cancel.cancelled:
                await asyncio.to_thread(harness.close)


class AppServerEngine:
    """Runs one task in an app-server thread confined to the task worktree by the runtime sandbox."""

    name = "appserver"
    isolation = IsolationLevel.DELEGATED_UNMEDIATED

    def __init__(self, *, approval_mode: Any = None, client_factory: Any = None, sandbox: Any = None) -> None:
        # The SDK default is ApprovalMode.auto_review; the caller must choose a mode explicitly.
        self._approval_mode = approval_mode
        self._client_factory = client_factory
        self._sandbox = sandbox

    def check_available(self) -> None:
        if self._client_factory is None and importlib.util.find_spec("openai_codex") is None:
            raise EngineUnavailable("openai-codex is not installed")
        if self._approval_mode is None:
            raise EngineUnavailable("an explicit approval_mode is required; the SDK default auto-reviews")

    async def run(self, request: EngineRequest, on_event: OnEvent, cancel: CancelToken) -> EngineResult:
        self.check_available()
        holder: dict[str, Any] = {}
        started = threading.Event()

        def work() -> Any:
            factory = self._client_factory or importlib.import_module("openai_codex").Codex
            sandbox = self._sandbox
            if sandbox is None:
                sandbox = importlib.import_module("openai_codex").Sandbox.workspace_write
            with factory() as client:
                kwargs: dict[str, Any] = {
                    "cwd": str(request.worktree),
                    "sandbox": sandbox,
                    "approval_mode": self._approval_mode,
                }
                if request.model:
                    kwargs["model"] = request.model
                thread = client.thread_start(**kwargs)
                turn = thread.turn(request.prompt)
                holder["turn"] = turn
                holder["thread_id"] = getattr(thread, "id", None)
                started.set()
                return turn.run()

        job = asyncio.create_task(asyncio.to_thread(work))
        interrupted = False
        while not job.done():
            if cancel.cancelled and not interrupted and started.is_set():
                interrupted = True
                await asyncio.to_thread(holder["turn"].interrupt)
            await asyncio.wait({job}, timeout=0.1)
        try:
            result = job.result()
        except Exception as exc:  # engine failures are observations, not crashes
            status = "cancelled" if interrupted else "failed"
            return EngineResult(status=status, finish_reason=f"exception: {type(exc).__name__}")

        events = import_events(self.name, list(getattr(result, "items", []) or []), "item")
        for event in events:
            on_event(event)
        raw_status = str(getattr(result, "status", "")).lower()
        if interrupted or "interrupt" in raw_status:
            status = "cancelled"
        else:
            status = "completed" if "completed" in raw_status else "failed"
        return EngineResult(
            status=status,
            claimed_final_response=getattr(result, "final_response", None),
            finish_reason=raw_status or None,
            engine_session_id=holder.get("thread_id"),
            events=events,
        )
