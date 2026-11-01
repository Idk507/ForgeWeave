"""Composition of the local, task-owned native CLI execution path."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from forgeweave.contracts import ActorKind, Event, EventKind, PolicyOutcome, TaskStatus, WorktreeState
from forgeweave.core.loop import NativeAgentLoop
from forgeweave.core.task_completion import complete_repository_task
from forgeweave.events import EventStore, ToolExecutionRecorder
from forgeweave.models import FakeModelProvider, ModelChunk
from forgeweave.policy import PolicyGateway, PolicyRule
from forgeweave.task import TaskProjectionBuilder, TaskStateMachine
from forgeweave.tools.files import WorkspacePathGuard, register_file_tools
from forgeweave.workspace import WorkspaceLockStore, WorkspaceManager, WorkspaceStore, assert_active_lease


def run_local_task(*, repo_root: Path, state_dir: Path, task_id: str, prompt: str,
                   allow_host_execution: bool, mode: str, allowed_paths: tuple[str, ...],
                   fake_tool_call: str | None, fake_response: str | None,
                   complete_report: bool, timeout_seconds: int) -> dict:
    """Run a bounded offline native task inside a persisted owned worktree.

    The explicit host-execution flag covers Git and repository test processes;
    it does not claim operating-system confinement.
    """
    if not allow_host_execution:
        raise ValueError("--allow-host-execution is required for unconfined Git and test processes")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", task_id):
        raise ValueError("task id must contain lowercase letters, digits and hyphens")
    if not prompt.strip() or timeout_seconds < 1:
        raise ValueError("a nonempty prompt and positive timeout are required")
    root, state = repo_root.resolve(), state_dir.resolve()
    if state == root or root in state.parents or state in root.parents:
        raise ValueError("state directory must be outside the repository and its ancestors")
    for path in allowed_paths:
        parts = Path(path).parts
        if not parts or Path(path).is_absolute() or any(p.lower() in (".", "..", ".git") or ":" in p for p in parts):
            raise ValueError("write paths must be safe relative repository paths")
        if parts[0].lower() == "tests" or Path(path).name.lower() in {"pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg"}:
            raise ValueError("verification inputs cannot be authorized for edits in this task mode")
        resolved = WorkspacePathGuard(root).resolve(path)
        relative = resolved.relative_to(root)
        if relative.parts[0].lower() == "tests" or relative.name.lower() in {"pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg"}:
            raise ValueError("verification inputs cannot be authorized for edits in this task mode")
    manager = WorkspaceManager(repository_root=root, worktree_root=state / "worktrees")
    # Validate before opening the state database or admitting the task.
    manager._ensure_clean_source()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    events = EventStore.open(state / "events.db")
    locks = WorkspaceLockStore.open(state / "locks.db")
    workspaces = WorkspaceStore.open(state / "workspaces.db")
    task = TaskStateMachine(events)
    attempt = f"attempt-{uuid4().hex}"
    record = None
    try:
        events.claim_task(task_id)
        task.create_task(task_id=task_id, title="Native coding task", attempt_id=attempt)
        task.transition(task_id, TaskStatus.PREPARING, reason="prepare owned worktree")
        worktree_path = state / "worktrees" / f"{task_id}-task"
        _worktree_event(events, task_id, attempt, {"phase": "intent", "repository": str(root),
                        "path": str(worktree_path), "base_commit": head, "branch": f"fw/{task_id}-task"})
        manager = WorkspaceManager(repository_root=root, worktree_root=state / "worktrees", lock_store=locks,
                                   lock_ttl_seconds=max(300, timeout_seconds + 60))
        record = manager.create_worktree(task_id=task_id, slug="task")
        if record.base_commit != head:
            raise RuntimeError("repository head changed during worktree creation; inspect preserved worktree")
        workspaces.record_worktree(worktree_id=task_id, task_id=task_id, repository_path=str(root),
            worktree_path=str(record.worktree_path), base_commit=record.base_commit, branch=record.branch,
            state=WorktreeState.ACTIVE)
        _worktree_event(events, task_id, attempt, {"phase": "created", "repository": str(root),
                        "path": str(record.worktree_path), "base_commit": head, "branch": record.branch})
        task.transition(task_id, TaskStatus.RUNNING, reason="start native loop")
        guard = WorkspacePathGuard(record.worktree_path)
        registry = register_file_tools(guard, catalog_version="tools-v1")
        rules = tuple(PolicyRule("replace_text", PolicyOutcome.ALLOW, "explicit workspace path",
                                 (("path", path),)) for path in allowed_paths) if mode == "implement" else ()
        rules += (PolicyRule("replace_text", PolicyOutcome.DENY, "write path not authorized"),)
        policy = PolicyGateway(policy_revision="native-cli-v1", rules=rules)
        if fake_tool_call:
            chunks = [ModelChunk(kind="tool_call", call_id="scripted-1", content=fake_tool_call), ModelChunk(kind="done")]
        else:
            chunks = [ModelChunk(kind="text", content=fake_response or "Inspection complete"), ModelChunk(kind="done")]
        loop = NativeAgentLoop(provider=FakeModelProvider(chunks), registry=registry, policy=policy,
            task_id=task_id, attempt_id=attempt, workspace_precondition_hash="sha256:" + sha256(head.encode()).hexdigest(),
            tool_execution_recorder=ToolExecutionRecorder(events),
            before_dispatch=lambda _call: assert_active_lease(locks, record.worktree_lock))
        if record.worktree_lock is None:
            raise RuntimeError("workspace lease unavailable")
        assert_active_lease(locks, record.worktree_lock)
        result = loop.run_once(messages=[{"role": "user", "content": prompt}])
        observations = [_jsonable(item) for item in result.observations]
        if any("error" in item for item in observations):
            task.transition(task_id, TaskStatus.FAILED, reason="tool request failed or was denied")
            stop = "failed"
            report = None
        else:
            # A scripted tool step is followed by a separate scripted final step.
            if fake_tool_call and fake_response:
                final = NativeAgentLoop(provider=FakeModelProvider([ModelChunk(kind="text", content=fake_response), ModelChunk(kind="done")]),
                    registry=registry, policy=policy, task_id=task_id, attempt_id=attempt,
                    workspace_precondition_hash="sha256:" + sha256(head.encode()).hexdigest()).run_once(
                        messages=[{"role": "user", "content": prompt}, {"role": "tool", "content": json.dumps(observations)}])
                text = final.text
            else:
                text = result.text
            task.transition(task_id, TaskStatus.VERIFYING, reason="check task completion")
            changed = subprocess.run(["git", "status", "--porcelain=v1"], cwd=record.worktree_path,
                                     capture_output=True, text=True, check=True).stdout.strip()
            report = None
            if changed and complete_report:
                modified = subprocess.run(["git", "diff", "--name-only", "-z"], cwd=record.worktree_path,
                                          capture_output=True, text=True, check=True).stdout
                untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                                           cwd=record.worktree_path, capture_output=True, text=True, check=True).stdout
                modified_files = tuple(sorted(set(filter(None, (modified + untracked).split("\0")))))
                completion = complete_repository_task(task_id=task_id, repo_root=record.worktree_path,
                    output_dir=state / "verification" / task_id, timeout_seconds=timeout_seconds, modified_files=modified_files)
                report = asdict(completion.report)
                report["passed"] = completion.passed
                success = completion.passed and (not fake_tool_call or bool(fake_response and fake_response.strip()))
            else:
                success = not changed and result.stop_decision.reason.value == "final_answer"
            task.transition(task_id, TaskStatus.COMPLETED if success else TaskStatus.FAILED,
                            reason="verification completed" if success else "verification required or failed")
            stop = "final_answer" if success else "failed"
        return {"task_id": task_id, "task_status": task.record(task_id).task.status.value,
                "worktree_path": str(record.worktree_path), "branch": record.branch, "base_commit": head,
                "isolation": "host-user", "stop_reason": stop, "text": locals().get("text", result.text),
                "observations": observations, "final_report": report}
    except BaseException:
        try:
            current = task.record(task_id).task.status
            if current in (TaskStatus.PREPARING, TaskStatus.RUNNING, TaskStatus.VERIFYING):
                task.transition(task_id, TaskStatus.FAILED, reason="native task interrupted")
        except Exception:
            pass
        raise
    finally:
        if record is not None and record.worktree_lock is not None:
            try:
                locks.release(record.worktree_lock)
            except Exception:
                pass
        workspaces.close()
        locks.close()
        events.close()


def inspect_local_task(*, state_dir: Path, task_id: str) -> dict:
    """Read persisted task status and worktree ownership without executing tools."""
    events = EventStore.open(state_dir / "events.db")
    workspaces = WorkspaceStore.open(state_dir / "workspaces.db")
    try:
        projection = TaskProjectionBuilder(events).build(task_id)
        owned = workspaces.list_worktrees(task_id=task_id)
        return {"task_id": task_id, "task_status": projection.record.task.status.value,
                "worktree_path": owned[0].worktree_path if owned else None, "event_count": projection.event_count}
    finally:
        workspaces.close()
        events.close()


def _worktree_event(store: EventStore, task_id: str, attempt: str, payload: dict) -> None:
    ref = store.put_payload(payload)
    store.append(Event(event_id=f"evt-{uuid4().hex}", task_id=task_id, attempt_id=attempt, sequence=1,
                       actor=ActorKind.SYSTEM, kind=EventKind.WORKTREE_RECORDED, correlation_id=task_id, payload_ref=ref))


def _jsonable(value):
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
