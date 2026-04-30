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
    transfer_payment = fields.Boolean(
        string="Pago por transferencia",
        compute="_compute_transfer_payment",
    )
    transfer_number = fields.Char(string="Numero de transferencia")

    @api.depends("payment_method_line_id", "payment_type")
    def _compute_cheque_payment(self):
        for wizard in self:
            wizard.cheque_payment = bool(
                wizard.payment_type == "outbound"
                and wizard.payment_method_line_id
                and wizard.payment_method_line_id.code == "dns_cheque"
            )

    @api.depends("payment_method_line_id", "payment_type", "journal_id")
    def _compute_transfer_payment(self):
        for wizard in self:
            wizard.transfer_payment = bool(
                wizard.payment_type == "outbound"
                and wizard.journal_id.type == "bank"
                and wizard.payment_method_line_id
                and wizard.payment_method_line_id._is_dns_transfer_method_line()
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
            if not wizard.transfer_payment:
                wizard.transfer_number = False

    @api.onchange("payment_date")
    def _onchange_payment_date_dns_cheque(self):
        for wizard in self:
            if wizard.cheque_payment and not wizard.cheque_issue_date:
                wizard.cheque_issue_date = wizard.payment_date

    @api.onchange("journal_id")
    def _onchange_journal_id_dns_transfer(self):
        for wizard in self:
            if not wizard.transfer_payment:
                wizard.transfer_number = False

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

    @api.constrains(
        "payment_method_line_id",
        "payment_type",
        "journal_id",
        "transfer_number",
    )
    def _check_dns_transfer_fields(self):
        for wizard in self:
            if not wizard.transfer_payment:
                continue
            if wizard.journal_id.type != "bank":
                raise ValidationError(
                    "Las transferencias deben registrarse con un diario bancario."
                )
            if not wizard.transfer_number:
                raise ValidationError(
                    "Complete los datos de la transferencia: numero de transferencia."
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
        if self.transfer_payment:
            payment_vals.update({"transfer_number": self.transfer_number})
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        payment_method_line = self.payment_method_line_id
        if (
            batch_result["payment_values"]["payment_type"] == "outbound"
            and self.journal_id.type == "bank"
            and payment_method_line
            and payment_method_line._is_dns_transfer_method_line()
        ):
            payment_vals.update({"transfer_number": self.transfer_number})
        return payment_vals
