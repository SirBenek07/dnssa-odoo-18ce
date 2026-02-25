from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def button_cancel(self):
        res = super().button_cancel()
        if self.env.context.get("skip_payroll_bill_cancel_sync"):
            return res

        bills = self.filtered(lambda m: m.move_type == "in_invoice")
        if not bills:
            return res

        payslips = self.env["hr.payslip"].search(
            [("vendor_bill_id", "in", bills.ids), ("state", "!=", "cancel")]
        )
        if payslips:
            payslips.with_context(skip_vendor_bill_cancel_sync=True).action_payslip_cancel()
        return res
