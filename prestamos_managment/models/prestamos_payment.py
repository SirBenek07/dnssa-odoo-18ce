from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class PrestamosLoanPayment(models.Model):
    _name = "prestamos.loan.payment"
    _description = "Pago de Prestamos"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "next_due_date asc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Nombre",
        compute="_compute_name",
        store=True,
    )
    loan_id = fields.Many2one(
        "prestamos.loan",
        string="Prestamo",
        required=True,
        domain="[('state', 'in', ('confirmed', 'paid')), ('company_id', '=', company_id)]",
        check_company=True,
        tracking=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="loan_id.partner_id",
        store=True,
        readonly=True,
    )
    loan_state = fields.Selection(
        related="loan_id.state",
        string="Estado del prestamo",
        store=True,
        readonly=True,
    )
    payment_journal_id = fields.Many2one(
        "account.journal",
        string="Banco de pago",
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        check_company=True,
        tracking=True,
    )
    payment_date = fields.Date(
        string="Fecha de pago",
        default=fields.Date.context_today,
        tracking=True,
    )
    line_ids = fields.One2many(
        "prestamos.loan.line",
        "payment_id",
        string="Cuotas",
    )
    pending_installment_count = fields.Integer(
        string="Cuotas pendientes",
        compute="_compute_payment_summary",
        store=True,
    )
    paid_installment_count = fields.Integer(
        string="Cuotas pagadas",
        compute="_compute_payment_summary",
        store=True,
    )
    next_due_date = fields.Date(
        string="Proximo vencimiento",
        compute="_compute_payment_summary",
        store=True,
    )
    capital_pending_amount = fields.Monetary(
        string="Capital pendiente",
        currency_field="currency_id",
        compute="_compute_payment_summary",
        store=True,
    )
    interest_pending_amount = fields.Monetary(
        string="Intereses pendientes",
        currency_field="currency_id",
        compute="_compute_payment_summary",
        store=True,
    )
    payment_residual_amount = fields.Monetary(
        string="Total pendiente",
        currency_field="currency_id",
        compute="_compute_payment_summary",
        store=True,
    )
    state = fields.Selection(
        [("pending", "Pendiente"), ("paid", "Pagado")],
        string="Estado",
        compute="_compute_payment_summary",
        store=True,
    )

    _sql_constraints = [
        (
            "loan_payment_unique",
            "unique(loan_id)",
            "Ya existe un registro de pago para este prestamo.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            loan = self.env["prestamos.loan"].browse(vals.get("loan_id"))
            if loan:
                vals.setdefault("company_id", loan.company_id.id)
                if loan.bank_journal_id:
                    vals.setdefault("payment_journal_id", loan.bank_journal_id.id)
        records = super().create(vals_list)
        for record in records:
            record._sync_schedule_lines()
            if record.loan_id.payment_id != record:
                record.loan_id.payment_id = record
        return records

    def write(self, vals):
        old_loans = self.mapped("loan_id")
        result = super().write(vals)
        if "loan_id" in vals:
            old_loans.schedule_line_ids.filtered(lambda line: line.payment_id in self).write(
                {"payment_id": False}
            )
            for record in self:
                if not record.payment_journal_id and record.loan_id.bank_journal_id:
                    record.payment_journal_id = record.loan_id.bank_journal_id
                record._sync_schedule_lines()
                record.loan_id.payment_id = record
        return result

    def unlink(self):
        loans = self.mapped("loan_id")
        self.mapped("line_ids").write({"payment_id": False})
        result = super().unlink()
        loans.filtered(lambda loan: loan.payment_id in self).write({"payment_id": False})
        return result

    @api.onchange("loan_id")
    def _onchange_loan_id(self):
        for payment in self:
            if payment.loan_id:
                payment.company_id = payment.loan_id.company_id
                payment.payment_journal_id = payment.loan_id.bank_journal_id

    @api.depends("loan_id.name")
    def _compute_name(self):
        for payment in self:
            payment.name = (
                "Pago - %s" % payment.loan_id.display_name
                if payment.loan_id
                else "Pago de prestamo"
            )

    @api.depends(
        "line_ids.state",
        "line_ids.due_date",
        "line_ids.capital_residual_amount",
        "line_ids.interest_residual_amount",
        "line_ids.payment_residual_amount",
    )
    def _compute_payment_summary(self):
        for payment in self:
            pending_lines = payment.line_ids.filtered(lambda line: line.state == "pending")
            paid_lines = payment.line_ids.filtered(lambda line: line.state == "paid")
            payment.pending_installment_count = len(pending_lines)
            payment.paid_installment_count = len(paid_lines)
            payment.next_due_date = pending_lines.sorted(
                lambda line: (line.due_date, line.sequence, line.id)
            )[:1].due_date
            payment.capital_pending_amount = sum(
                pending_lines.mapped("capital_residual_amount")
            )
            payment.interest_pending_amount = sum(
                pending_lines.mapped("interest_residual_amount")
            )
            payment.payment_residual_amount = sum(
                pending_lines.mapped("payment_residual_amount")
            )
            payment.state = "paid" if payment.line_ids and not pending_lines else "pending"

    def action_open_loan(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "prestamos_managment.action_prestamos_loan"
        )
        action["res_id"] = self.loan_id.id
        action["views"] = [
            (self.env.ref("prestamos_managment.view_prestamos_loan_form").id, "form")
        ]
        action["view_mode"] = "form"
        return action

    def action_pay_next_due(self):
        self.ensure_one()
        line = self.line_ids.filtered(lambda item: item.state == "pending").sorted(
            lambda item: (item.due_date, item.sequence, item.id)
        )[:1]
        if not line:
            raise UserError("No hay cuotas pendientes para pagar.")
        return self.action_pay_line(line)

    def action_pay_line(self, schedule_line):
        self.ensure_one()
        schedule_line.ensure_one()
        self._check_line_can_be_paid(schedule_line)
        return {
            "name": "Pagar",
            "type": "ir.actions.act_window",
            "res_model": "prestamos.payment.register",
            "view_mode": "form",
            "view_id": self.env.ref(
                "prestamos_managment.view_prestamos_payment_register_form"
            ).id,
            "target": "new",
            "context": {
                "default_payment_board_id": self.id,
                "default_schedule_line_id": schedule_line.id,
                "default_payment_date": self.payment_date
                or fields.Date.context_today(self),
            },
        }

    def _check_line_can_be_paid(self, schedule_line):
        self.ensure_one()
        schedule_line.ensure_one()
        if schedule_line.payment_id != self:
            raise UserError("La cuota no pertenece a este registro de pago.")
        if self.loan_id.state not in ("confirmed", "paid"):
            raise UserError("Solo se pueden pagar prestamos confirmados.")
        if schedule_line.state == "paid":
            raise UserError("La cuota ya esta pagada.")
        if self.currency_id.is_zero(schedule_line.payment_residual_amount):
            raise UserError("La cuota no tiene saldo pendiente.")

    def _create_payment_for_line(
        self,
        schedule_line,
        journal,
        payment_method_line,
        payment_date,
        payment_ref,
        partner_bank=False,
        transfer_number=False,
    ):
        self.ensure_one()
        schedule_line.ensure_one()
        self._check_line_can_be_paid(schedule_line)
        if not journal:
            raise UserError("Seleccione el banco de pago.")
        if not payment_method_line or payment_method_line.journal_id != journal:
            raise UserError("Seleccione un metodo de pago valido para el diario.")
        payment_account = self._get_bank_payment_account(journal, payment_method_line)
        if not payment_account:
            raise UserError(
                "El banco de pago no tiene cuenta de pagos, suspense o cuenta por defecto."
            )

        capital_amount = schedule_line.capital_residual_amount
        interest_amount = schedule_line.interest_residual_amount
        if self.currency_id.is_zero(capital_amount) and self.currency_id.is_zero(interest_amount):
            raise UserError("La cuota no tiene saldo pendiente.")

        payment_date = payment_date or fields.Date.context_today(self)
        payment_ref = payment_ref or "%s - Pago cuota %s" % (
            self.loan_id.name,
            schedule_line.sequence,
        )
        line_vals = []
        if not self.currency_id.is_zero(capital_amount):
            line_vals.append(
                self._prepare_payment_debit_line(
                    schedule_line,
                    schedule_line.capital_account_id,
                    capital_amount,
                    "capital",
                )
            )
        if not self.currency_id.is_zero(interest_amount):
            line_vals.append(
                self._prepare_payment_debit_line(
                    schedule_line,
                    schedule_line._get_interest_payment_account(),
                    interest_amount,
                    "interest",
                )
            )
        total_amount = sum(item["debit"] for item in line_vals)
        line_vals.append(
            {
                "name": "%s - Pago cuota %s" % (self.loan_id.name, schedule_line.sequence),
                "account_id": payment_account.id,
                "partner_id": self.partner_id.id,
                "credit": total_amount,
                "debit": 0.0,
                "prestamos_loan_id": self.loan_id.id,
                "prestamos_schedule_line_id": schedule_line.id,
            }
        )
        payment_vals = {
            "date": payment_date,
            "amount": total_amount,
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_id.id,
            "journal_id": journal.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "payment_method_line_id": payment_method_line.id,
            "partner_bank_id": partner_bank.id if partner_bank else False,
            "memo": payment_ref,
            "payment_reference": payment_ref,
            "prestamos_loan_id": self.loan_id.id,
            "prestamos_schedule_line_id": schedule_line.id,
            "prestamos_payment_id": self.id,
            "line_ids": [Command.create(vals) for vals in line_vals],
        }
        if transfer_number and "transfer_number" in self.env["account.payment"]._fields:
            payment_vals["transfer_number"] = transfer_number
        account_payment = self.env["account.payment"].create(payment_vals)
        account_payment.action_post()
        move = account_payment.move_id
        if move.state == "draft":
            move.action_post()

        capital_payment_line = move.line_ids.filtered(
            lambda line: line.prestamos_component == "capital"
            and line.prestamos_schedule_line_id == schedule_line
            and line.debit
        )[:1]
        interest_payment_line = move.line_ids.filtered(
            lambda line: line.prestamos_component == "interest"
            and line.prestamos_schedule_line_id == schedule_line
            and line.debit
        )[:1]

        if capital_payment_line:
            self._reconcile_payment_line(
                schedule_line,
                schedule_line.capital_account_id,
                capital_payment_line,
            )
        if interest_payment_line:
            self._reconcile_payment_line(
                schedule_line,
                schedule_line._get_interest_payment_account(),
                interest_payment_line,
            )

        schedule_line.write(
            {
                "capital_paid_amount": schedule_line.capital_amount,
                "interest_paid_amount": schedule_line.interest_payment_amount,
                "payment_move_id": move.id,
                "account_payment_id": account_payment.id,
                "payment_date": payment_date,
                "payment_journal_id": journal.id,
                "state": "paid",
            }
        )
        self.message_post(
            body="Cuota %s pagada por %s." % (schedule_line.sequence, total_amount)
        )
        if not self.loan_id.schedule_line_ids.filtered(lambda line: line.state != "paid"):
            self.loan_id.state = "paid"
        return account_payment

    def _sync_schedule_lines(self):
        for payment in self:
            payment.loan_id.schedule_line_ids.write({"payment_id": payment.id})

    def _prepare_payment_debit_line(self, schedule_line, account, amount, component):
        if not account:
            raise UserError("La cuota no tiene cuenta de %s configurada." % component)
        return {
            "name": "%s - Pago cuota %s %s" % (
                self.loan_id.name,
                schedule_line.sequence,
                component,
            ),
            "account_id": account.id,
            "partner_id": self.partner_id.id,
            "debit": amount,
            "credit": 0.0,
            "prestamos_loan_id": self.loan_id.id,
            "prestamos_schedule_line_id": schedule_line.id,
            "prestamos_component": component,
        }

    def _get_bank_payment_method_line(self, journal):
        payment_method_line = journal.outbound_payment_method_line_ids.filtered(
            "payment_account_id"
        )[:1] or journal.outbound_payment_method_line_ids[:1]
        if not payment_method_line:
            raise UserError("El banco de pago no tiene metodos de pago salientes.")
        return payment_method_line

    def _get_bank_payment_account(self, journal, payment_method_line):
        if payment_method_line.payment_account_id:
            return payment_method_line.payment_account_id
        payment_proxy = self.env["account.payment"].new(
            {
                "company_id": self.company_id.id,
                "journal_id": journal.id,
                "payment_type": "outbound",
                "partner_type": "supplier",
            }
        )
        return payment_proxy._get_outstanding_account("outbound") or journal.default_account_id

    def _reconcile_payment_line(self, schedule_line, account, payment_line):
        if not account.reconcile:
            return
        credit_lines = self.env["account.move.line"].search(
            [
                ("prestamos_schedule_line_id", "=", schedule_line.id),
                ("account_id", "=", account.id),
                ("parent_state", "=", "posted"),
                ("credit", ">", 0.0),
                ("reconciled", "=", False),
            ]
        )
        lines = credit_lines | payment_line
        if len(lines) > 1:
            lines.reconcile()
