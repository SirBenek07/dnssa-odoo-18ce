# Copyright 2020 haulogy SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestProjectParent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_project_1 = cls.env.ref("project.project_project_1")
        cls.project_project_2 = cls.env.ref("project.project_project_2")
        cls.project_project_3 = cls.env["project.project"].create(
            {"name": "TestProject", "parent_id": cls.project_project_1.id}
        )

    def test_parent_childs_project(self):
        self.assertIn(self.project_project_2, self.project_project_1.child_ids)
        self.assertIn(self.project_project_3, self.project_project_1.child_ids)

    def test_action_open_child_project(self):
        res = self.project_project_1.action_open_child_project()
        self.assertEqual(
            res.get("domain"), [("parent_id", "=", self.project_project_1.id)]
        )
        self.assertEqual(
            res.get("context").get("default_parent_id"), self.project_project_1.id
        )

    def test_parent_analytic_items(self):
        plan = self.env.ref("analytic.analytic_plan_projects")
        parent_project = self.env["project.project"].create({"name": "Parent Analytic"})
        child_project = self.env["project.project"].create(
            {"name": "Child Analytic", "parent_id": parent_project.id}
        )
        parent_account = self.env["account.analytic.account"].create(
            {"name": "Parent AA", "plan_id": plan.id}
        )
        child_account = self.env["account.analytic.account"].create(
            {"name": "Child AA", "plan_id": plan.id}
        )
        parent_project.account_id = parent_account.id
        child_project.account_id = child_account.id
        analytic_line_model = self.env["account.analytic.line"]
        analytic_line_model.create(
            {"name": "Parent Line", "account_id": parent_account.id}
        )
        analytic_line_model.create(
            {"name": "Child Line", "account_id": child_account.id}
        )
        self.assertEqual(parent_project.descendant_analytic_line_count, 2)
        self.assertEqual(child_project.descendant_analytic_line_count, 1)
        action = parent_project.action_view_descendant_analytic_items()
        domain = action.get("domain", [])
        self.assertTrue(domain)
        self.assertEqual(domain[0][:2], ("account_id", "in"))
        expected_accounts = (
            parent_project._get_descendant_projects().account_id.ids
        )
        self.assertCountEqual(domain[0][2], expected_accounts)
