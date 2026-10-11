"""Minimal argparse-based ForgeWeave CLI."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr
import json
from pathlib import Path
import sys
from typing import Sequence, TextIO

from forgeweave.cli.config import current_config_view, render_config
from forgeweave.cli.report import render_final_report_from_files
from forgeweave.cli.run import NativeRunConfig, render_native_run, run_native_once
from forgeweave.cli.slash import parse_slash_command, render_slash_command
from forgeweave.cli.status import TaskStatusView, render_task_status, task_status_from_event_store
from forgeweave.cli.task import (
    cancel_task_from_event_store,
    render_task_cancel,
    render_task_diff,
    render_task_resume,
    resume_task_from_event_store,
    task_diff_from_repo,
)
from forgeweave.cli.workflow import (
    admit_workflow_run_from_file,
    render_workflow_list,
    render_workflow_status,
    render_workflow_template,
    render_workflow_template_list,
    render_workflow_tick,
    render_workflow_run_admission,
    render_workflow_validation,
    resume_workflow_run_from_store,
    validate_workflow_definition_file,
    workflow_executors_for_cli_tick,
    workflow_inputs_from_json,
    workflow_list_from_store,
    workflow_status_from_store,
    workflow_tick_from_store,
    workflow_template_list_view,
    workflow_template_view,
)
from forgeweave.cli.verify import (
    render_selected_verification_run,
    render_verification_selection,
    render_verified_dispatch_config,
    selected_verification_run_view,
    verification_selection_view,
    verified_dispatch_config_view,
)


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Run the minimal CLI and return a process-style exit code."""

    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    parser = _build_parser()
    try:
        with redirect_stderr(errors):
            args = parser.parse_args(list(argv) if argv is not None else None)
        rendered = _dispatch(args)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    except KeyboardInterrupt:
        print("cancelled: keyboard interrupt", file=errors)
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=errors)
        return 1

    if rendered:
        print(rendered, file=output)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fw", description="ForgeWeave local coding agent CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run one deterministic native loop turn")
    prompt_group = run.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="User prompt for the native run")
    prompt_group.add_argument("--prompt-file", help="UTF-8 file containing the user prompt")
    run.add_argument("--provider", choices=("fake", "openai-compatible"), default="fake", help="Model provider for this run")
    run.add_argument("--fake-response", help="Deterministic text response for local testing")
    tool_call_group = run.add_mutually_exclusive_group()
    tool_call_group.add_argument("--fake-tool-call", help="Deterministic ForgeWeave tool-call JSON for local testing")
    tool_call_group.add_argument("--fake-tool-call-file", help="UTF-8 file containing deterministic ForgeWeave tool-call JSON")
    run.add_argument("--repo-root", help="Repository root for tool execution and verified dispatch")
    run.add_argument("--snapshot-dir", help="Directory for Git patch snapshots")
    run.add_argument("--target", action="append", dest="targets", help="Analyzer target path; repeatable")
    run.add_argument("--config-hash", help="Hash of effective analyzer configuration")
    run.add_argument("--retry-attempts", type=int, default=3, help="Repair retry budget for code regressions")
    run.add_argument("--timeout-seconds", type=int, default=60, help="Analyzer timeout in seconds")
    run.add_argument("--ruff-executable", default="ruff", help="Ruff executable name or path")
    run.add_argument("--ruff-rule", action="append", dest="ruff_rules", help="Ruff rule selector; repeatable, defaults to ALL")
    run.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")
    run.add_argument("--output-file", help="Write rendered run output to a UTF-8 file instead of stdout")
    run.add_argument("--dry-run", action="store_true", help="Validate and observe tool calls without applying workspace writes")
    run.add_argument("--complete-report", action="store_true", help="Run selected verification after a stopping response and attach the final report")
    run.add_argument("--task-id", default="cli-task", help="Task id for loop, verification and final-report evidence")
    run.add_argument("--verification-output-dir", help="Directory for completion verification output artifacts")
    run.add_argument("--modified-file", action="append", dest="modified_files", help="Modified file path for the completion report; repeatable")
    run.add_argument("--risk", action="append", dest="risks", help="Open risk for the completion report; repeatable")
    run.add_argument("--artifact", action="append", dest="artifact_links", help="Artifact link for the completion report; repeatable")

    config = subcommands.add_parser("config", help="Inspect local configuration")
    config_subcommands = config.add_subparsers(dest="config_command", required=True)
    config_show = config_subcommands.add_parser("show", help="Show safe runtime configuration")
    config_show.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    verify = subcommands.add_parser("verify", help="Inspect verification configuration")
    verify_subcommands = verify.add_subparsers(dest="verify_command", required=True)
    verify_config = verify_subcommands.add_parser("config", help="Validate verified-dispatch configuration")
    verify_config.add_argument("--repo-root", required=True, help="Repository root for analyzer execution")
    verify_config.add_argument("--snapshot-dir", required=True, help="Directory for Git patch snapshots")
    verify_config.add_argument("--target", action="append", required=True, dest="targets", help="Analyzer target path; repeatable")
    verify_config.add_argument("--config-hash", required=True, help="Hash of effective analyzer configuration")
    verify_config.add_argument("--retry-attempts", type=int, default=3, help="Repair retry budget for code regressions")
    verify_config.add_argument("--timeout-seconds", type=int, default=60, help="Analyzer timeout in seconds")
    verify_config.add_argument("--ruff-executable", default="ruff", help="Ruff executable name or path")
    verify_config.add_argument("--ruff-rule", action="append", dest="ruff_rules", help="Ruff rule selector; repeatable, defaults to ALL")
    verify_config.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    verify_select = verify_subcommands.add_parser("select", help="Select verification commands from repository config without running them")
    verify_select.add_argument("--repo-root", required=True, help="Repository root to inspect")
    verify_select.add_argument("--environment-profile-hash", default="sha256:local", help="Environment profile hash to attach to commands")
    verify_select.add_argument("--timeout-seconds", type=int, default=60, help="Timeout seconds for selected commands")
    verify_select.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    verify_run_selected = verify_subcommands.add_parser("run-selected", help="Select and run repository verification commands")
    verify_run_selected.add_argument("--task-id", required=True, help="Task id for captured verification evidence")
    verify_run_selected.add_argument("--repo-root", required=True, help="Repository root to inspect and verify")
    verify_run_selected.add_argument("--output-dir", required=True, help="Directory for verification output artifacts")
    verify_run_selected.add_argument("--environment-profile-hash", default="sha256:local", help="Environment profile hash to attach to commands")
    verify_run_selected.add_argument("--timeout-seconds", type=int, default=60, help="Timeout seconds for selected commands")
    verify_run_selected.add_argument("--output-cap-bytes", type=int, default=64000, help="Combined stdout/stderr cap for each command")
    verify_run_selected.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    task = subcommands.add_parser("task", help="Inspect task state")
    task_subcommands = task.add_subparsers(dest="task_command", required=True)
    task_status = task_subcommands.add_parser("status", help="Show a task status projection")
    task_source = task_status.add_mutually_exclusive_group(required=True)
    task_source.add_argument("--task-file", help="Path to a task status projection JSON file")
    task_source.add_argument("--event-store", help="Path to a ForgeWeave SQLite event store")
    task_status.add_argument("--task-id", help="Task id to project from --event-store")
    task_status.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    task_resume = task_subcommands.add_parser("resume", help="Resume a failed task after restart reconciliation")
    task_resume.add_argument("--event-store", required=True, help="Path to a ForgeWeave SQLite event store")
    task_resume.add_argument("--task-id", required=True, help="Task id to resume")
    task_resume.add_argument("--recovered-attempt-id", required=True, help="Failed attempt id to reconcile before resume")
    task_resume.add_argument("--new-attempt-id", required=True, help="New attempt id to create when recovery is safe")
    task_resume.add_argument("--evidence", required=True, help="Restart/recovery evidence for reconciliation decisions")
    task_resume.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    task_cancel = task_subcommands.add_parser("cancel", help="Cancel a task through the event-store lifecycle")
    task_cancel.add_argument("--event-store", required=True, help="Path to a ForgeWeave SQLite event store")
    task_cancel.add_argument("--task-id", required=True, help="Task id to cancel")
    task_cancel.add_argument("--reason", required=True, help="Cancellation reason recorded in lifecycle validation")
    task_cancel.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    task_diff = task_subcommands.add_parser("diff", help="Show a bounded unstaged Git diff for a task repository")
    task_diff.add_argument("--repo-root", required=True, help="Explicit repository root containing .git")
    task_diff.add_argument("--max-bytes", type=int, default=200_000, help="Maximum UTF-8 bytes of patch output")
    task_diff.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    task_report = task_subcommands.add_parser("report", help="Render a structured final task report")
    task_report.add_argument("--task-id", required=True, help="Task id for the final report")
    task_report.add_argument("--modified-file", action="append", dest="modified_files", help="Modified file path; repeatable")
    task_report.add_argument("--verification-run-file", action="append", dest="verification_run_files", help="VerificationRun JSON file; repeatable")
    task_report.add_argument("--risk", action="append", dest="risks", help="Open risk; repeatable")
    task_report.add_argument("--artifact", action="append", dest="artifact_links", help="Artifact link; repeatable")
    task_report.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow = subcommands.add_parser("workflow", help="Inspect workflow state")
    workflow_subcommands = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_validate = workflow_subcommands.add_parser("validate", help="Validate a JSON workflow definition file")
    workflow_validate.add_argument("definition_file", help="Path to a JSON workflow definition file")
    workflow_validate.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow_list = workflow_subcommands.add_parser("list", help="List persisted workflow definitions and runs")
    workflow_list.add_argument("--workflow-store", required=True, help="Path to a ForgeWeave workflow SQLite store")
    workflow_list.add_argument("--workflow-id", help="Optional workflow id filter")
    workflow_list.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow_run = workflow_subcommands.add_parser("run", help="Admit a workflow run without executing steps")
    workflow_run.add_argument("definition_file", help="Path to a JSON workflow definition file")
    workflow_run.add_argument("--workflow-store", required=True, help="Path to a ForgeWeave workflow SQLite store")
    workflow_run.add_argument("--run-id", help="Optional explicit run id")
    workflow_run.add_argument("--input-json", help="Workflow input JSON object")
    workflow_run.add_argument("--input-file", help="Path to a workflow input JSON object")
    workflow_run.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow_resume = workflow_subcommands.add_parser("resume", help="Resume a failed or waiting workflow run")
    workflow_resume.add_argument("--workflow-store", required=True, help="Path to a ForgeWeave workflow SQLite store")
    workflow_resume.add_argument("--run-id", required=True, help="Workflow run id to resume")
    workflow_resume.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow_template = workflow_subcommands.add_parser("template", help="Inspect built-in workflow templates")
    workflow_template_subcommands = workflow_template.add_subparsers(dest="workflow_template_command", required=True)
    workflow_template_list = workflow_template_subcommands.add_parser("list", help="List built-in workflow templates")
    workflow_template_list.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")
    workflow_template_show = workflow_template_subcommands.add_parser("show", help="Show one built-in workflow template")
    workflow_template_show.add_argument("template_id", help="Built-in workflow template id")
    workflow_template_show.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow_tick = workflow_subcommands.add_parser("tick", help="Run one safe workflow scheduler tick")
    workflow_tick.add_argument("--workflow-store", required=True, help="Path to a ForgeWeave workflow SQLite store")
    workflow_tick.add_argument("--run-id", required=True, help="Workflow run id to advance")
    workflow_tick.add_argument("--max-ready-steps", type=int, help="Maximum ready steps to record in this tick")
    workflow_tick.add_argument("--enable-native-agent-executor", action="store_true", help="Run agent steps through the native-loop executor")
    workflow_tick.add_argument("--enable-tool-executor", action="store_true", help="Run tool steps through the policy-mediated tool executor")
    workflow_tick.add_argument("--fake-response", help="Deterministic native-agent text response for executor-enabled ticks")
    workflow_tick.add_argument("--fake-tool-call", help="Deterministic native-agent tool-call JSON for executor-enabled ticks")
    workflow_tick.add_argument("--repo-root", help="Repository root for workflow tool execution")
    workflow_tick.add_argument("--dry-run", action="store_true", help="Observe workflow tool writes without applying workspace changes")
    workflow_tick.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")

    workflow_status = workflow_subcommands.add_parser("status", help="Show a persisted workflow run status projection")
    workflow_status.add_argument("--workflow-store", required=True, help="Path to a ForgeWeave workflow SQLite store")
    workflow_status.add_argument("--run-id", required=True, help="Workflow run id to inspect")
    workflow_status.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")
    return parser


