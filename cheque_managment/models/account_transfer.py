from odoo import api, fields, models


class AccountTransferPerformed(models.Model):
    _name = "account.transfer.performed"
    _description = "Transferencia realizada"
    _order = "date desc, id desc"
    _check_company_auto = True
    _rec_name = "transfer_number"

    transfer_number = fields.Char(
        string="Numero de transferencia",
        required=True,
        tracking=True,
    )
    date = fields.Date(
        string="Fecha de pago",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Beneficiario",
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Banco",
        required=True,
        domain="[('type', '=', 'bank')]",
        check_company=True,
        tracking=True,
    )
    payment_id = fields.Many2one(
        "account.payment",
        string="Pago",
        copy=False,
        readonly=True,
        check_company=True,
        ondelete="set null",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Metodo de pago",
        readonly=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="journal_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    amount = fields.Monetary(
        string="Monto",
        currency_field="currency_id",
        tracking=True,
    )
    memo = fields.Char(string="Memo")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("in_process", "En proceso"),
            ("paid", "Pagado"),
            ("canceled", "Cancelado"),
            ("rejected", "Rechazado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.depends("transfer_number", "partner_id", "amount")
    def _compute_display_name(self):
        for transfer in self:
            parts = [transfer.transfer_number or ""]
            if transfer.partner_id:
                parts.append(transfer.partner_id.display_name)
            if transfer.amount:
                parts.append(f"{transfer.amount:,.0f}")
            transfer.display_name = " - ".join(filter(None, parts))

    def name_get(self):
        result = []
        for transfer in self:
            result.append((transfer.id, transfer.display_name or transfer.transfer_number or ""))
        return result
