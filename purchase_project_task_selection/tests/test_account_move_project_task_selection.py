from odoo.tests import Form, tagged
from odoo.exceptions import ValidationError

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountMoveProjectTaskSelection(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analytic_plan = cls.env.ref("analytic.analytic_plan_projects")
        cls.analytic_account_a = cls.env["account.analytic.account"].create(
            {"name": "Analitica A", "plan_id": cls.analytic_plan.id}
        )
        cls.project_a = cls.env["project.project"].create(
            {"name": "Proyecto A", "account_id": cls.analytic_account_a.id}
        )
        cls.project_b = cls.env["project.project"].create({"name": "Proyecto B"})
        cls.task_a = cls.env["project.task"].create(
            {"name": "Tarea A", "project_id": cls.project_a.id}
        )
        cls.task_b = cls.env["project.task"].create(
            {"name": "Tarea B", "project_id": cls.project_b.id}
        )

    def _new_invoice_form(self, move_type):
        return Form(self.env["account.move"].with_context(default_move_type=move_type))

    def test_invoice_line_task_sets_project(self):
        with self._new_invoice_form("out_invoice") as form:
            form.partner_id = self.partner_a
            with form.invoice_line_ids.new() as line_form:
                line_form.product_id = self.product_a
                self.assertFalse(line_form.project_id)
                line_form.task_id = self.task_a
                self.assertEqual(line_form.project_id, self.project_a)
                self.assertEqual(
                    line_form.analytic_distribution,
                    self.project_a._get_analytic_distribution(),
                )

    def test_invoice_project_sets_line_project_and_clears_mismatched_task(self):
        with self._new_invoice_form("in_invoice") as form:
            form.partner_id = self.partner_a
            form.project_id = self.project_a
            with form.invoice_line_ids.new() as line_form:
                line_form.product_id = self.product_b
                self.assertEqual(line_form.project_id, self.project_a)
                self.assertEqual(
                    line_form.analytic_distribution,
                    self.project_a._get_analytic_distribution(),
                )
                line_form.task_id = self.task_a
                line_form.project_id = self.project_b
                self.assertFalse(line_form.task_id)
                self.assertFalse(line_form.analytic_distribution)

    def test_create_invoice_line_defaults_project_from_move(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.company_data["default_journal_sale"].id,
                "project_id": self.project_a.id,
            }
        )
        line = self.env["account.move.line"].create(
            {
                "move_id": move.id,
                "name": "Linea",
                "product_id": self.product_a.id,
                "quantity": 1.0,
                "price_unit": 10.0,
                "account_id": self.product_a.property_account_income_id.id,
            }
        )
        self.assertEqual(line.project_id, self.project_a)
        self.assertEqual(
            line.analytic_distribution, self.project_a._get_analytic_distribution()
        )

    def test_reject_task_from_other_project(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.company_data["default_journal_sale"].id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["account.move.line"].create(
                {
                    "move_id": move.id,
                    "name": "Linea",
                    "product_id": self.product_a.id,
                    "quantity": 1.0,
                    "price_unit": 10.0,
                    "account_id": self.product_a.property_account_income_id.id,
                    "project_id": self.project_a.id,
                    "task_id": self.task_b.id,
                }
            )

    def test_project_without_analytic_clears_invoice_line_distribution(self):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
            }
        )
        line = self.env["account.move.line"].new(
            {
                "move_id": move.id,
                "name": "Linea",
                "product_id": self.product_b.id,
                "quantity": 1.0,
                "price_unit": 10.0,
                "account_id": self.product_b.property_account_expense_id.id,
                "analytic_distribution": self.project_a._get_analytic_distribution(),
            }
        )
        line.project_id = self.project_b
        line._onchange_project_id_clear_task_if_mismatch()
        self.assertFalse(line.analytic_distribution)
