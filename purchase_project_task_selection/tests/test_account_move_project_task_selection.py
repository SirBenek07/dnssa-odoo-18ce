from odoo.tests import Form, tagged
from odoo.exceptions import ValidationError

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountMoveProjectTaskSelection(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_a = cls.env["project.project"].create({"name": "Proyecto A"})
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

    def test_invoice_project_sets_line_project_and_clears_mismatched_task(self):
        with self._new_invoice_form("in_invoice") as form:
            form.partner_id = self.partner_a
            form.project_id = self.project_a
            with form.invoice_line_ids.new() as line_form:
                line_form.product_id = self.product_b
                self.assertEqual(line_form.project_id, self.project_a)
                line_form.task_id = self.task_a
                line_form.project_id = self.project_b
                self.assertFalse(line_form.task_id)

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
