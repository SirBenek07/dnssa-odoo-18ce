from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountCheque(models.Model):
    _name = "account.cheque"
    _description = "Cheque Emitido"
    _order = "cash_date asc, issue_date asc, id desc"
    _check_company_auto = True
    _rec_name = "check_number"

    check_number = fields.Char(string="Numero de cheque", required=True, tracking=True)
    issue_date = fields.Date(
        string="Fecha de emision",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    cash_date = fields.Date(string="Fecha de cobro", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        required=True,
        domain=[("supplier_rank", ">", 0)],
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Banco",
        required=True,
        domain="[('type', '=', 'bank'), ('emit_check', '=', True)]",
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
    calendar_label = fields.Char(
        string="Etiqueta calendario",
        compute="_compute_calendar_label",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("issued", "Emitido"),
            ("cashed", "Cobrado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    is_cash_due = fields.Boolean(
        string="Cheque vencido para cobro",
        compute="_compute_is_cash_due",
        store=True,
    )

    _sql_constraints = [
        (
            "account_cheque_journal_number_uniq",
            "unique(journal_id, check_number)",
            "El numero de cheque debe ser unico por banco.",
        ),
    ]

    @api.depends("state", "cash_date")
    def _compute_is_cash_due(self):
        today = fields.Date.context_today(self)
        for cheque in self:
            cheque.is_cash_due = bool(
                cheque.state == "issued" and cheque.cash_date and cheque.cash_date <= today
            )

    @api.depends("check_number", "partner_id", "amount")
    def _compute_calendar_label(self):
        for cheque in self:
            parts = [cheque.check_number or ""]
            if cheque.partner_id:
                parts.append(cheque.partner_id.display_name)
            if cheque.amount:
                parts.append(f"{cheque.amount:,.0f}")
            cheque.calendar_label = " - ".join(filter(None, parts))

    @api.depends("check_number", "partner_id", "amount")
    def _compute_display_name(self):
        for cheque in self:
            cheque.display_name = cheque.calendar_label or cheque.check_number or ""

    def name_get(self):
        result = []
        for cheque in self:
            result.append((cheque.id, cheque.calendar_label or cheque.check_number or ""))
        return result

    def action_set_draft(self):
        self.write({"state": "draft"})

    def action_set_issued(self):
        self.write({"state": "issued"})

    def action_set_cashed(self):
        if self.filtered("payment_id"):
            raise ValidationError(
                "Este cheque esta vinculado a un pago. Se marca como cobrado automaticamente al conciliar el pago."
            )
        self.write({"state": "cashed"})

    def action_set_cancelled(self):
        self.write({"state": "cancelled"})
