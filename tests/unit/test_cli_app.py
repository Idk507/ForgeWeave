from __future__ import annotations

import json
from pathlib import Path
import subprocess
from io import StringIO
import tempfile
import unittest
from unittest import mock

from forgeweave.automation import (
    StepAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    workflow_input_hash,
)
from forgeweave.cli.app import main
from forgeweave.cli.config import current_config_view, render_config
from forgeweave.cli.status import TaskStatusView, render_task_status
from forgeweave.contracts import EffectSet, ExecutionProfile, IsolationClaim, PolicyDecision, PolicyOutcome, TaskStatus, ToolCall, VerificationRun
from forgeweave.events import EventStore, ToolExecutionRecorder
from forgeweave.task import TaskStateMachine


class CliAppTests(unittest.TestCase):
    def test_config_show_json_reports_safe_runtime_configuration(self) -> None:
        stdout = StringIO()

        exit_code = main(["config", "show", "--json"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["default_engine"], "native")
        self.assertFalse(payload["laya_enabled"])
        self.assertIn("isolation", payload)
        self.assertFalse(payload["isolation"]["restricted_execution_measured"])
        self.assertEqual(payload["isolation"]["claims"]["filesystem"]["level"], "host-user")

    def test_config_show_renders_execution_profile_without_overclaiming(self) -> None:
        profile = ExecutionProfile(
            profile_id="test-profile",
            filesystem=IsolationClaim(level="workspace-write", backend="git-worktree", measured=False),
            network=IsolationClaim(level="shared-egress", backend="host", measured=False),
            credentials=IsolationClaim(level="host-user", backend="os", measured=False),
            process_tree=IsolationClaim(level="job-object", backend="windows-job-object", measured=True, evidence="M0.13"),
            resources=IsolationClaim(level="best-effort", backend="process", measured=False),
        )

        rendered = render_config(current_config_view(profile), as_json=True)
        payload = json.loads(rendered)

        self.assertFalse(payload["isolation"]["restricted_execution_measured"])
        self.assertEqual(payload["isolation"]["claims"]["process_tree"]["backend"], "windows-job-object")
        self.assertEqual(payload["isolation"]["claims"]["process_tree"]["evidence"], "M0.13")

    def test_task_status_view_renders_json_without_secrets(self) -> None:
        view = TaskStatusView(
            task_id="task-1",
            title="Fix bug",
            status="RUNNING",
            current_attempt_id="attempt-1",
            current_attempt_status="RUNNING",
            event_count=4,
            last_event_kind="ToolResult",
        )

        rendered = render_task_status(view, as_json=True)
        payload = json.loads(rendered)

        self.assertEqual(payload["task_id"], "task-1")
        self.assertEqual(payload["status"], "RUNNING")
        self.assertNotIn("api_key", rendered.lower())
        self.assertNotIn("secret", rendered.lower())

    def test_task_status_command_reads_event_store_projection_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_store = Path(tmp) / "events.db"
            store = EventStore.open(event_store)
            try:
                machine = TaskStateMachine(store)
                machine.create_task(task_id="task-1", title="Fix bug", attempt_id="attempt-1")
                machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
                machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                ["task", "status", "--event-store", str(event_store), "--task-id", "task-1", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["task_id"], "task-1")
        self.assertEqual(payload["title"], "Fix bug")
        self.assertEqual(payload["status"], "RUNNING")
        self.assertEqual(payload["current_attempt_status"], "RUNNING")
        self.assertEqual(payload["last_event_kind"], "TaskStateChanged")

    def test_task_status_event_store_requires_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stderr = StringIO()

            exit_code = main(["task", "status", "--event-store", str(Path(tmp) / "events.db")], stderr=stderr)

        self.assertEqual(exit_code, 1)
        self.assertIn("--task-id is required", stderr.getvalue())

    def test_workflow_validate_command_renders_valid_definition_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            definition_file = Path(tmp) / "workflow.json"
            definition_file.write_text(
                json.dumps(
                    {
                        "workflow_id": "wf-validate",
                        "version": 1,
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "steps": [
                            {"step_id": "research", "kind": "agent", "capability": "research"},
                            {"step_id": "test", "kind": "verification", "depends_on": ["research"]},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()

            exit_code = main(["workflow", "validate", str(definition_file), "--json"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["workflow_id"], "wf-validate")
        self.assertEqual(payload["step_count"], 2)
        self.assertTrue(payload["definition_hash"].startswith("sha256:"))

    def test_workflow_validate_command_reports_invalid_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            definition_file = Path(tmp) / "workflow.json"
            definition_file.write_text(
                json.dumps(
                    {
                        "workflow_id": "wf-invalid",
                        "version": 1,
                        "input_schema": {},
                        "output_schema": {},
                        "steps": [{"step_id": "test", "kind": "verification", "depends_on": ["missing"]}],
                    }
                ),
                encoding="utf-8",
            )
            stderr = StringIO()

            exit_code = main(["workflow", "validate", str(definition_file)], stderr=stderr)

        self.assertEqual(exit_code, 1)
        self.assertIn("missing", stderr.getvalue())

    def test_workflow_list_command_renders_persisted_definitions_and_runs_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            try:
                definition = WorkflowDefinition(
                    workflow_id="wf-list",
                    version=1,
                    steps=(WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),),
                    input_schema={},
                    output_schema={},
                )
                store.record_definition(definition)
                store.admit_run(
                    WorkflowRun(
                        run_id="run-1",
                        workflow_id=definition.workflow_id,
                        definition_hash=definition.definition_hash,
                        input_hash=workflow_input_hash({"goal": "list"}),
                    )
                )
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                ["workflow", "list", "--workflow-store", str(workflow_store), "--workflow-id", "wf-list", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["definitions"][0]["workflow_id"], "wf-list")
        self.assertEqual(payload["definitions"][0]["step_count"], 1)
        self.assertEqual(payload["runs"][0]["run_id"], "run-1")
        self.assertEqual(payload["runs"][0]["status"], WorkflowRunStatus.PENDING.value)

    def test_workflow_list_command_renders_empty_text_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            store.close()
            stdout = StringIO()

            exit_code = main(["workflow", "list", "--workflow-store", str(workflow_store)], stdout=stdout)

        self.assertEqual(exit_code, 0)
        rendered = stdout.getvalue()
        self.assertIn("Workflow definitions:", rendered)
        self.assertIn("Workflow runs:", rendered)
        self.assertIn("none", rendered)

    def test_workflow_template_list_command_renders_json(self) -> None:
        stdout = StringIO()

        exit_code = main(["workflow", "template", "list", "--json"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        template_ids = {item["template_id"] for item in payload["templates"]}
        self.assertIn("research-plan-implement-test-review", template_ids)
        self.assertIn("parallel-investigation-synthesis", template_ids)
        self.assertIn("independent-patches-integration-verification", template_ids)

    def test_workflow_template_show_command_renders_definition(self) -> None:
        stdout = StringIO()

        exit_code = main(
            ["workflow", "template", "show", "parallel-investigation-synthesis", "--json"],
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["template_id"], "parallel-investigation-synthesis")
        self.assertEqual(payload["definition"]["workflow_id"], "parallel-investigation-synthesis")
        self.assertTrue(payload["definition"]["steps"])

    def test_workflow_run_command_admits_definition_and_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            definition_file = Path(tmp) / "workflow.json"
            definition_file.write_text(
                json.dumps(
                    {
                        "workflow_id": "wf-run",
                        "version": 1,
                        "input_schema": {},
                        "output_schema": {},
                        "steps": [{"step_id": "research", "kind": "agent"}],
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()

            exit_code = main(
                [
                    "workflow",
                    "run",
                    str(definition_file),
                    "--workflow-store",
                    str(workflow_store),
                    "--run-id",
                    "run-1",
                    "--input-json",
                    '{"issue": 123}',
                    "--json",
                ],
                stdout=stdout,
            )
            store = WorkflowStore.open(workflow_store)
            try:
                stored_run = store.get_run("run-1")
                definitions = store.list_definitions()
            finally:
                store.close()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["run"]["run_id"], "run-1")
        self.assertEqual(payload["run"]["workflow_id"], "wf-run")
        self.assertEqual(payload["run"]["status"], WorkflowRunStatus.PENDING.value)
        self.assertFalse(payload["execution_started"])
        self.assertEqual(stored_run.run_id, "run-1")
        self.assertEqual(len(definitions), 1)

    def test_workflow_resume_command_moves_failed_run_to_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            try:
                definition = WorkflowDefinition(
                    workflow_id="wf-resume",
                    version=1,
                    steps=(WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),),
                    input_schema={},
                    output_schema={},
                )
                store.record_definition(definition)
                store.admit_run(
                    WorkflowRun(
                        run_id="run-1",
                        workflow_id=definition.workflow_id,
                        definition_hash=definition.definition_hash,
                        input_hash=workflow_input_hash({}),
                        status=WorkflowRunStatus.FAILED,
                    )
                )
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                ["workflow", "resume", "--workflow-store", str(workflow_store), "--run-id", "run-1", "--json"],
                stdout=stdout,
            )
            store = WorkflowStore.open(workflow_store)
            try:
                resumed = store.get_run("run-1")
            finally:
                store.close()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["run"]["status"], WorkflowRunStatus.PENDING.value)
        self.assertFalse(payload["admitted"])
        self.assertEqual(resumed.status, WorkflowRunStatus.PENDING)

    def test_workflow_resume_rejects_pending_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            try:
                definition = WorkflowDefinition(
                    workflow_id="wf-resume",
                    version=1,
                    steps=(WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),),
                    input_schema={},
                    output_schema={},
                )
                store.record_definition(definition)
                store.admit_run(
                    WorkflowRun(
                        run_id="run-1",
                        workflow_id=definition.workflow_id,
                        definition_hash=definition.definition_hash,
                        input_hash=workflow_input_hash({}),
                    )
                )
            finally:
                store.close()
            stderr = StringIO()

            exit_code = main(
                ["workflow", "resume", "--workflow-store", str(workflow_store), "--run-id", "run-1"],
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("cannot resume from status pending", stderr.getvalue())

    def test_workflow_tick_command_records_ready_step_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            try:
                definition = WorkflowDefinition(
                    workflow_id="wf-tick",
                    version=1,
                    steps=(WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),),
                    input_schema={},
                    output_schema={},
                )
                store.record_definition(definition)
                store.admit_run(
                    WorkflowRun(
                        run_id="run-1",
                        workflow_id=definition.workflow_id,
                        definition_hash=definition.definition_hash,
                        input_hash=workflow_input_hash({}),
                    )
                )
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                ["workflow", "tick", "--workflow-store", str(workflow_store), "--run-id", "run-1", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["run_status"], WorkflowRunStatus.RUNNING.value)
        self.assertFalse(payload["execution_started"])
        self.assertEqual(payload["recorded_steps"][0]["step_id"], "research")
        self.assertEqual(payload["recorded_steps"][0]["status"], WorkflowStepStatus.WAITING_EXTERNAL.value)

    def test_workflow_status_command_renders_persisted_projection_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            try:
                definition = WorkflowDefinition(
                    workflow_id="wf-1",
                    version=1,
                    steps=(
                        WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT),
                        WorkflowStep(step_id="implement", kind=WorkflowStepKind.AGENT, depends_on=("plan",)),
                    ),
                    input_schema={},
                    output_schema={},
                )
                store.record_definition(definition)
                store.admit_run(
                    WorkflowRun(
                        run_id="run-1",
                        workflow_id=definition.workflow_id,
                        definition_hash=definition.definition_hash,
                        input_hash=workflow_input_hash({"goal": "build"}),
                    )
                )
                store.record_attempt(
                    StepAttempt(
                        attempt_id="attempt-1",
                        run_id="run-1",
                        step_id="plan",
                        idempotency_key="run-1:plan:1",
                        status=WorkflowStepStatus.SUCCEEDED,
                    )
                )
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                ["workflow", "status", "--workflow-store", str(workflow_store), "--run-id", "run-1", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["run"]["run_id"], "run-1")
        self.assertEqual(payload["run"]["status"], WorkflowRunStatus.PENDING.value)
        self.assertEqual(payload["ready"], ["implement"])
        self.assertEqual(payload["completed"], ["plan"])
        self.assertEqual(payload["steps"][0]["latest_attempt_id"], "attempt-1")
        self.assertEqual(payload["steps"][1]["status"], WorkflowStepStatus.READY.value)

    def test_workflow_status_command_renders_text_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_store = Path(tmp) / "workflows.db"
            store = WorkflowStore.open(workflow_store)
            try:
                definition = WorkflowDefinition(
                    workflow_id="wf-1",
                    version=1,
                    steps=(WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),),
                    input_schema={},
                    output_schema={},
                )
                store.record_definition(definition)
                store.admit_run(
                    WorkflowRun(
                        run_id="run-1",
                        workflow_id=definition.workflow_id,
                        definition_hash=definition.definition_hash,
                        input_hash=workflow_input_hash({}),
                    )
                )
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                ["workflow", "status", "--workflow-store", str(workflow_store), "--run-id", "run-1"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        rendered = stdout.getvalue()
        self.assertIn("Workflow run: run-1", rendered)
        self.assertIn("Ready: research", rendered)
        self.assertIn("research: ready", rendered)

    def test_task_report_command_renders_final_report_from_verification_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_file = Path(tmp) / "verification.json"
            run_file.write_text(_verification_run("run-fail", "failed", 1).model_dump_json(), encoding="utf-8")
            stdout = StringIO()

            exit_code = main(
                [
                    "task",
                    "report",
                    "--task-id",
                    "task-1",
                    "--modified-file",
                    "src/app.py",
                    "--verification-run-file",
                    str(run_file),
                    "--risk",
                    "manual review pending",
                    "--artifact",
                    "artifact://task-1/patch",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["modified_files"], ["src/app.py"])
        self.assertEqual(payload["failed_checks"][0]["run_id"], "run-fail")
        self.assertEqual(payload["risks"], ["manual review pending"])
        self.assertEqual(payload["artifact_links"], ["artifact://task-1/patch"])

    def test_task_report_command_rejects_non_object_verification_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_file = Path(tmp) / "verification.json"
            run_file.write_text("[]", encoding="utf-8")
            stderr = StringIO()

            exit_code = main(
                ["task", "report", "--task-id", "task-1", "--verification-run-file", str(run_file)],
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("verification run file must contain a JSON object", stderr.getvalue())

    def test_task_diff_command_reads_bounded_git_patch_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._git_repo(Path(tmp))
            (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
            stdout = StringIO()

            exit_code = main(
                ["task", "diff", "--repo-root", str(repo), "--max-bytes", "10000", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["repo_root"], str(repo.resolve()))
        self.assertIn("-one", payload["patch"])
        self.assertIn("+two", payload["patch"])
        self.assertFalse(payload["truncated"])

    def test_task_diff_command_reports_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._git_repo(Path(tmp))
            (repo / "tracked.txt").write_text("x" * 2000, encoding="utf-8")
            stdout = StringIO()

            exit_code = main(
                ["task", "diff", "--repo-root", str(repo), "--max-bytes", "64", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["truncated"])
        self.assertLessEqual(len(payload["patch"].encode("utf-8")), 64)

    def test_task_cancel_command_appends_cancelled_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_store = Path(tmp) / "events.db"
            store = EventStore.open(event_store)
            try:
                machine = TaskStateMachine(store)
                machine.create_task(task_id="task-1", title="Fix bug", attempt_id="attempt-1")
                machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
                machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                [
                    "task",
                    "cancel",
                    "--event-store",
                    str(event_store),
                    "--task-id",
                    "task-1",
                    "--reason",
                    "user requested stop",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["cancelled"])
        self.assertEqual(payload["status"], "CANCELLED")
        self.assertEqual(payload["current_attempt_status"], "CANCELLED")

    def test_task_cancel_command_rejects_completed_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_store = Path(tmp) / "events.db"
            store = EventStore.open(event_store)
            try:
                machine = TaskStateMachine(store)
                machine.create_task(task_id="task-1", title="Fix bug", attempt_id="attempt-1")
                machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
                machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
                machine.transition("task-1", TaskStatus.VERIFYING, reason="checks")
                machine.transition("task-1", TaskStatus.COMPLETED, reason="done")
            finally:
                store.close()
            stderr = StringIO()

            exit_code = main(
                [
                    "task",
                    "cancel",
                    "--event-store",
                    str(event_store),
                    "--task-id",
                    "task-1",
                    "--reason",
                    "too late",
                ],
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("illegal task transition", stderr.getvalue())

    def test_task_resume_command_reconciles_and_creates_new_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_store = Path(tmp) / "events.db"
            store = EventStore.open(event_store)
            try:
                machine = TaskStateMachine(store)
                machine.create_task(task_id="task-1", title="Fix bug", attempt_id="attempt-1")
                machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
                machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
                machine.transition("task-1", TaskStatus.FAILED, reason="process stopped")
                self._record_authorized_tool(store, call_id="call-1")
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                [
                    "task",
                    "resume",
                    "--event-store",
                    str(event_store),
                    "--task-id",
                    "task-1",
                    "--recovered-attempt-id",
                    "attempt-1",
                    "--new-attempt-id",
                    "attempt-2",
                    "--evidence",
                    "restart recovery",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["resumed"])
        self.assertEqual(payload["current_attempt_id"], "attempt-2")
        self.assertEqual(payload["cancelled_tool_executions"], ["call-1"])
        self.assertEqual(payload["unknown_tool_executions"], [])

    def test_task_resume_command_blocks_on_unknown_dispatched_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_store = Path(tmp) / "events.db"
            store = EventStore.open(event_store)
            try:
                machine = TaskStateMachine(store)
                machine.create_task(task_id="task-1", title="Fix bug", attempt_id="attempt-1")
                machine.transition("task-1", TaskStatus.PREPARING, reason="load instructions")
                machine.transition("task-1", TaskStatus.RUNNING, reason="start loop")
                machine.transition("task-1", TaskStatus.FAILED, reason="process stopped")
                recorder = self._record_authorized_tool(store, call_id="call-1")
                recorder.mark_dispatching("call-1")
            finally:
                store.close()
            stdout = StringIO()

            exit_code = main(
                [
                    "task",
                    "resume",
                    "--event-store",
                    str(event_store),
                    "--task-id",
                    "task-1",
                    "--recovered-attempt-id",
                    "attempt-1",
                    "--new-attempt-id",
                    "attempt-2",
                    "--evidence",
                    "restart recovery",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["resumed"])
        self.assertEqual(payload["status"], "WAITING_RECONCILIATION")
        self.assertEqual(payload["current_attempt_id"], "attempt-1")
        self.assertEqual(payload["unknown_tool_executions"], ["call-1"])

    def test_task_status_command_reads_projection_file_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            projection = Path(tmp) / "task-status.json"
            projection.write_text(
                json.dumps(
                    {
                        "task_id": "task-1",
                        "title": "Fix bug",
                        "status": "VERIFYING",
                        "current_attempt_id": "attempt-2",
                        "current_attempt_status": "VERIFYING",
                        "event_count": 9,
                        "last_event_kind": "ToolCallRequested",
                    }
                ),
                encoding="utf-8",
            )

            stdout = StringIO()

            exit_code = main(["task", "status", "--task-file", str(projection), "--json"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["current_attempt_status"], "VERIFYING")

    def test_task_status_text_is_human_readable(self) -> None:
        view = TaskStatusView(
            task_id="task-1",
            title="Fix bug",
            status="FAILED",
            current_attempt_id="attempt-1",
            current_attempt_status="FAILED",
            event_count=6,
            last_event_kind="ToolFailure",
        )

        rendered = render_task_status(view, as_json=False)

        self.assertIn("task-1", rendered)
        self.assertIn("FAILED", rendered)
        self.assertIn("ToolFailure", rendered)



    def test_run_command_returns_fake_text_response_as_json(self) -> None:
        stdout = StringIO()

        exit_code = main(
            ["run", "--prompt", "say hi", "--fake-response", "hello", "--json"],
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["text"], "hello")
        self.assertEqual(payload["stop_reason"], "final_answer")
        self.assertFalse(payload["verified_dispatch_enabled"])



    def test_run_command_handles_slash_help_without_model_loop(self) -> None:
        stdout = StringIO()

        exit_code = main(["run", "--prompt", "/help", "--fake-response", "ignored", "--json"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["slash_command"], "help")
        self.assertIn("/config", payload["text"])
        self.assertNotIn("stop_reason", payload)

    def test_run_command_rejects_unknown_slash_command(self) -> None:
        stderr = StringIO()

        exit_code = main(["run", "--prompt", "/deploy", "--fake-response", "ignored"], stderr=stderr)

        self.assertEqual(exit_code, 1)
        self.assertIn("unsupported slash command", stderr.getvalue())


    def test_run_command_can_use_openai_compatible_provider_without_fake_chunks(self) -> None:
        stdout = StringIO()

        class Provider:
            def stream(self, *, messages, tools, options):
                from forgeweave.models import ModelChunk

                self.messages = messages
                yield ModelChunk(kind="text", content="live response")
                yield ModelChunk(kind="done", usage={"total_tokens": 2})

        provider = Provider()
        with mock.patch("forgeweave.cli.run.OpenAICompatibleProvider.from_env", return_value=provider) as factory:
            exit_code = main(
                ["run", "--provider", "openai-compatible", "--prompt", "say hi", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        factory.assert_called_once_with()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["provider"], "openai-compatible")
        self.assertEqual(payload["text"], "live response")
        self.assertEqual(provider.messages, [{"role": "user", "content": "say hi"}])

    def test_run_command_rejects_fake_response_with_live_provider(self) -> None:
        stderr = StringIO()

        exit_code = main(
            ["run", "--provider", "openai-compatible", "--prompt", "say hi", "--fake-response", "ignored"],
            stderr=stderr,
        )

        self.assertEqual(exit_code, 1)
        self.assertIn("fake response/tool-call options require --provider fake", stderr.getvalue())

    def test_run_command_reads_prompt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text("file prompt", encoding="utf-8")
            stdout = StringIO()

            exit_code = main(
                ["run", "--prompt-file", str(prompt_file), "--fake-response", "from file", "--json"],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["text"], "from file")
        self.assertEqual(payload["stop_reason"], "final_answer")

    def test_run_command_rejects_prompt_and_prompt_file_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text("file prompt", encoding="utf-8")
            stderr = StringIO()

            exit_code = main(
                ["run", "--prompt", "inline", "--prompt-file", str(prompt_file), "--fake-response", "x"],
                stderr=stderr,
            )

        self.assertEqual(exit_code, 2)

    def test_run_command_can_execute_deterministic_write_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = StringIO()
            tool_call = json.dumps(
                {
                    "tool_name": "write_text",
                    "tool_schema_version": "write-text.v1",
                    "arguments": {"path": "out.txt", "content": "created"},
                }
            )

            exit_code = main(
                ["run", "--prompt", "write", "--fake-tool-call", tool_call, "--repo-root", str(root), "--json"],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual((root / "out.txt").read_text(encoding="utf-8"), "created")
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["observations"][0]["tool_name"], "write_text")
            self.assertEqual(payload["stop_reason"], "continue")

    def test_run_command_reads_fake_tool_call_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = StringIO()
            tool_call_file = root / "tool-call.json"
            tool_call_file.write_text(
                json.dumps(
                    {
                        "tool_name": "write_text",
                        "tool_schema_version": "write-text.v1",
                        "arguments": {"path": "from-file.txt", "content": "loaded"},
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "write",
                    "--fake-tool-call-file",
                    str(tool_call_file),
                    "--repo-root",
                    str(root),
                    "--json",
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual((root / "from-file.txt").read_text(encoding="utf-8"), "loaded")
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["observations"][0]["tool_name"], "write_text")

    def test_run_command_rejects_fake_tool_call_and_file_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool_call_file = root / "tool-call.json"
            tool_call_file.write_text("{}", encoding="utf-8")
            stderr = StringIO()

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "write",
                    "--fake-tool-call",
                    "{}",
                    "--fake-tool-call-file",
                    str(tool_call_file),
                ],
                stderr=stderr,
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("not allowed with argument", stderr.getvalue())

    def test_run_command_dry_run_does_not_write_tool_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = StringIO()
            tool_call = json.dumps(
                {
                    "tool_name": "write_text",
                    "tool_schema_version": "write-text.v1",
                    "arguments": {"path": "would-write.txt", "content": "created"},
                }
            )

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "write",
                    "--fake-tool-call",
                    tool_call,
                    "--repo-root",
                    str(root),
                    "--dry-run",
                    "--json",
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse((root / "would-write.txt").exists())
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["dry_run"])
            self.assertIn("dry-run: would write", payload["observations"][0]["output"])

    def test_run_command_writes_rendered_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_file = Path(tmp) / "nested" / "run.json"
            stdout = StringIO()

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "say hi",
                    "--fake-response",
                    "hello",
                    "--json",
                    "--output-file",
                    str(output_file),
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["text"], "hello")
            self.assertEqual(payload["stop_reason"], "final_answer")


    def test_run_command_can_attach_completion_report_after_final_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            output_dir = Path(tmp) / "verify-artifacts"
            stdout = StringIO()

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "finish",
                    "--fake-response",
                    "done",
                    "--repo-root",
                    str(root),
                    "--complete-report",
                    "--task-id",
                    "task-1",
                    "--verification-output-dir",
                    str(output_dir),
                    "--modified-file",
                    "src/app.py",
                    "--artifact",
                    "artifact://task-1/diff",
                    "--json",
                ],
                stdout=stdout,
            )
            payload = json.loads(stdout.getvalue())
            artifact_id = payload["final_report"]["checks"][0]["output_artifact_id"]
            artifact_exists = (output_dir / f"{artifact_id}.txt").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["stop_reason"], "final_answer")
        self.assertTrue(payload["final_report"]["passed"])
        self.assertEqual(payload["final_report"]["task_id"], "task-1")
        self.assertEqual(payload["final_report"]["modified_files"], ["src/app.py"])
        self.assertEqual(payload["final_report"]["artifact_links"], ["artifact://task-1/diff"])
        self.assertEqual(payload["final_report"]["checks"][0]["criterion_ids"], ["unittest"])
        self.assertTrue(artifact_exists)

    def test_run_command_completion_report_marks_missing_checks_as_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdout = StringIO()

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "finish",
                    "--fake-response",
                    "done",
                    "--repo-root",
                    tmp,
                    "--complete-report",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["final_report"]["passed"])
        self.assertEqual(payload["final_report"]["checks"], [])
        self.assertIn("no verification commands were selected or run", payload["final_report"]["risks"])

    def test_run_command_skips_completion_report_until_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = StringIO()
            tool_call = json.dumps(
                {
                    "tool_name": "write_text",
                    "tool_schema_version": "write-text.v1",
                    "arguments": {"path": "out.txt", "content": "created"},
                }
            )

            exit_code = main(
                [
                    "run",
                    "--prompt",
                    "write",
                    "--fake-tool-call",
                    tool_call,
                    "--repo-root",
                    str(root),
                    "--complete-report",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["stop_reason"], "continue")
        self.assertIsNone(payload["final_report"])

    def test_run_command_requires_complete_verified_dispatch_options(self) -> None:
        stderr = StringIO()

        exit_code = main(
            ["run", "--prompt", "x", "--fake-response", "y", "--snapshot-dir", "C:/repo/.forgeweave/snapshots"],
            stderr=stderr,
        )

        self.assertEqual(exit_code, 1)
        self.assertIn("verified dispatch requires", stderr.getvalue())

    def test_verify_run_selected_command_executes_unittest_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            output_dir = Path(tmp) / "artifacts"
            stdout = StringIO()

            exit_code = main(
                [
                    "verify",
                    "run-selected",
                    "--task-id",
                    "task-1",
                    "--repo-root",
                    str(root),
                    "--output-dir",
                    str(output_dir),
                    "--json",
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["command_count"], 1)
            self.assertEqual(payload["failed_count"], 0)
            self.assertEqual(payload["results"][0]["criterion_ids"], ["unittest"])
            self.assertIsNotNone(payload["results"][0]["duration_ms"])
            artifact = output_dir / f"{payload['results'][0]['output_artifact_id']}.txt"
            self.assertTrue(artifact.exists())

    def test_verify_run_selected_command_reports_empty_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdout = StringIO()

            exit_code = main(
                [
                    "verify",
                    "run-selected",
                    "--task-id",
                    "task-1",
                    "--repo-root",
                    tmp,
                    "--output-dir",
                    str(Path(tmp) / "artifacts"),
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["command_count"], 0)
        self.assertEqual(payload["results"], [])

    def test_verify_select_command_reports_pytest_selection_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
            (root / "tests").mkdir()
            stdout = StringIO()

            exit_code = main(
                [
                    "verify",
                    "select",
                    "--repo-root",
                    str(root),
                    "--environment-profile-hash",
                    "sha256:env",
                    "--timeout-seconds",
                    "7",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["commands"][0]["argv"], ["python", "-m", "pytest"])
        self.assertEqual(payload["commands"][0]["criterion_ids"], ["pytest"])
        self.assertEqual(payload["commands"][0]["environment_profile_hash"], "sha256:env")
        self.assertEqual(payload["commands"][0]["timeout_seconds"], 7)
        self.assertEqual(payload["sources"], ["pyproject.toml:[tool.pytest]"])

    def test_verify_select_command_rejects_bad_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stderr = StringIO()

            exit_code = main(
                ["verify", "select", "--repo-root", tmp, "--timeout-seconds", "0"],
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("timeout_seconds must be >= 1", stderr.getvalue())

    def test_verify_config_command_builds_verified_executor_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            snapshots = Path(tmp) / "snapshots"
            stdout = StringIO()

            exit_code = main(
                [
                    "verify",
                    "config",
                    "--repo-root",
                    str(root),
                    "--snapshot-dir",
                    str(snapshots),
                    "--target",
                    "app.py",
                    "--config-hash",
                    "sha256:config",
                    "--retry-attempts",
                    "2",
                    "--timeout-seconds",
                    "7",
                    "--ruff-executable",
                    "custom-ruff",
                    "--ruff-rule",
                    "F",
                    "--json",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["repo_root"], str(root.resolve()))
        self.assertEqual(payload["snapshot_dir"], str(snapshots.resolve()))
        self.assertEqual(payload["targets"], [str(root.resolve() / "app.py")])
        self.assertEqual(payload["retry_attempts"], 2)
        self.assertEqual(payload["timeout_seconds"], 7)
        self.assertEqual(payload["analyzer_names"], ["ruff"])
        self.assertEqual(payload["ruff_executable"], "custom-ruff")
        self.assertEqual(payload["ruff_rules"], ["F"])

    def _git_repo(self, root: Path) -> Path:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "forgeweave@example.test"], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "ForgeWeave Test"], cwd=root, check=True, capture_output=True, text=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True, text=True)
        return root

    def _record_authorized_tool(self, store: EventStore, *, call_id: str) -> ToolExecutionRecorder:
        recorder = ToolExecutionRecorder(store)
        call = ToolCall(
            call_id=call_id,
            tool_name="write_text",
            tool_schema_version="tool.v1",
            arguments={"path": "out.txt"},
            argument_hash=f"sha256:args-{call_id}",
            effects=EffectSet(writes=frozenset({"workspace"})),
        )
        recorder.record_requested(task_id="task-1", attempt_id="attempt-1", call=call)
        recorder.record_policy_decision(
            PolicyDecision(
                decision_id=f"policy-{call_id}",
                task_id="task-1",
                attempt_id="attempt-1",
                tool_call_id=call_id,
                outcome=PolicyOutcome.ALLOW,
                reason="allowed",
                policy_revision="policy-v1",
            )
        )
        return recorder

    def test_verify_config_rejects_missing_targets(self) -> None:
        stderr = StringIO()

        exit_code = main(
            [
                "verify",
                "config",
                "--repo-root",
                "C:/repo",
                "--snapshot-dir",
                "C:/repo/.forgeweave/snapshots",
                "--config-hash",
                "sha256:config",
            ],
            stderr=stderr,
        )

        self.assertEqual(exit_code, 2)


    def test_keyboard_interrupt_returns_cancelled_exit_code(self) -> None:
        stderr = StringIO()

        with mock.patch("forgeweave.cli.app._dispatch", side_effect=KeyboardInterrupt):
            exit_code = main(["run", "--prompt", "x", "--fake-response", "y"], stderr=stderr)

        self.assertEqual(exit_code, 130)
        self.assertIn("cancelled: keyboard interrupt", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_unknown_command_returns_nonzero(self) -> None:
        stderr = StringIO()

        self.assertEqual(main(["unknown"], stderr=stderr), 2)


def _verification_run(run_id: str, outcome: str, exit_code: int) -> VerificationRun:
    return VerificationRun(
        run_id=run_id,
        task_id="task-1",
        criterion_ids=("criterion-1",),
        command_argv=("python", "-m", "unittest"),
        cwd="C:/repo",
        environment_profile_hash="sha256:env",
        verifier_version="verify-v1",
        config_hash="sha256:config",
        workspace_fingerprint="sha256:workspace",
        exit_code=exit_code,
        output_artifact_id="artifact-1",
        outcome=outcome,  # type: ignore[arg-type]
    )


if __name__ == "__main__":
    unittest.main()

