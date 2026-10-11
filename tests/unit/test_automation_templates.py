from __future__ import annotations

import unittest

from forgeweave.automation import get_workflow_template, list_workflow_templates, workflow_definition_to_mapping


class WorkflowTemplateTests(unittest.TestCase):
    def test_builtin_templates_are_valid_and_include_required_workflows(self) -> None:
        templates = list_workflow_templates()

        self.assertEqual(
            {template.template_id for template in templates},
            {
                "independent-patches-integration-verification",
                "parallel-investigation-synthesis",
                "research-plan-implement-test-review",
            },
        )
        self.assertTrue(all(template.definition.definition_hash.startswith("sha256:") for template in templates))
        self.assertTrue(all(template.definition.steps for template in templates))

    def test_template_definition_mapping_is_json_ready(self) -> None:
        template = get_workflow_template("research-plan-implement-test-review")

        payload = workflow_definition_to_mapping(template.definition)

        self.assertEqual(payload["workflow_id"], "research-plan-implement-test-review")
        self.assertEqual(payload["steps"][-1]["kind"], "join")
        self.assertEqual(payload["steps"][-1]["join_policy"]["mode"], "all_success")

    def test_unknown_template_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            get_workflow_template("missing")


if __name__ == "__main__":
    unittest.main()
