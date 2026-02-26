from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    cheque_payment = fields.Boolean(
        string="Pago con cheque",
        compute="_compute_cheque_payment",
    )
    cheque_number = fields.Char(string="Numero de cheque")
    cheque_issue_date = fields.Date(string="Fecha de emision")
    cheque_cash_date = fields.Date(string="Fecha de cobro")

    @api.depends("payment_method_line_id", "payment_type")
    def _compute_cheque_payment(self):
        for wizard in self:
            wizard.cheque_payment = bool(
                wizard.payment_type == "outbound"
                and wizard.payment_method_line_id
                and wizard.payment_method_line_id.code == "dns_cheque"
            )

    @api.onchange("payment_method_line_id")
    def _onchange_payment_method_line_id_dns_cheque(self):
        for wizard in self:
            if wizard.cheque_payment:
                wizard.cheque_issue_date = wizard.cheque_issue_date or wizard.payment_date
            else:
                wizard.cheque_number = False
                wizard.cheque_issue_date = False
                wizard.cheque_cash_date = False

    @api.onchange("payment_date")
    def _onchange_payment_date_dns_cheque(self):
        for wizard in self:
            if wizard.cheque_payment and not wizard.cheque_issue_date:
                wizard.cheque_issue_date = wizard.payment_date

    @api.constrains(
        "payment_method_line_id",
        "payment_type",
        "journal_id",
        "cheque_number",
        "cheque_issue_date",
        "cheque_cash_date",
    )
    def _check_dns_cheque_fields(self):
        for wizard in self:
            if not wizard.cheque_payment:
                continue
            if wizard.journal_id.type != "bank" or not wizard.journal_id.emit_check:
                raise ValidationError(
                    "El diario seleccionado no tiene habilitada la emision de cheques."
                )
            if not wizard.payment_method_line_id.payment_account_id:
                raise ValidationError(
                    "El metodo de pago 'Cheque' no tiene configurada la cuenta transitoria de pagos pendientes. "
                    "Configurela en el diario bancario (Pagos salientes)."
                )
            missing = []
            if not wizard.cheque_number:
                missing.append("numero de cheque")
            if not wizard.cheque_issue_date:
                missing.append("fecha de emision")
            if not wizard.cheque_cash_date:
                missing.append("fecha de cobro")
            if missing:
                raise ValidationError(
                    "Complete los datos del cheque: %s." % ", ".join(missing)
                )

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        if self.cheque_payment:
            payment_vals.update(
                {
                    "cheque_number": self.cheque_number,
                    "cheque_issue_date": self.cheque_issue_date,
                    "cheque_cash_date": self.cheque_cash_date,
                }
            )
        return payment_vals
