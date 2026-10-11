"""Minimal native `fw run` execution path."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from forgeweave.contracts import EffectSet, PolicyOutcome, ToolSpec
from forgeweave.core import FinalReport, NativeAgentLoop, complete_repository_task
from forgeweave.models import FakeModelProvider, ModelChunk, OpenAICompatibleProvider
from forgeweave.policy import PolicyGateway, PolicyRule
from forgeweave.tools import ToolRegistry
from forgeweave.verify import build_verified_executor


@dataclass(frozen=True)
class NativeRunConfig:
    """CLI-provided native run settings for the first deterministic slice."""

    prompt: str
    provider: str = "fake"
    fake_response: str | None = None
    fake_tool_call: str | None = None
    as_json: bool = False
    dry_run: bool = False
    complete_report: bool = False
    task_id: str = "cli-task"
    verification_output_dir: Path | None = None
    modified_files: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    artifact_links: tuple[str, ...] = ()
    repo_root: Path | None = None
    snapshot_dir: Path | None = None
    targets: tuple[Path, ...] = ()
    config_hash: str | None = None
    retry_attempts: int = 3
    timeout_seconds: int = 60
    ruff_executable: str = "ruff"
    ruff_rules: tuple[str, ...] = ("ALL",)


@dataclass(frozen=True)
class NativeRunView:
    """Safe result projection for one native run."""

    stop_reason: str
    should_stop: bool
    text: str
    provider: str
    observations: tuple[dict[str, Any], ...]
    verified_dispatch_enabled: bool
    dry_run: bool
    final_report: FinalReport | None = None


def run_native_once(config: NativeRunConfig) -> NativeRunView:
    """Run one native loop turn with deterministic fake provider input."""

    if not config.prompt.strip():
        raise ValueError("prompt must not be blank")
    verified_executor = _verified_executor(config)
    provider = _provider(config)
    registry = _registry(_repo_root(config), dry_run=config.dry_run)
    loop = NativeAgentLoop(
        provider=provider,
        registry=registry,
        policy=PolicyGateway(
            policy_revision="policy-v1",
            rules=(PolicyRule(tool_name="write_text", outcome=PolicyOutcome.ALLOW, reason="cli run explicit write"),),
        ),
        task_id=config.task_id,
        attempt_id="cli-attempt-1",
        workspace_precondition_hash="sha256:cli-workspace",
        verified_executor=verified_executor,
    )
    result = loop.run_once(messages=[{"role": "user", "content": config.prompt}])
    final_report = _completion_report(config) if config.complete_report and result.stop_decision.should_stop else None
    return NativeRunView(
        stop_reason=result.stop_decision.reason.value,
        should_stop=result.stop_decision.should_stop,
        text=result.text,
        provider=config.provider,
        observations=tuple(result.observations),
        verified_dispatch_enabled=verified_executor is not None,
        dry_run=config.dry_run,
        final_report=final_report,
    )


def render_native_run(view: NativeRunView, *, as_json: bool) -> str:
    """Render one native run result."""

    if as_json:
        payload = asdict(view)
        if view.final_report is not None:
            payload["final_report"]["passed"] = view.final_report.passed
        return json.dumps(payload, sort_keys=True)
    lines = [f"Stop reason: {view.stop_reason}", f"Provider: {view.provider}"]
    if view.text:
        lines.append(f"Text: {view.text}")
    lines.append(f"Verified dispatch enabled: {str(view.verified_dispatch_enabled).lower()}")
    lines.append(f"Dry run: {str(view.dry_run).lower()}")
    if view.final_report is not None:
        lines.append(f"Final report passed: {str(view.final_report.passed).lower()}")
        lines.append(f"Checks run: {len(view.final_report.checks)}")
        if view.final_report.failed_checks:
            lines.append(f"Failed checks: {len(view.final_report.failed_checks)}")
        if view.final_report.risks:
            lines.append("Risks: " + "; ".join(view.final_report.risks))
    if view.observations:
        lines.append("Observations: " + json.dumps(view.observations, sort_keys=True))
    return "\n".join(lines)


def _provider(config: NativeRunConfig):
    if config.provider == "fake":
        return FakeModelProvider(_chunks(config))
    if config.provider == "openai-compatible":
        if config.fake_response is not None or config.fake_tool_call is not None:
            raise ValueError("fake response/tool-call options require --provider fake")
        return OpenAICompatibleProvider.from_env()
    raise ValueError(f"unsupported provider: {config.provider}")


def _completion_report(config: NativeRunConfig) -> FinalReport:
    output_dir = config.verification_output_dir or (_repo_root(config) / ".forgeweave" / "verification")
    return complete_repository_task(
        task_id=config.task_id,
        repo_root=_repo_root(config),
        output_dir=output_dir,
        modified_files=config.modified_files,
        risks=config.risks,
        artifact_links=config.artifact_links,
        timeout_seconds=config.timeout_seconds,
    ).report


def _chunks(config: NativeRunConfig) -> tuple[ModelChunk, ...]:
    if config.fake_tool_call is not None:
        return (
            ModelChunk(kind="tool_call", call_id="cli-call-1", content=config.fake_tool_call),
            ModelChunk(kind="done"),
        )
    return (ModelChunk(kind="text", content=config.fake_response or ""), ModelChunk(kind="done"))


def _verified_executor(config: NativeRunConfig):
    if config.snapshot_dir is None and not config.targets and config.config_hash is None:
        return None
    missing = []
    if config.repo_root is None:
        missing.append("repo_root")
    if config.snapshot_dir is None:
        missing.append("snapshot_dir")
    if not config.targets:
        missing.append("targets")
    if config.config_hash is None:
        missing.append("config_hash")
    if missing:
        raise ValueError("verified dispatch requires: " + ", ".join(missing))
    return build_verified_executor(
        repo_root=config.repo_root,
        snapshot_dir=config.snapshot_dir,
        targets=config.targets,
        config_hash=config.config_hash,
        retry_attempts=config.retry_attempts,
        timeout_seconds=config.timeout_seconds,
        ruff_executable=config.ruff_executable,
        ruff_rules=config.ruff_rules,
    )


def _repo_root(config: NativeRunConfig) -> Path:
    return (config.repo_root or Path.cwd()).resolve()


def _registry(root: Path, *, dry_run: bool = False) -> ToolRegistry:
    registry = ToolRegistry(catalog_version="tools-v1")
    registry.register(
        ToolSpec(
            name="write_text",
            description="Write UTF-8 text under the run repository root.",
            input_schema={
                "type": "object",
                "required": ["path", "content"],
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            },
            effects=EffectSet(writes=frozenset({"workspace"})),
            schema_version="write-text.v1",
        ),
        lambda arguments: _dry_run_write_text(root, arguments) if dry_run else _write_text(root, arguments),
    )
    return registry


def _write_text(root: Path, arguments: dict[str, Any]) -> str:
    target = _write_target(root, arguments)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(arguments["content"], encoding="utf-8")
    return str(target)


def _write_target(root: Path, arguments: dict[str, Any]) -> Path:
    target = (root / arguments["path"]).resolve()
    if root not in (target, *target.parents):
        raise ValueError("path escapes run root")
    return target


def _dry_run_write_text(root: Path, arguments: dict[str, Any]) -> str:
    target = _write_target(root, arguments)
    return f"dry-run: would write {target}"
