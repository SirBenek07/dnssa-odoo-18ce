from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends(
        "amount_residual",
        "move_type",
        "state",
        "company_id",
        "reconciled_payment_ids.state",
        "reconciled_payment_ids.is_matched",
        "reconciled_payment_ids.payment_method_line_id",
        "matched_payment_ids.state",
        "matched_payment_ids.is_matched",
        "matched_payment_ids.payment_method_line_id",
    )
    def _compute_payment_state(self):
        super()._compute_payment_state()

        # For vendor/customer invoices paid with cheque, keep invoice "in payment" until
        # the related payment is bank-matched (statement reconciliation).
        for move in self.filtered(lambda m: m.state == "posted" and m.is_invoice(True)):
            if move.payment_state != "paid":
                continue

            cheque_payments_pending_bank = (move.reconciled_payment_ids | move.matched_payment_ids).filtered(
                lambda p: p.payment_method_line_id
                and p.payment_method_line_id.code == "dns_cheque"
                and p.state in ("in_process", "paid")
                and not p.is_matched
            )
            if cheque_payments_pending_bank:
                move.payment_state = move._get_invoice_in_payment_state()
