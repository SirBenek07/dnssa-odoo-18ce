from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payroll_payslip_id = fields.Many2one(
        "hr.payslip",
        string="Nomina relacionada",
        copy=False,
        readonly=True,
    )

    def action_post(self):
        res = super().action_post()
        slips = self.filtered("payroll_payslip_id").mapped("payroll_payslip_id")
        if slips:
            slips._compute_py_payment_amounts()
            slips._compute_py_payment_state()
        return res
