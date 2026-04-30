import calendar

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PrestamosLoan(models.Model):
    _name = "prestamos.loan"
    _description = "Prestamo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "loan_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Nombre del prestamo", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Entidad prestadora",
        required=True,
        tracking=True,
    )
    partner_is_bank_or_financial_entity = fields.Boolean(
        related="partner_id.is_bank_or_financial_entity",
        string="Entidad bancaria o financiera",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("paid", "Pagado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    capital_amount = fields.Monetary(
        string="Capital prestado",
        currency_field="currency_id",
        required=True,
        tracking=True,
    )
    interest_amount = fields.Monetary(
        string="Intereses",
        currency_field="currency_id",
        tracking=True,
    )
    interest_rate = fields.Float(
        string="Tasa de interes anual (%)",
        digits=(16, 6),
        help="Para el sistema aleman se aplica sobre saldo pendiente, proporcional a los dias reales de cada cuota sobre base 365.",
        tracking=True,
    )
    generate_interest_invoice = fields.Boolean(
        string="Generar factura de intereses",
        default=True,
        tracking=True,
    )
    interest_taxes_included = fields.Boolean(
        string="Impuestos incluidos en intereses",
        default=True,
        tracking=True,
        help="Active esta opcion cuando el importe informado de intereses ya incluye IVA u otros impuestos.",
    )
    loan_date = fields.Date(
        string="Fecha del prestamo",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    first_due_date = fields.Date(
        string="Fecha de primera cuota",
        required=True,
        tracking=True,
    )
    due_policy = fields.Selection(
        [
            ("end_of_month", "Fin de mes"),
            ("due_date", "Fecha de vencimiento"),
        ],
        string="Vencimiento",
        required=True,
        default="due_date",
        tracking=True,
    )
    installment_count = fields.Integer(
        string="Cuotas",
        default=1,
        required=True,
        tracking=True,
    )
    installment_frequency = fields.Selection(
        [
            ("fortnightly", "Quincenal"),
            ("monthly", "Mensual"),
            ("bimonthly", "Bimensual"),
            ("quarterly", "Trimestral"),
            ("semiannual", "Semestral"),
            ("annual", "Anual"),
        ],
        string="Frecuencia de cuotas",
        default="monthly",
        required=True,
        tracking=True,
    )
    amortization_system = fields.Selection(
        [
            ("frances", "Sistema frances"),
            ("aleman", "Sistema aleman"),
            ("americano", "Sistema americano / bullet"),
            ("lineal", "Sistema lineal simple"),
        ],
        string="Sistema",
        required=True,
        default="frances",
        tracking=True,
    )
    system_description = fields.Text(
        string="Logica de devengacion",
        compute="_compute_system_description",
    )

    balance_amount = fields.Monetary(
        string="Balance",
        currency_field="currency_id",
        compute="_compute_balance_amount",
        store=True,
        readonly=True,
    )
    other_interest_amount = fields.Monetary(
        string="Otros intereses",
        currency_field="currency_id",
        compute="_compute_other_interest_amount",
        store=True,
        readonly=True,
    )

    bank_journal_id = fields.Many2one(
        "account.journal",
        string="Banco acreditado",
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        check_company=True,
        tracking=True,
    )
    short_loan_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de prestamo a corto plazo",
        domain="[('deprecated', '=', False), ('company_ids', 'parent_of', company_id), ('internal_group', '=', 'liability')]",
        check_company=True,
        tracking=True,
    )
    long_loan_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de prestamo a largo plazo",
        domain="[('deprecated', '=', False), ('company_ids', 'parent_of', company_id), ('internal_group', '=', 'liability')]",
        check_company=True,
        tracking=True,
    )
    short_interest_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de intereses a pagar a corto plazo",
        domain="[('deprecated', '=', False), ('company_ids', 'parent_of', company_id), ('account_type', '=', 'liability_payable')]",
        check_company=True,
        tracking=True,
    )
    long_interest_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de intereses a pagar a largo plazo",
        domain="[('deprecated', '=', False), ('company_ids', 'parent_of', company_id), ('account_type', '=', 'liability_payable')]",
        check_company=True,
        tracking=True,
    )
    expense_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de gastos de intereses",
        domain="[('deprecated', '=', False), ('company_ids', 'parent_of', company_id), ('account_type', '=', 'expense')]",
        check_company=True,
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        check_company=True,
        tracking=True,
    )
    analytic_line_ids = fields.One2many(
        "prestamos.loan.analytic.line",
        "loan_id",
        string="Proyecto/s",
    )
    analytic_distribution = fields.Json(
        string="Distribucion analitica",
        compute="_compute_analytic_distribution",
        store=True,
    )
    interest_product_id = fields.Many2one(
        "product.product",
        string="Producto de intereses",
        domain="[('purchase_ok', '=', True)]",
        tracking=True,
    )

    schedule_line_ids = fields.One2many(
        "prestamos.loan.line",
        "loan_id",
        string="Plan de amortizacion",
        copy=False,
    )
    interest_invoice_id = fields.Many2one(
        "account.move",
        string="Factura intereses",
        domain="[('move_type', '=', 'in_invoice'), ('company_id', '=', company_id)]",
        check_company=True,
        copy=False,
        readonly=True,
    )
    other_interest_invoice_ids = fields.One2many(
        "account.move",
        "prestamos_other_interest_loan_id",
        string="Otros intereses",
        domain=[("move_type", "=", "in_invoice")],
    )
    capital_move_id = fields.Many2one(
        "account.move",
        string="Asiento de capital",
        check_company=True,
        copy=False,
        readonly=True,
    )
    interest_move_id = fields.Many2one(
        "account.move",
        string="Asiento de intereses",
        check_company=True,
        copy=False,
        readonly=True,
    )
    interest_payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Termino de pago de intereses",
        copy=False,
        readonly=True,
    )
    payment_id = fields.Many2one(
        "prestamos.loan.payment",
        string="Pago de prestamo",
        copy=False,
        readonly=True,
        ondelete="set null",
    )

    _sql_constraints = [
        (
            "installment_count_positive",
            "CHECK(installment_count > 0)",
            "La cantidad de cuotas debe ser mayor a cero.",
        ),
        (
            "capital_amount_positive",
            "CHECK(capital_amount > 0)",
            "El capital prestado debe ser mayor a cero.",
        ),
        (
            "interest_amount_positive",
            "CHECK(interest_amount >= 0)",
            "Los intereses no pueden ser negativos.",
        ),
        (
            "interest_rate_positive",
            "CHECK(interest_rate >= 0)",
            "La tasa de interes no puede ser negativa.",
        ),
    ]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        defaults = self._get_account_defaults(self.env.company, self.env["res.partner"])
        for field_name, value in defaults.items():
            if field_name in fields_list and value and not values.get(field_name):
                values[field_name] = value.id
        return values

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for loan in self:
            loan._apply_account_defaults()

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for loan in self:
            loan._apply_account_defaults()

    def _apply_account_defaults(self):
        self.ensure_one()
        if not self.company_id:
            return
        defaults = self._get_account_defaults(self.company_id, self.partner_id)
        for field_name, account in defaults.items():
            self[field_name] = account

    def _get_account_defaults(self, company, partner):
        is_owner_or_partner = bool(partner and partner._is_loan_owner_or_partner())
        is_financial = bool(partner and partner.is_bank_or_financial_entity)
        if is_owner_or_partner:
            short_loan_account = (
                company.loan_owner_short_term_account_id
                or company.loan_non_bank_short_term_account_id
                or company.loan_non_bank_payable_account_id
                or company.loan_default_short_term_account_id
            )
            long_loan_account = (
                company.loan_owner_long_term_account_id
                or company.loan_non_bank_long_term_account_id
                or company.loan_non_bank_payable_account_id
                or company.loan_default_long_term_account_id
            )
            expense_account = (
                company.loan_non_bank_interest_expense_account_id
                or company.loan_default_expense_account_id
            )
        elif is_financial:
            short_loan_account = (
                company.loan_bank_short_term_account_id
                or company.loan_bank_payable_account_id
                or company.loan_default_short_term_account_id
            )
            long_loan_account = (
                company.loan_bank_long_term_account_id
                or company.loan_bank_payable_account_id
                or company.loan_default_long_term_account_id
            )
            expense_account = (
                company.loan_bank_interest_expense_account_id
                or company.loan_default_expense_account_id
            )
        else:
            short_loan_account = (
                company.loan_non_bank_short_term_account_id
                or company.loan_non_bank_payable_account_id
                or company.loan_default_short_term_account_id
            )
            long_loan_account = (
                company.loan_non_bank_long_term_account_id
                or company.loan_non_bank_payable_account_id
                or company.loan_default_long_term_account_id
            )
            expense_account = (
                company.loan_non_bank_interest_expense_account_id
                or company.loan_default_expense_account_id
            )
        short_interest_account = company.loan_short_interest_payable_account_id
        if short_interest_account.account_type != "liability_payable":
            short_interest_account = False
        long_interest_account = company.loan_long_interest_payable_account_id
        if long_interest_account.account_type != "liability_payable":
            long_interest_account = False
        return {
            "short_loan_account_id": short_loan_account,
            "long_loan_account_id": long_loan_account,
            "short_interest_account_id": short_interest_account,
            "long_interest_account_id": long_interest_account,
            "expense_account_id": expense_account,
            "interest_product_id": company.loan_interest_product_id,
        }

    @api.onchange(
        "amortization_system",
        "capital_amount",
        "interest_rate",
        "loan_date",
        "first_due_date",
        "due_policy",
        "installment_count",
        "installment_frequency",
        "interest_taxes_included",
    )
    def _onchange_german_interest_inputs(self):
        for loan in self:
            loan._sync_german_interest_amount()

    @api.depends("amortization_system")
    def _compute_system_description(self):
        descriptions = {
            "frances": (
                "Cuota total constante. La porcion de interes se calcula sobre saldo "
                "y decrece; la amortizacion de capital crece."
            ),
            "aleman": (
                "Amortizacion de capital constante. El interes se calcula sobre saldo "
                "pendiente usando la tasa anual proporcional a los dias reales de cada cuota."
            ),
            "americano": (
                "Pago periodico de intereses y amortizacion del capital completo en "
                "la ultima cuota."
            ),
            "lineal": (
                "Capital e intereses distribuidos linealmente entre las cuotas. La "
                "cuota total queda constante con el interes total informado."
            ),
        }
        for loan in self:
            loan.system_description = descriptions.get(loan.amortization_system, "")

    @api.depends(
        "schedule_line_ids.state",
        "schedule_line_ids.payment_residual_amount",
        "state",
    )
    def _compute_balance_amount(self):
        for loan in self:
            if loan.state == "draft":
                loan.balance_amount = 0.0
                continue
            loan.balance_amount = sum(
                line.payment_residual_amount
                for line in loan.schedule_line_ids
                if line.state == "pending"
            )

    @api.depends(
        "other_interest_invoice_ids.amount_total_signed",
        "other_interest_invoice_ids.state",
        "other_interest_invoice_ids.move_type",
    )
    def _compute_other_interest_amount(self):
        for loan in self:
            loan.other_interest_amount = sum(
                abs(invoice.amount_total_signed)
                for invoice in loan.other_interest_invoice_ids
                if invoice.move_type == "in_invoice" and invoice.state != "cancel"
            )

    @api.depends("analytic_line_ids.account_id", "analytic_line_ids.percentage")
    def _compute_analytic_distribution(self):
        for loan in self:
            distribution = {}
            for line in loan.analytic_line_ids:
                if line.account_id and line.percentage:
                    distribution[str(line.account_id.id)] = line.percentage
            loan.analytic_distribution = distribution or False

    @api.constrains("analytic_line_ids")
    def _check_analytic_distribution_total(self):
        precision = self.env["decimal.precision"].precision_get("Percentage Analytic")
        for loan in self:
            if not loan.analytic_line_ids:
                continue
            total = sum(loan.analytic_line_ids.mapped("percentage"))
            if float_compare(total, 100.0, precision_digits=precision) != 0:
                raise ValidationError(
                    "La distribucion analitica del prestamo debe sumar 100%."
                )

    @api.constrains("first_due_date", "loan_date")
    def _check_dates(self):
        for loan in self:
            if loan.first_due_date and loan.loan_date and loan.first_due_date < loan.loan_date:
                raise ValidationError(
                    "La fecha de primera cuota no puede ser anterior a la fecha del prestamo."
                )

    def write(self, vals):
        protected_fields = {
            "capital_amount",
            "interest_amount",
            "interest_rate",
            "loan_date",
            "first_due_date",
            "due_policy",
            "installment_count",
            "installment_frequency",
            "amortization_system",
            "generate_interest_invoice",
            "interest_taxes_included",
        }
        if protected_fields & vals.keys():
            locked = self.filtered(lambda loan: loan.state != "draft")
            if locked:
                raise UserError(
                    "Los datos principales del prestamo no se pueden modificar luego de confirmar."
                )
        return super().write(vals)

    def action_recompute_schedule(self):
        for loan in self:
            if loan.state != "draft":
                raise UserError(
                    "Solo se puede regenerar el plan de amortizacion en borrador."
                )
            loan._sync_german_interest_amount()
            loan._create_schedule_lines()
        return True

    def action_confirm(self):
        for loan in self:
            if loan.state != "draft":
                continue
            loan._sync_german_interest_amount()
            loan._check_ready_to_confirm()
            loan._create_schedule_lines()
            loan.capital_move_id = loan._create_capital_move()
            if not loan.currency_id.is_zero(loan.interest_amount):
                if loan.generate_interest_invoice:
                    loan.interest_invoice_id = loan._create_interest_invoice()
                else:
                    loan.interest_move_id = loan._create_interest_move()
            loan.state = "confirmed"
            loan._ensure_payment_board()
        return True

    def action_set_paid(self):
        for loan in self:
            if loan.schedule_line_ids.filtered(lambda line: line.state != "paid"):
                raise UserError(
                    "Use Pago de Prestamos para registrar los pagos y generar los asientos."
                )
            loan.state = "paid"
        return True

    def action_cancel(self):
        self.filtered(lambda loan: loan.state == "draft").write({"state": "cancelled"})
        return True

    def action_open_capital_move(self):
        self.ensure_one()
        return self._action_open_move(self.capital_move_id)

    def action_open_interest_move(self):
        self.ensure_one()
        move = self.interest_invoice_id or self.interest_move_id
        return self._action_open_move(move)

    def action_open_payment(self):
        self.ensure_one()
        payment = self._ensure_payment_board()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "prestamos_managment.action_prestamos_loan_payment"
        )
        action["res_id"] = payment.id
        action["views"] = [
            (self.env.ref("prestamos_managment.view_prestamos_loan_payment_form").id, "form")
        ]
        action["view_mode"] = "form"
        return action

    def action_open_other_interest_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        action["domain"] = [("prestamos_other_interest_loan_id", "=", self.id)]
        action["context"] = {
            "default_move_type": "in_invoice",
            "default_partner_id": self.partner_id.id,
            "default_prestamos_other_interest_loan_id": self.id,
            "default_invoice_date": fields.Date.context_today(self),
        }
        return action

    def _action_open_move(self, move):
        if not move:
            return False
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action["res_id"] = move.id
        action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
        action["view_mode"] = "form"
        return action

    def _check_ready_to_confirm(self):
        self.ensure_one()
        missing = []
        required_fields = [
            ("partner_id", "Entidad prestadora"),
            ("loan_date", "Fecha del prestamo"),
            ("first_due_date", "Fecha de primera cuota"),
            ("bank_journal_id", "Banco acreditado"),
            ("short_loan_account_id", "Cuenta de prestamo a corto plazo"),
            ("long_loan_account_id", "Cuenta de prestamo a largo plazo"),
            ("short_interest_account_id", "Cuenta de intereses a pagar a corto plazo"),
            ("long_interest_account_id", "Cuenta de intereses a pagar a largo plazo"),
            ("expense_account_id", "Cuenta de gastos de intereses"),
            ("journal_id", "Diario"),
        ]
        for field_name, label in required_fields:
            if not self[field_name]:
                missing.append(label)
        if self.generate_interest_invoice and self.interest_amount and not self.interest_product_id:
            missing.append("Producto de intereses")
        if missing:
            raise UserError("Faltan configurar: %s." % ", ".join(missing))
        if self.generate_interest_invoice and self.interest_amount:
            invalid_interest_accounts = [
                label
                for field_name, label in (
                    ("short_interest_account_id", "Cuenta de intereses a pagar a corto plazo"),
                    ("long_interest_account_id", "Cuenta de intereses a pagar a largo plazo"),
                )
                if self[field_name].account_type != "liability_payable"
            ]
            if invalid_interest_accounts:
                raise UserError(
                    "Las cuentas de intereses a pagar deben ser cuentas de tipo Por pagar: %s."
                    % ", ".join(invalid_interest_accounts)
                )
            purchase_journal = self._get_purchase_journal()
            if not purchase_journal:
                raise UserError(
                    "No se encontro un diario de compras para crear la factura de intereses."
                )
        if not self._get_bank_credit_account():
            raise UserError(
                "El banco acreditado no tiene cuenta transitoria, de suspense o cuenta por defecto."
            )

    def _create_schedule_lines(self):
        self.ensure_one()
        self.schedule_line_ids.unlink()
        due_dates = self._compute_due_dates()
        capital_parts, interest_parts = self._compute_schedule_amounts()
        if self.amortization_system == "aleman":
            self.interest_amount = self.currency_id.round(sum(interest_parts))
        term_base_date = fields.Date.context_today(self)
        commands = []
        for sequence, (due_date, capital, interest) in enumerate(
            zip(due_dates, capital_parts, interest_parts), start=1
        ):
            term_class = self._get_term_class(due_date, term_base_date)
            commands.append(
                Command.create(
                    {
                        "sequence": sequence,
                        "due_date": due_date,
                        "capital_amount": capital,
                        "interest_amount": interest,
                        "capital_term": term_class,
                        "interest_term": term_class,
                        "capital_account_id": self._get_component_account(
                            "capital", term_class
                        ).id,
                        "interest_account_id": self._get_component_account(
                            "interest", term_class
                        ).id,
                        "payment_id": self.payment_id.id if self.payment_id else False,
                    }
                )
            )
        self.schedule_line_ids = commands

    def _compute_due_dates(self):
        self.ensure_one()
        first_due_date = fields.Date.to_date(self.first_due_date)
        if self.installment_frequency == "fortnightly":
            return [
                first_due_date + relativedelta(days=15 * index)
                for index in range(self.installment_count)
            ]
        month_step = self._get_installment_month_step()
        dates = []
        for index in range(self.installment_count):
            if index == 0:
                dates.append(first_due_date)
                continue
            candidate = first_due_date + relativedelta(months=month_step * index)
            if self.due_policy == "end_of_month":
                last_day = calendar.monthrange(candidate.year, candidate.month)[1]
                dates.append(candidate.replace(day=last_day))
            else:
                last_day = calendar.monthrange(candidate.year, candidate.month)[1]
                dates.append(candidate.replace(day=min(first_due_date.day, last_day)))
        return dates

    def _get_installment_month_step(self):
        self.ensure_one()
        return {
            "monthly": 1,
            "bimonthly": 2,
            "quarterly": 3,
            "semiannual": 6,
            "annual": 12,
        }.get(self.installment_frequency, 1)

    def _compute_schedule_amounts(self):
        self.ensure_one()
        if self.amortization_system == "frances":
            return self._compute_french_amounts()
        if self.amortization_system == "aleman":
            return self._compute_german_amounts()
        if self.amortization_system == "americano":
            return self._compute_american_amounts()
        return self._compute_linear_amounts()

    def _compute_french_amounts(self):
        self.ensure_one()
        currency = self.currency_id
        principal = self.capital_amount
        interest_total = self.interest_amount
        periods = self.installment_count
        if currency.is_zero(interest_total):
            return self._split_evenly(principal, periods), [0.0] * periods

        monthly_rate = self._solve_french_monthly_rate(principal, interest_total, periods)
        payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** -periods)
        balance = principal
        capital_parts = []
        interest_parts = []
        for index in range(periods):
            if index == periods - 1:
                capital = currency.round(principal - sum(capital_parts))
                interest = currency.round(interest_total - sum(interest_parts))
            else:
                interest = currency.round(balance * monthly_rate)
                capital = currency.round(payment - interest)
                balance -= capital
            capital_parts.append(capital)
            interest_parts.append(interest)
        return capital_parts, interest_parts

    def _compute_german_amounts(self):
        self.ensure_one()
        currency = self.currency_id
        periods = self.installment_count
        if periods <= 0:
            return [], []
        capital_parts = self._split_evenly(
            self.capital_amount,
            periods,
            residual_position="first",
        )
        balances = []
        balance = self.capital_amount
        for capital in capital_parts:
            balances.append(balance)
            balance -= capital
        total_balance = sum(balances)
        if (
            not total_balance
            or self.interest_rate <= 0.0
            or not self.loan_date
            or not self.first_due_date
        ):
            return capital_parts, [0.0] * periods
        rate = self.interest_rate / 100.0
        due_dates = self._compute_due_dates()
        previous_date = fields.Date.to_date(self.loan_date)
        interest_parts = []
        for balance, due_date in zip(balances, due_dates):
            current_date = fields.Date.to_date(due_date)
            days = (current_date - previous_date).days
            interest = currency.round(balance * rate * days / 365.0)
            interest_parts.append(interest)
            previous_date = current_date
        return capital_parts, interest_parts

    def _sync_german_interest_amount(self):
        self.ensure_one()
        if self.amortization_system != "aleman":
            return
        _capital_parts, interest_parts = self._compute_german_amounts()
        self.interest_amount = self.currency_id.round(sum(interest_parts))

    def _compute_american_amounts(self):
        self.ensure_one()
        periods = self.installment_count
        capital_parts = [0.0] * periods
        capital_parts[-1] = self.capital_amount
        interest_parts = self._split_evenly(self.interest_amount, periods)
        return capital_parts, interest_parts

    def _compute_linear_amounts(self):
        self.ensure_one()
        return (
            self._split_evenly(self.capital_amount, self.installment_count),
            self._split_evenly(self.interest_amount, self.installment_count),
        )

    def _split_evenly(self, amount, periods, residual_position="last"):
        self.ensure_one()
        currency = self.currency_id
        if periods <= 0:
            return []
        if periods == 1:
            return [amount]
        partial = currency.round(amount / periods)
        values = [partial] * periods
        residual = currency.round(amount - sum(values))
        target_index = 0 if residual_position == "first" else -1
        values[target_index] = currency.round(values[target_index] + residual)
        return values

    def _solve_french_monthly_rate(self, principal, target_interest, periods):
        def total_interest(rate):
            payment = principal * rate / (1 - (1 + rate) ** -periods)
            return payment * periods - principal

        low = 0.0
        high = 0.01
        while total_interest(high) < target_interest and high < 100:
            high *= 2
        for _iteration in range(100):
            mid = (low + high) / 2
            if total_interest(mid) < target_interest:
                low = mid
            else:
                high = mid
        return high

    def _get_term_class(self, due_date, base_date):
        threshold = fields.Date.to_date(base_date) + relativedelta(months=12)
        return "long" if fields.Date.to_date(due_date) >= threshold else "short"

    def _get_component_account(self, component, term_class):
        self.ensure_one()
        if component == "capital":
            return self.long_loan_account_id if term_class == "long" else self.short_loan_account_id
        return (
            self.long_interest_account_id
            if term_class == "long"
            else self.short_interest_account_id
        )

    def _create_capital_move(self):
        self.ensure_one()
        line_vals = [
            {
                "name": "%s - Capital acreditado" % self.name,
                "account_id": self._get_bank_credit_account().id,
                "partner_id": self.partner_id.id,
                "debit": self.capital_amount,
                "credit": 0.0,
                "prestamos_loan_id": self.id,
                "prestamos_component": "capital",
            }
        ]
        for schedule in self.schedule_line_ids:
            if self.currency_id.is_zero(schedule.capital_amount):
                continue
            line_vals.append(
                {
                    "name": "%s - Cuota %s capital" % (self.name, schedule.sequence),
                    "account_id": schedule.capital_account_id.id,
                    "partner_id": self.partner_id.id,
                    "date_maturity": schedule.due_date,
                    "debit": 0.0,
                    "credit": schedule.capital_amount,
                    "prestamos_loan_id": self.id,
                    "prestamos_schedule_line_id": schedule.id,
                    "prestamos_component": "capital",
                }
            )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.loan_date,
                "journal_id": self.journal_id.id,
                "ref": "%s - Capital" % self.name,
                "company_id": self.company_id.id,
                "line_ids": [Command.create(vals) for vals in line_vals],
            }
        )
        move.action_post()
        for line in move.line_ids.filtered("prestamos_schedule_line_id"):
            if line.prestamos_component == "capital":
                line.prestamos_schedule_line_id.capital_move_line_id = line
        return move

    def _create_interest_move(self):
        self.ensure_one()
        line_vals = [
            {
                "name": "%s - Intereses devengados" % self.name,
                "account_id": self._get_interest_expense_account().id,
                "partner_id": self.partner_id.id,
                "debit": self.interest_amount,
                "credit": 0.0,
                "analytic_distribution": self.analytic_distribution or False,
                "prestamos_loan_id": self.id,
                "prestamos_component": "interest",
            }
        ]
        for schedule in self.schedule_line_ids:
            if self.currency_id.is_zero(schedule.interest_amount):
                continue
            line_vals.append(
                {
                    "name": "%s - Cuota %s intereses" % (self.name, schedule.sequence),
                    "account_id": schedule.interest_account_id.id,
                    "partner_id": self.partner_id.id,
                    "date_maturity": schedule.due_date,
                    "debit": 0.0,
                    "credit": schedule.interest_amount,
                    "prestamos_loan_id": self.id,
                    "prestamos_schedule_line_id": schedule.id,
                    "prestamos_component": "interest",
                }
            )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.loan_date,
                "journal_id": self.journal_id.id,
                "ref": "%s - Intereses" % self.name,
                "company_id": self.company_id.id,
                "line_ids": [Command.create(vals) for vals in line_vals],
            }
        )
        move.action_post()
        for line in move.line_ids.filtered("prestamos_schedule_line_id"):
            if line.prestamos_component == "interest":
                line.prestamos_schedule_line_id.interest_move_line_id = line
        return move

    def _create_interest_invoice(self):
        self.ensure_one()
        payment_term = self._create_interest_payment_term()
        product = self.interest_product_id
        non_zero_lines = self.schedule_line_ids.filtered(
            lambda line: not self.currency_id.is_zero(line.interest_amount)
        ).sorted("sequence")
        taxes = product.supplier_taxes_id.filtered(
            lambda tax: not tax.company_id or tax.company_id == self.company_id
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_id.id,
                "invoice_date": self.loan_date,
                "date": self.loan_date,
                "journal_id": self._get_purchase_journal().id,
                "invoice_payment_term_id": payment_term.id,
                "ref": "%s - Intereses" % self.name,
                "company_id": self.company_id.id,
                "prestamos_interest_loan_id": self.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": "%s - Cuota %s" % (
                                product.display_name or self.name,
                                schedule.sequence,
                            ),
                            "quantity": 1.0,
                            "price_unit": schedule._get_interest_invoice_price_unit(taxes),
                            "account_id": self._get_interest_expense_account().id,
                            "tax_ids": [Command.set(taxes.ids)],
                            "analytic_distribution": self.analytic_distribution or False,
                        }
                    )
                    for schedule in non_zero_lines
                ],
            }
        )
        self._tag_interest_invoice_terms(invoice)
        invoice.action_post()
        payment_term.sudo().active = False
        return invoice

    def _create_interest_payment_term(self):
        self.ensure_one()
        non_zero_lines = self.schedule_line_ids.filtered(
            lambda line: not self.currency_id.is_zero(line.interest_amount)
        )
        if not non_zero_lines:
            return False
        interest_payment_total = sum(non_zero_lines.mapped("interest_payment_amount"))
        if self.currency_id.is_zero(interest_payment_total):
            interest_payment_total = sum(non_zero_lines.mapped("interest_amount"))
        remaining = 100.0
        commands = []
        for index, schedule in enumerate(non_zero_lines):
            if index == len(non_zero_lines) - 1:
                percent = remaining
            else:
                schedule_interest_payment_amount = schedule.interest_payment_amount
                if self.currency_id.is_zero(schedule_interest_payment_amount):
                    schedule_interest_payment_amount = schedule.interest_amount
                percent = round(
                    schedule_interest_payment_amount / interest_payment_total * 100.0,
                    6,
                )
                remaining -= percent
            commands.append(
                Command.create(
                    {
                        "value": "percent",
                        "value_amount": percent,
                        "delay_type": "days_after",
                        "nb_days": (
                            fields.Date.to_date(schedule.due_date)
                            - fields.Date.to_date(self.loan_date)
                        ).days,
                    }
                )
            )
        return self.env["account.payment.term"].sudo().create(
            {
                "name": "Prestamo %s - intereses" % self.name,
                "company_id": self.company_id.id,
                "line_ids": commands,
                "display_on_invoice": True,
            }
        )

    def _tag_interest_invoice_terms(self, invoice):
        self.ensure_one()
        term_lines = invoice.line_ids.filtered(lambda line: line.display_type == "payment_term").sorted(
            "date_maturity"
        )
        schedule_lines = self.schedule_line_ids.filtered(
            lambda line: not self.currency_id.is_zero(line.interest_amount)
        ).sorted("due_date")
        for account_line, schedule in zip(term_lines, schedule_lines):
            values = {
                "prestamos_loan_id": self.id,
                "prestamos_schedule_line_id": schedule.id,
                "prestamos_component": "interest",
            }
            if schedule.interest_account_id.account_type == "liability_payable":
                values["account_id"] = schedule.interest_account_id.id
            account_line.write(values)
            schedule.interest_move_line_id = account_line

    def _get_interest_expense_account(self):
        self.ensure_one()
        if self.expense_account_id:
            return self.expense_account_id
        product = self.interest_product_id
        if product:
            account = (
                product.property_account_expense_id
                or product.categ_id.property_account_expense_categ_id
            )
            if account:
                return account
        return False

    def _get_purchase_journal(self):
        self.ensure_one()
        return self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company_id.id)],
            limit=1,
        )

    def _get_bank_credit_account(self):
        self.ensure_one()
        journal = self.bank_journal_id
        payment_account = journal.inbound_payment_method_line_ids.filtered(
            "payment_account_id"
        )[:1].payment_account_id
        return payment_account or journal.suspense_account_id or journal.default_account_id

    def _ensure_payment_board(self):
        self.ensure_one()
        payment = self.payment_id
        if not payment:
            payment = self.env["prestamos.loan.payment"].search(
                [("loan_id", "=", self.id)],
                limit=1,
            )
        if not payment:
            payment = self.env["prestamos.loan.payment"].create(
                {
                    "loan_id": self.id,
                    "payment_journal_id": self.bank_journal_id.id,
                }
            )
        if self.payment_id != payment:
            self.payment_id = payment
        self.schedule_line_ids.filtered(lambda line: line.payment_id != payment).write(
            {"payment_id": payment.id}
        )
        return payment

    @api.model
    def _cron_reclassify_short_term_lines(self):
        loans = self.search([("state", "=", "confirmed")])
        today = fields.Date.context_today(self)
        threshold = today + relativedelta(months=12)
        for loan in loans:
            due_lines = loan.schedule_line_ids.filtered(
                lambda line: line.state == "pending" and line.due_date < threshold
            )
            loan._reclassify_lines_to_short_term(due_lines, today)
        return True

    def _reclassify_lines_to_short_term(self, schedule_lines, move_date):
        self.ensure_one()
        for schedule in schedule_lines:
            line_vals = []
            capital_reclassified = False
            interest_reclassified = False
            if (
                schedule.capital_term == "long"
                and schedule.capital_move_line_id
                and schedule.capital_move_line_id.account_id == schedule.capital_account_id
                and not self.currency_id.is_zero(schedule.capital_amount)
            ):
                line_vals += self._prepare_reclassification_lines(
                    schedule,
                    schedule.capital_account_id,
                    self.short_loan_account_id,
                    abs(schedule.capital_move_line_id.balance) or schedule.capital_amount,
                    "capital",
                )
                capital_reclassified = True
            if (
                schedule.interest_term == "long"
                and schedule.interest_move_line_id
                and schedule.interest_move_line_id.account_id == schedule.interest_account_id
                and not self.currency_id.is_zero(abs(schedule.interest_move_line_id.balance))
            ):
                line_vals += self._prepare_reclassification_lines(
                    schedule,
                    schedule.interest_account_id,
                    self.short_interest_account_id,
                    abs(schedule.interest_move_line_id.balance),
                    "interest",
                )
                interest_reclassified = True
            if not line_vals:
                continue
            move = self.env["account.move"].create(
                {
                    "move_type": "entry",
                    "date": move_date,
                    "journal_id": self.journal_id.id,
                    "ref": "%s - Reclasificacion cuota %s" % (self.name, schedule.sequence),
                    "company_id": self.company_id.id,
                    "line_ids": [Command.create(vals) for vals in line_vals],
                }
            )
            move.action_post()
            if capital_reclassified:
                self._reconcile_reclassification_origin(
                    schedule,
                    schedule.capital_move_line_id,
                    move,
                )
            if interest_reclassified:
                self._reconcile_reclassification_origin(
                    schedule,
                    schedule.interest_move_line_id,
                    move,
                )
            updates = {}
            if capital_reclassified:
                updates.update(
                    {
                        "capital_term": "short",
                        "capital_account_id": self.short_loan_account_id.id,
                    }
                )
            if interest_reclassified:
                updates.update(
                    {
                        "interest_term": "short",
                        "interest_account_id": self.short_interest_account_id.id,
                    }
                )
            if updates:
                updates["last_reclassification_move_id"] = move.id
                schedule.write(updates)

    def _prepare_reclassification_lines(self, schedule, origin_account, target_account, amount, component):
        if origin_account == target_account or self.currency_id.is_zero(amount):
            return []
        return [
            {
                "name": "%s - Reclasificacion cuota %s %s" % (
                    self.name,
                    schedule.sequence,
                    component,
                ),
                "account_id": origin_account.id,
                "partner_id": self.partner_id.id,
                "debit": amount,
                "credit": 0.0,
                "prestamos_loan_id": self.id,
                "prestamos_schedule_line_id": schedule.id,
                "prestamos_component": "reclassification",
            },
            {
                "name": "%s - Reclasificacion cuota %s %s" % (
                    self.name,
                    schedule.sequence,
                    component,
                ),
                "account_id": target_account.id,
                "partner_id": self.partner_id.id,
                "debit": 0.0,
                "credit": amount,
                "prestamos_loan_id": self.id,
                "prestamos_schedule_line_id": schedule.id,
                "prestamos_component": "reclassification",
            },
        ]

    def _reconcile_reclassification_origin(self, schedule, origin_line, reclassification_move):
        if not origin_line or not origin_line.account_id.reconcile or origin_line.reconciled:
            return
        debit_lines = reclassification_move.line_ids.filtered(
            lambda line: line.prestamos_schedule_line_id == schedule
            and line.account_id == origin_line.account_id
            and line.debit
        )
        lines = origin_line | debit_lines
        if len(lines) > 1:
            lines.reconcile()


