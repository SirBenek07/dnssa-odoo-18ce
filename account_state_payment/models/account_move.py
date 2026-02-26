from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_invoice_in_payment_state(self):
        company = self[:1].company_id or self.env.company
        if company.use_in_payment_state_until_bank_match:
            return "in_payment"
        return super()._get_invoice_in_payment_state()
