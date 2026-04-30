from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    cheque_record_id = fields.Many2one(
        "account.cheque",
        string="Cheque",
        copy=False,
        readonly=True,
        check_company=True,
    )
    cheque_payment = fields.Boolean(
        string="Pago con cheque",
        compute="_compute_cheque_payment",
    )
    cheque_number = fields.Char(string="Numero de cheque", tracking=True, copy=False)
    cheque_issue_date = fields.Date(string="Fecha de emision", tracking=True, copy=False)
    cheque_cash_date = fields.Date(string="Fecha de cobro", tracking=True, copy=False)
    transfer_record_id = fields.Many2one(
        "account.transfer.performed",
        string="Transferencia",
        copy=False,
        readonly=True,
        check_company=True,
    )
    transfer_payment = fields.Boolean(
        string="Pago por transferencia",
        compute="_compute_transfer_payment",
    )
    transfer_number = fields.Char(
        string="Numero de transferencia",
        tracking=True,
        copy=False,
    )

    @api.depends("payment_method_line_id", "payment_type")
    def _compute_cheque_payment(self):
        for payment in self:
            payment.cheque_payment = bool(
                payment.payment_type == "outbound"
                and payment.payment_method_line_id
                and payment.payment_method_line_id.code == "dns_cheque"
            )

    @api.depends("payment_method_line_id", "payment_type", "journal_id")
    def _compute_transfer_payment(self):
        for payment in self:
            payment.transfer_payment = bool(
                payment.payment_type == "outbound"
                and payment.journal_id.type == "bank"
                and payment.payment_method_line_id
                and payment.payment_method_line_id._is_dns_transfer_method_line()
            )

    @api.onchange("payment_method_line_id")
    def _onchange_payment_method_line_id_dns_cheque(self):
        for payment in self:
            if payment.cheque_payment:
                payment.cheque_issue_date = payment.cheque_issue_date or payment.date
            else:
                payment.cheque_number = False
                payment.cheque_issue_date = False
                payment.cheque_cash_date = False
            if not payment.transfer_payment:
                payment.transfer_number = False

    @api.onchange("date")
    def _onchange_date_dns_cheque(self):
        for payment in self:
            if payment.cheque_payment and not payment.cheque_issue_date:
                payment.cheque_issue_date = payment.date

    @api.onchange("journal_id")
    def _onchange_journal_id_dns_transfer(self):
        for payment in self:
            if not payment.transfer_payment:
                payment.transfer_number = False

    @api.constrains(
        "payment_method_line_id",
        "payment_type",
        "journal_id",
        "cheque_number",
        "cheque_issue_date",
        "cheque_cash_date",
    )
    def _check_dns_cheque_fields(self):
        for payment in self:
            if not payment.cheque_payment:
                continue
            if payment.journal_id.type != "bank" or not payment.journal_id.emit_check:
                raise ValidationError(
                    "El diario seleccionado no tiene habilitada la emision de cheques."
                )
            if not payment.payment_method_line_id.payment_account_id:
                raise ValidationError(
                    "El metodo de pago 'Cheque' no tiene configurada la cuenta transitoria de pagos pendientes. "
                    "Configurela en el diario bancario (Pagos salientes)."
                )
            missing = []
            if not payment.cheque_number:
                missing.append("numero de cheque")
            if not payment.cheque_issue_date:
                missing.append("fecha de emision")
            if not payment.cheque_cash_date:
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
        for payment in self:
            if not payment.transfer_payment:
                continue
            if payment.journal_id.type != "bank":
                raise ValidationError(
                    "Las transferencias deben registrarse con un diario bancario."
                )
            if not payment.transfer_number:
                raise ValidationError(
                    "Complete los datos de la transferencia: numero de transferencia."
                )

    def _get_dns_cheque_state_from_payment(self):
        self.ensure_one()
        # "Cobrado" should reflect bank reconciliation (matched to statement), not only invoice reconciliation.
        if self.is_matched and self.state in ("in_process", "paid"):
            return "cashed"
        if self.state == "draft":
            return "draft"
        if self.state in ("canceled", "rejected"):
            return "cancelled"
        return "issued"

    def _dns_sync_cheque_record(self):
        if self.env.context.get("skip_dns_cheque_sync"):
            return
        for payment in self:
            if not payment.cheque_payment:
                # If it was switched away from cheque while still draft, remove the orphan record.
                if payment.cheque_record_id and payment.state == "draft":
                    payment.cheque_record_id.unlink()
                    payment.with_context(skip_dns_cheque_sync=True).write(
                        {"cheque_record_id": False}
                    )
                continue

            if not (
                payment.cheque_number
                and payment.cheque_issue_date
                and payment.cheque_cash_date
                and payment.partner_id
                and payment.journal_id
            ):
                continue

            vals = {
                "check_number": payment.cheque_number,
                "issue_date": payment.cheque_issue_date,
                "cash_date": payment.cheque_cash_date,
                "partner_id": payment.partner_id.id,
                "journal_id": payment.journal_id.id,
                "payment_id": payment.id,
                "amount": abs(payment.amount_company_currency_signed) or payment.amount,
                "state": payment._get_dns_cheque_state_from_payment(),
            }
            if payment.cheque_record_id:
                payment.cheque_record_id.write(vals)
            else:
                cheque = self.env["account.cheque"].create(vals)
                payment.with_context(skip_dns_cheque_sync=True).write(
                    {"cheque_record_id": cheque.id}
                )

    def _dns_sync_transfer_record(self):
        if self.env.context.get("skip_dns_transfer_sync"):
            return
        for payment in self:
            if not payment.transfer_payment:
                if payment.transfer_record_id and payment.state == "draft":
                    payment.transfer_record_id.unlink()
                    payment.with_context(skip_dns_transfer_sync=True).write(
                        {"transfer_record_id": False}
                    )
                continue

            if not (payment.transfer_number and payment.journal_id):
                continue

            vals = {
                "transfer_number": payment.transfer_number,
                "date": payment.date,
                "partner_id": payment.partner_id.id,
                "journal_id": payment.journal_id.id,
                "payment_id": payment.id,
                "payment_method_line_id": payment.payment_method_line_id.id,
                "amount": abs(payment.amount_company_currency_signed) or payment.amount,
                "memo": payment.memo,
                "state": payment.state,
            }
            if payment.transfer_record_id:
                payment.transfer_record_id.write(vals)
            else:
                transfer = self.env["account.transfer.performed"].create(vals)
                payment.with_context(skip_dns_transfer_sync=True).write(
                    {"transfer_record_id": transfer.id}
                )

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments._dns_sync_cheque_record()
        payments._dns_sync_transfer_record()
        return payments

    def write(self, vals):
        res = super().write(vals)
        tracked = {
            "payment_method_line_id",
            "payment_type",
            "journal_id",
            "partner_id",
            "date",
            "state",
            "amount",
            "memo",
            "cheque_number",
            "cheque_issue_date",
            "cheque_cash_date",
            "transfer_number",
            "transfer_record_id",
        }
        if tracked.intersection(vals):
            self._dns_sync_cheque_record()
            self._dns_sync_transfer_record()
        return res

    def action_post(self):
        res = super().action_post()
        self._dns_sync_cheque_record()
        self._dns_sync_transfer_record()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._dns_sync_cheque_record()
        self._dns_sync_transfer_record()
        return res

    def action_draft(self):
        res = super().action_draft()
        self._dns_sync_cheque_record()
        self._dns_sync_transfer_record()
        return res

    @api.depends(
        "move_id.line_ids.amount_residual",
        "move_id.line_ids.amount_residual_currency",
        "move_id.line_ids.account_id",
        "state",
    )
    def _compute_reconciliation_status(self):
        super()._compute_reconciliation_status()
        # Auto-mark linked cheques as cashed/cancelled/issued when payment reconciliation changes.
        for payment in self.filtered(lambda p: p.cheque_record_id and p.cheque_payment):
            target_state = payment._get_dns_cheque_state_from_payment()
            if payment.cheque_record_id.state != target_state:
                payment.cheque_record_id.write({"state": target_state})
        for payment in self.filtered(lambda p: p.transfer_record_id and p.transfer_payment):
            if payment.transfer_record_id.state != payment.state:
                payment.transfer_record_id.write({"state": payment.state})