class PrestamosLoanLine(models.Model):
    _name = "prestamos.loan.line"
    _description = "Cuota de prestamo"
    _order = "sequence asc, id asc"
    _check_company_auto = True

    loan_id = fields.Many2one(
        "prestamos.loan",
        string="Prestamo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    payment_id = fields.Many2one(
        "prestamos.loan.payment",
        string="Pago de prestamo",
        index=True,
        ondelete="set null",
    )
    company_id = fields.Many2one(
        "res.company",
        related="loan_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="loan_id.currency_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Cuota", required=True)
    due_date = fields.Date(string="Fecha de vencimiento", required=True)
    capital_amount = fields.Monetary(
        string="Capital",
        currency_field="currency_id",
        required=True,
    )
    interest_amount = fields.Monetary(
        string="Intereses",
        currency_field="currency_id",
        required=True,
    )
    interest_base_amount = fields.Monetary(
        string="Intereses",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    total_amount = fields.Monetary(
        string="Total a pagar",
        currency_field="currency_id",
        compute="_compute_total_amount",
        store=True,
    )
    capital_paid_amount = fields.Monetary(
        string="Capital pagado",
        currency_field="currency_id",
        copy=False,
        readonly=True,
    )
    interest_paid_amount = fields.Monetary(
        string="Intereses pagados",
        currency_field="currency_id",
        copy=False,
        readonly=True,
    )
    capital_residual_amount = fields.Monetary(
        string="Capital pendiente",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    interest_payment_amount = fields.Monetary(
        string="Interes a pagar",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    interest_extra_amount = fields.Monetary(
        string="IVA y otros",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    interest_residual_amount = fields.Monetary(
        string="Interes pendiente",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    payment_total_amount = fields.Monetary(
        string="Total pago",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    payment_residual_amount = fields.Monetary(
        string="Total pendiente de pago",
        currency_field="currency_id",
        compute="_compute_payment_residuals",
        store=True,
    )
    state = fields.Selection(
        [("pending", "Pendiente"), ("paid", "Pagado")],
        string="Estado",
        default="pending",
        required=True,
    )
    capital_term = fields.Selection(
        [("short", "Corto plazo"), ("long", "Largo plazo")],
        string="Plazo capital",
        required=True,
    )
    interest_term = fields.Selection(
        [("short", "Corto plazo"), ("long", "Largo plazo")],
        string="Plazo intereses",
        required=True,
    )
    capital_account_id = fields.Many2one(
        "account.account",
        string="Cuenta capital",
        check_company=True,
    )
    interest_account_id = fields.Many2one(
        "account.account",
        string="Cuenta intereses",
        check_company=True,
    )
    capital_move_line_id = fields.Many2one(
        "account.move.line",
        string="Apunte capital",
        copy=False,
        readonly=True,
    )
    interest_move_line_id = fields.Many2one(
        "account.move.line",
        string="Apunte intereses",
        copy=False,
        readonly=True,
    )
    last_reclassification_move_id = fields.Many2one(
        "account.move",
        string="Ultima reclasificacion",
        copy=False,
        readonly=True,
    )
    payment_move_id = fields.Many2one(
        "account.move",
        string="Asiento de pago",
        copy=False,
        readonly=True,
        check_company=True,
    )
    account_payment_id = fields.Many2one(
        "account.payment",
        string="Pago contable",
        copy=False,
        readonly=True,
        check_company=True,
    )
    payment_date = fields.Date(
        string="Fecha de pago",
        copy=False,
        readonly=True,
    )
    payment_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de pago",
        copy=False,
        readonly=True,
        check_company=True,
    )

    @api.depends("capital_amount", "interest_base_amount")
    def _compute_total_amount(self):
        for line in self:
            line.total_amount = line.capital_amount + line.interest_base_amount

    @api.depends(
        "capital_amount",
        "capital_paid_amount",
        "interest_amount",
        "interest_paid_amount",
        "interest_move_line_id.balance",
        "loan_id.generate_interest_invoice",
        "loan_id.interest_taxes_included",
        "loan_id.interest_product_id",
        "loan_id.interest_product_id.supplier_taxes_id",
        "loan_id.interest_product_id.supplier_taxes_id.amount",
        "loan_id.interest_product_id.supplier_taxes_id.amount_type",
        "loan_id.interest_product_id.supplier_taxes_id.price_include_override",
        "loan_id.partner_id",
        "loan_id.company_id",
    )
    def _compute_payment_residuals(self):
        for line in self:
            (
                interest_base_amount,
                interest_extra_amount,
                estimated_interest_payment_amount,
            ) = line._get_interest_tax_breakdown()
            if line.interest_move_line_id:
                interest_payment_amount = abs(line.interest_move_line_id.balance)
                interest_extra_amount = line.currency_id.round(
                    max(interest_payment_amount - interest_base_amount, 0.0)
                )
            else:
                interest_payment_amount = estimated_interest_payment_amount
            line.interest_base_amount = interest_base_amount
            line.interest_payment_amount = interest_payment_amount
            line.interest_extra_amount = interest_extra_amount
            line.capital_residual_amount = max(
                line.capital_amount - line.capital_paid_amount,
                0.0,
            )
            line.interest_residual_amount = max(
                interest_payment_amount - line.interest_paid_amount,
                0.0,
            )
            line.payment_total_amount = line.capital_amount + interest_payment_amount
            line.payment_residual_amount = (
                line.capital_residual_amount + line.interest_residual_amount
            )

    def _get_interest_taxes(self):
        self.ensure_one()
        product = self.loan_id.interest_product_id
        if not product:
            return self.env["account.tax"]
        return product.supplier_taxes_id.filtered(
            lambda tax: not tax.company_id or tax.company_id == self.company_id
        )

    def _compute_interest_taxes(self, taxes, price_unit=None, force_price_include=None):
        self.ensure_one()
        price_unit = self.interest_amount if price_unit is None else price_unit
        if (
            not taxes
            or not price_unit
            or self.currency_id.is_zero(price_unit)
        ):
            return False
        taxes = taxes.with_company(self.company_id)
        if force_price_include is not None:
            taxes = taxes.with_context(force_price_include=force_price_include)
        return taxes.compute_all(
            price_unit,
            currency=self.currency_id,
            quantity=1.0,
            product=self.loan_id.interest_product_id,
            partner=self.loan_id.partner_id,
        )

    def _get_interest_tax_breakdown(self):
        self.ensure_one()
        loan = self.loan_id
        currency = self.currency_id
        interest_amount = currency.round(self.interest_amount)
        if (
            not loan.generate_interest_invoice
            or not interest_amount
            or currency.is_zero(interest_amount)
        ):
            return interest_amount, 0.0, interest_amount
        taxes = self._get_interest_taxes()
        if not taxes:
            return interest_amount, 0.0, interest_amount

        if loan.interest_taxes_included:
            tax_result = self._compute_interest_taxes(
                taxes,
                price_unit=interest_amount,
                force_price_include=True,
            )
            if not tax_result:
                return interest_amount, 0.0, interest_amount
            interest_base_amount = currency.round(tax_result["total_excluded"])
            interest_payment_amount = interest_amount
        else:
            tax_result = self._compute_interest_taxes(
                taxes,
                price_unit=interest_amount,
                force_price_include=False,
            )
            if not tax_result:
                return interest_amount, 0.0, interest_amount
            interest_base_amount = currency.round(tax_result["total_excluded"])
            interest_payment_amount = currency.round(tax_result["total_included"])

        interest_extra_amount = currency.round(
            max(interest_payment_amount - interest_base_amount, 0.0)
        )
        return interest_base_amount, interest_extra_amount, interest_payment_amount

    def _get_interest_invoice_price_unit(self, taxes):
        self.ensure_one()
        if not taxes:
            return self.interest_base_amount or self.interest_amount
        _interest_base_amount, _interest_extra_amount, target_total = (
            self._get_interest_tax_breakdown()
        )
        direct_result = self._compute_interest_taxes(taxes, price_unit=target_total)
        if not direct_result:
            return target_total
        if self.currency_id.is_zero(direct_result["total_included"] - target_total):
            return target_total

        low = 0.0
        high = target_total
        for _index in range(40):
            mid = (low + high) / 2.0
            tax_result = self._compute_interest_taxes(taxes, price_unit=mid)
            if not tax_result:
                return target_total
            difference = tax_result["total_included"] - target_total
            if self.currency_id.is_zero(difference):
                return self.currency_id.round(mid)
            if difference < 0.0:
                low = mid
            else:
                high = mid
        return self.currency_id.round(high)

    def _get_estimated_interest_extra_amount(self):
        self.ensure_one()
        return self._get_interest_tax_breakdown()[1]

    def action_pay_installment(self):
        self.ensure_one()
        payment = self.payment_id or self.loan_id._ensure_payment_board()
        return payment.action_pay_line(self)

    def action_open_payment_move(self):
        self.ensure_one()
        if not self.payment_move_id:
            return False
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action["res_id"] = self.payment_move_id.id
        action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
        action["view_mode"] = "form"
        return action

    def action_open_account_payment(self):
        self.ensure_one()
        if not self.account_payment_id:
            return False
        return {
            "name": "Pago",
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "res_id": self.account_payment_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_interest_payment_account(self):
        self.ensure_one()
        if self.last_reclassification_move_id and self.interest_account_id:
            return self.interest_account_id
        return (
            self.interest_move_line_id.account_id
            if self.interest_move_line_id
            else self.interest_account_id
        )


class PrestamosLoanAnalyticLine(models.Model):
    _name = "prestamos.loan.analytic.line"
    _description = "Distribucion analitica de prestamo"
    _order = "id asc"

    loan_id = fields.Many2one(
        "prestamos.loan",
        string="Prestamo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analitica",
        required=True,
    )
    percentage = fields.Float(
        string="Porcentaje",
        digits="Percentage Analytic",
        required=True,
        default=100.0,
    )

    _sql_constraints = [
        (
            "percentage_positive",
            "CHECK(percentage > 0 AND percentage <= 100)",
            "El porcentaje debe ser mayor a 0 y menor o igual a 100.",
        )
    ]