def _dispatch(args: argparse.Namespace) -> str:
    if args.command == "run":
        prompt = _run_prompt(args)
        slash_command = parse_slash_command(prompt)
        if slash_command is not None:
            return render_slash_command(slash_command, as_json=args.as_json)
        view = run_native_once(
            NativeRunConfig(
                prompt=prompt,
                provider=args.provider,
                fake_response=args.fake_response,
                fake_tool_call=_run_fake_tool_call(args),
                as_json=args.as_json,
                dry_run=args.dry_run,
                complete_report=args.complete_report,
                task_id=args.task_id,
                verification_output_dir=Path(args.verification_output_dir) if args.verification_output_dir else None,
                modified_files=tuple(args.modified_files or ()),
                risks=tuple(args.risks or ()),
                artifact_links=tuple(args.artifact_links or ()),
                repo_root=Path(args.repo_root) if args.repo_root else None,
                snapshot_dir=Path(args.snapshot_dir) if args.snapshot_dir else None,
                targets=tuple(Path(target) for target in (args.targets or ())),
                config_hash=args.config_hash,
                retry_attempts=args.retry_attempts,
                timeout_seconds=args.timeout_seconds,
                ruff_executable=args.ruff_executable,
                ruff_rules=tuple(args.ruff_rules or ("ALL",)),
            )
        )
        rendered = render_native_run(view, as_json=args.as_json)
        if args.output_file:
            _write_output_file(Path(args.output_file), rendered)
            return ""
        return rendered
    if args.command == "config" and args.config_command == "show":
        return render_config(current_config_view(), as_json=args.as_json)
    if args.command == "verify" and args.verify_command == "run-selected":
        view = selected_verification_run_view(
            task_id=args.task_id,
            repo_root=Path(args.repo_root),
            output_dir=Path(args.output_dir),
            environment_profile_hash=args.environment_profile_hash,
            timeout_seconds=args.timeout_seconds,
            output_cap_bytes=args.output_cap_bytes,
        )
        return render_selected_verification_run(view, as_json=args.as_json)
    if args.command == "verify" and args.verify_command == "select":
        view = verification_selection_view(
            repo_root=Path(args.repo_root),
            environment_profile_hash=args.environment_profile_hash,
            timeout_seconds=args.timeout_seconds,
        )
        return render_verification_selection(view, as_json=args.as_json)
    if args.command == "verify" and args.verify_command == "config":
        view = verified_dispatch_config_view(
            repo_root=Path(args.repo_root),
            snapshot_dir=Path(args.snapshot_dir),
            targets=tuple(Path(target) for target in args.targets),
            config_hash=args.config_hash,
            retry_attempts=args.retry_attempts,
            timeout_seconds=args.timeout_seconds,
            ruff_executable=args.ruff_executable,
            ruff_rules=tuple(args.ruff_rules or ("ALL",)),
        )
        return render_verified_dispatch_config(view, as_json=args.as_json)
    if args.command == "task" and args.task_command == "report":
        return render_final_report_from_files(
            task_id=args.task_id,
            modified_files=tuple(args.modified_files or ()),
            verification_run_files=tuple(Path(path) for path in (args.verification_run_files or ())),
            risks=tuple(args.risks or ()),
            artifact_links=tuple(args.artifact_links or ()),
            as_json=args.as_json,
        )
    if args.command == "task" and args.task_command == "diff":
        view = task_diff_from_repo(Path(args.repo_root), max_bytes=args.max_bytes)
        return render_task_diff(view, as_json=args.as_json)
    if args.command == "task" and args.task_command == "cancel":
        view = cancel_task_from_event_store(Path(args.event_store), task_id=args.task_id, reason=args.reason)
        return render_task_cancel(view, as_json=args.as_json)
    if args.command == "task" and args.task_command == "resume":
        view = resume_task_from_event_store(
            Path(args.event_store),
            task_id=args.task_id,
            recovered_attempt_id=args.recovered_attempt_id,
            new_attempt_id=args.new_attempt_id,
            evidence=args.evidence,
        )
        return render_task_resume(view, as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "validate":
        view = validate_workflow_definition_file(Path(args.definition_file))
        return render_workflow_validation(view, as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "list":
        view = workflow_list_from_store(Path(args.workflow_store), workflow_id=args.workflow_id)
        return render_workflow_list(view, as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "run":
        view = admit_workflow_run_from_file(
            Path(args.workflow_store),
            Path(args.definition_file),
            inputs=workflow_inputs_from_json(args.input_json, Path(args.input_file) if args.input_file else None),
            run_id=args.run_id,
        )
        return render_workflow_run_admission(view, as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "resume":
        view = resume_workflow_run_from_store(Path(args.workflow_store), run_id=args.run_id)
        return render_workflow_run_admission(view, as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "template":
        if args.workflow_template_command == "list":
            return render_workflow_template_list(workflow_template_list_view(), as_json=args.as_json)
        if args.workflow_template_command == "show":
            return render_workflow_template(workflow_template_view(args.template_id), as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "tick":
        executors = workflow_executors_for_cli_tick(
            enable_native_agent=args.enable_native_agent_executor,
            enable_tool=args.enable_tool_executor,
            fake_response=args.fake_response,
            fake_tool_call=args.fake_tool_call,
            repo_root=Path(args.repo_root) if args.repo_root else None,
            dry_run=args.dry_run,
        )
        view = workflow_tick_from_store(Path(args.workflow_store), run_id=args.run_id, max_ready_steps=args.max_ready_steps, executors=executors)
        return render_workflow_tick(view, as_json=args.as_json)
    if args.command == "workflow" and args.workflow_command == "status":
        view = workflow_status_from_store(Path(args.workflow_store), run_id=args.run_id)
        return render_workflow_status(view, as_json=args.as_json)
    if args.command == "task" and args.task_command == "status":
        if args.event_store:
            if not args.task_id:
                raise ValueError("--task-id is required with --event-store")
            view = task_status_from_event_store(Path(args.event_store), task_id=args.task_id)
            return render_task_status(view, as_json=args.as_json)
        payload = json.loads(Path(args.task_file).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("task status projection must be a JSON object")
        return render_task_status(TaskStatusView.from_mapping(payload), as_json=args.as_json)
    raise ValueError("unknown command")


def _write_output_file(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n", encoding="utf-8")


def _run_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    return args.prompt


def _run_fake_tool_call(args: argparse.Namespace) -> str | None:
    if args.fake_tool_call_file:
        return Path(args.fake_tool_call_file).read_text(encoding="utf-8")
    return args.fake_tool_call


if __name__ == "__main__":
    raise SystemExit(main())


