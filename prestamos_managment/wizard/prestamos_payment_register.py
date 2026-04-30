from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PrestamosPaymentRegister(models.TransientModel):
    _name = "prestamos.payment.register"
    _description = "Registrar pago de cuota de prestamo"
    _check_company_auto = True

    payment_board_id = fields.Many2one(
        "prestamos.loan.payment",
        string="Tablero de pago",
        required=True,
        readonly=True,
    )
    schedule_line_id = fields.Many2one(
        "prestamos.loan.line",
        string="Cuota",
        required=True,
        readonly=True,
    )
    loan_id = fields.Many2one(
        "prestamos.loan",
        related="schedule_line_id.loan_id",
        string="Prestamo",
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="payment_board_id.partner_id",
        string="Entidad",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="payment_board_id.company_id",
        string="Compania",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="payment_board_id.currency_id",
        string="Moneda",
        readonly=True,
    )
    amount = fields.Monetary(
        string="Importe",
        currency_field="currency_id",
        compute="_compute_amount",
    )
    payment_date = fields.Date(
        string="Fecha de pago",
        required=True,
        default=fields.Date.context_today,
    )
    communication = fields.Char(
        string="Memo",
        required=True,
        compute="_compute_communication",
        readonly=False,
        store=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        check_company=True,
        domain="[('id', 'in', available_journal_ids)]",
    )
    available_journal_ids = fields.Many2many(
        "account.journal",
        compute="_compute_available_journal_ids",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Metodo de pago",
        required=True,
        compute="_compute_payment_method_line_id",
        readonly=False,
        store=True,
        domain="[('id', 'in', available_payment_method_line_ids)]",
    )
    available_payment_method_line_ids = fields.Many2many(
        "account.payment.method.line",
        compute="_compute_payment_method_line_fields",
    )
    payment_method_code = fields.Char(related="payment_method_line_id.code")
    transfer_payment = fields.Boolean(
        string="Pago por transferencia",
        compute="_compute_transfer_payment",
    )
    transfer_number = fields.Char(string="Numero de transferencia")
    partner_bank_id = fields.Many2one(
        "res.partner.bank",
        string="Cuenta bancaria receptora",
        compute="_compute_partner_bank_id",
        readonly=False,
        store=True,
        domain="[('id', 'in', available_partner_bank_ids)]",
    )
    available_partner_bank_ids = fields.Many2many(
        "res.partner.bank",
        compute="_compute_available_partner_bank_ids",
    )
    show_partner_bank_account = fields.Boolean(
        compute="_compute_show_require_partner_bank"
    )
    require_partner_bank_account = fields.Boolean(
        compute="_compute_show_require_partner_bank"
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        payment_board = self.env["prestamos.loan.payment"].browse(
            vals.get("payment_board_id") or self.env.context.get("default_payment_board_id")
        )
        if payment_board:
            vals.setdefault("journal_id", payment_board.payment_journal_id.id)
        return vals

    @api.depends("schedule_line_id.payment_residual_amount")
    def _compute_amount(self):
        for wizard in self:
            wizard.amount = wizard.schedule_line_id.payment_residual_amount

    @api.depends("loan_id.name", "schedule_line_id.sequence")
    def _compute_communication(self):
        for wizard in self:
            wizard.communication = "%s - Pago cuota %s" % (
                wizard.loan_id.name,
                wizard.schedule_line_id.sequence,
            )

    @api.depends("company_id")
    def _compute_available_journal_ids(self):
        Journal = self.env["account.journal"]
        for wizard in self:
            if not wizard.company_id:
                wizard.available_journal_ids = Journal
                continue
            journals = Journal.search(
                [
                    ("company_id", "=", wizard.company_id.id),
                    ("type", "in", ("bank", "cash", "credit")),
                ]
            )
            wizard.available_journal_ids = journals.filtered(
                "outbound_payment_method_line_ids"
            )

    @api.depends("journal_id")
    def _compute_payment_method_line_fields(self):
        for wizard in self:
            wizard.available_payment_method_line_ids = (
                wizard.journal_id._get_available_payment_method_lines("outbound")
                if wizard.journal_id
                else False
            )

    @api.depends("available_payment_method_line_ids", "journal_id")
    def _compute_payment_method_line_id(self):
        for wizard in self:
            available_lines = wizard.available_payment_method_line_ids
            if wizard.payment_method_line_id in available_lines:
                continue
            wizard.payment_method_line_id = available_lines[:1]

    @api.depends("journal_id", "payment_method_line_id")
    def _compute_transfer_payment(self):
        for wizard in self:
            payment_method_line = wizard.payment_method_line_id
            is_transfer = (
                payment_method_line
                and hasattr(payment_method_line, "_is_dns_transfer_method_line")
                and payment_method_line._is_dns_transfer_method_line()
            )
            wizard.transfer_payment = bool(
                wizard.journal_id.type == "bank"
                and is_transfer
            )

    @api.onchange("journal_id", "payment_method_line_id")
    def _onchange_transfer_payment_fields(self):
        for wizard in self:
            if not wizard.transfer_payment:
                wizard.transfer_number = False

    @api.constrains("journal_id", "payment_method_line_id", "transfer_number")
    def _check_transfer_fields(self):
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

    @api.depends("partner_id", "company_id")
    def _compute_available_partner_bank_ids(self):
        for wizard in self:
            if not wizard.partner_id:
                wizard.available_partner_bank_ids = False
                continue
            wizard.available_partner_bank_ids = wizard.partner_id.bank_ids.filtered(
                lambda bank: not bank.company_id or bank.company_id == wizard.company_id
            )

    @api.depends("available_partner_bank_ids")
    def _compute_partner_bank_id(self):
        for wizard in self:
            if wizard.partner_bank_id not in wizard.available_partner_bank_ids:
                wizard.partner_bank_id = wizard.available_partner_bank_ids[:1]

    @api.depends("journal_id", "payment_method_line_id")
    def _compute_show_require_partner_bank(self):
        AccountPayment = self.env["account.payment"]
        using_bank_account = AccountPayment._get_method_codes_using_bank_account()
        needing_bank_account = AccountPayment._get_method_codes_needing_bank_account()
        for wizard in self:
            wizard.show_partner_bank_account = (
                wizard.journal_id.type != "cash"
                and wizard.payment_method_line_id.code in using_bank_account
            )
            wizard.require_partner_bank_account = (
                wizard.payment_method_line_id.code in needing_bank_account
            )

    def action_create_payment(self):
        self.ensure_one()
        if self.currency_id.is_zero(self.amount):
            raise UserError("La cuota no tiene saldo pendiente.")
        self.payment_board_id._create_payment_for_line(
            self.schedule_line_id,
            self.journal_id,
            self.payment_method_line_id,
            self.payment_date,
            self.communication,
            self.partner_bank_id,
            transfer_number=self.transfer_number if self.transfer_payment else False,
        )
        return {"type": "ir.actions.act_window_close"}
