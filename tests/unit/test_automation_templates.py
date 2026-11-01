from __future__ import annotations

import unittest

from forgeweave.automation import get_workflow_template, list_workflow_templates, workflow_definition_to_mapping


class WorkflowTemplateTests(unittest.TestCase):
    def test_builtin_templates_are_valid_and_include_required_workflows(self) -> None:
        templates = list_workflow_templates()

        self.assertEqual(
            {template.template_id for template in templates},
            {
                "browser-ui-regression",
                "dependency-update",
                "docs-sync",
                "independent-patches-integration-verification",
                "issue-to-patch",
                "parallel-investigation-synthesis",
                "pr-review",
                "research-plan-implement-test-review",
                "scheduled-test-triage",
            },
        )
        self.assertEqual([template.template_id for template in templates], sorted(template.template_id for template in templates))
        self.assertTrue(all(template.definition.definition_hash.startswith("sha256:") for template in templates))
        self.assertTrue(all(template.definition.steps for template in templates))

    def test_template_definition_mapping_is_json_ready(self) -> None:
        template = get_workflow_template("research-plan-implement-test-review")

        payload = workflow_definition_to_mapping(template.definition)

        self.assertEqual(payload["workflow_id"], "research-plan-implement-test-review")
        self.assertEqual(payload["steps"][-1]["kind"], "join")
        self.assertEqual(payload["steps"][-1]["join_policy"]["mode"], "all_success")

    def test_m4_example_templates_have_reviewable_gates_and_local_artifacts(self) -> None:
        example_ids = {
            "issue-to-patch",
            "pr-review",
            "dependency-update",
            "browser-ui-regression",
            "scheduled-test-triage",
            "docs-sync",
        }

        for template_id in example_ids:
            with self.subTest(template_id=template_id):
                definition = get_workflow_template(template_id).definition
                steps = {step.step_id: step for step in definition.steps}
                kinds = {step.kind.value for step in definition.steps}
                artifact_steps = [step for step in definition.steps if step.parameters and step.parameters.get("artifacts")]

                self.assertIn("join", kinds)
                self.assertTrue(artifact_steps)
                self.assertTrue(any(step.kind.value == "verification" for step in definition.steps))
                self.assertTrue(any(step.join_policy is not None for step in definition.steps))
                self.assertEqual(definition.workflow_id, template_id)
                self.assertEqual(len(steps), len(definition.steps))

    def test_browser_ui_regression_template_declares_browser_requirement(self) -> None:
        definition = get_workflow_template("browser-ui-regression").definition
        browser_steps = [step for step in definition.steps if step.capability == "browser"]

        self.assertEqual({step.step_id for step in browser_steps}, {"reproduce_ui", "verify_browser"})
        self.assertTrue(all(step.parameters and step.parameters.get("requires_browser") is True for step in browser_steps))

    def test_unknown_template_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            get_workflow_template("missing")


if __name__ == "__main__":
    unittest.main()
