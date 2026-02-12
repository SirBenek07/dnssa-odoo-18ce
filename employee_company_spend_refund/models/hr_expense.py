from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round


class HrExpense(models.Model):
    _inherit = "hr.expense"

    is_company_spend_refund = fields.Boolean(
        string="Gasto de empresa pagado por empleado",
        help="Vincula una factura de proveedor existente y transfiere su saldo "
        "pendiente a una deuda de reembolso con el empleado.",
        tracking=True,
    )
    company_vendor_bill_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura de proveedor",
        domain=(
            "[('company_id', '=', company_id),"
            " ('move_type', '=', 'in_invoice'),"
            " ('state', '=', 'posted'),"
            " ('payment_state', 'in', ('not_paid', 'partial'))]"
        ),
        copy=False,
    )
    company_reclass_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Asiento de reclasificacion",
        readonly=True,
        copy=False,
    )

    @api.constrains("is_company_spend_refund", "payment_mode", "company_vendor_bill_id")
    def _check_company_spend_refund_requirements(self):
        for expense in self:
            if not expense.is_company_spend_refund:
                continue
            if expense.payment_mode != "own_account":
                raise ValidationError(
                    _(
                        "Este flujo solo permite 'Pagado por: Empleado (a reembolsar)'."
                    )
                )
            if not expense.company_vendor_bill_id:
                raise ValidationError(
                    _("Seleccione una factura de proveedor publicada y pendiente de pago.")
                )
            if expense.company_vendor_bill_id.move_type != "in_invoice":
                raise ValidationError(_("Solo se permiten facturas de proveedor."))
            if expense.company_vendor_bill_id.company_id != expense.company_id:
                raise ValidationError(
                    _("La compania de la factura debe coincidir con la del gasto.")
                )
            if expense.company_vendor_bill_id.state != "posted":
                raise ValidationError(_("La factura de proveedor debe estar publicada."))
            if expense.company_vendor_bill_id.payment_state not in {"not_paid", "partial"}:
                raise ValidationError(
                    _("La factura de proveedor debe estar pendiente (No pagada o Parcialmente pagada).")
                )
            if (
                expense.vendor_id
                and expense.company_vendor_bill_id.partner_id
                and expense.vendor_id != expense.company_vendor_bill_id.partner_id
            ):
                raise ValidationError(_("El proveedor debe coincidir con la factura seleccionada."))

    @api.constrains("is_company_spend_refund", "company_vendor_bill_id")
    def _check_company_spend_refund_no_duplicate_bill(self):
        for expense in self.filtered(
            lambda e: e.is_company_spend_refund and e.company_vendor_bill_id
        ):
            duplicate = self.search(
                [
                    ("id", "!=", expense.id),
                    ("is_company_spend_refund", "=", True),
                    ("company_vendor_bill_id", "=", expense.company_vendor_bill_id.id),
                    ("state", "!=", "refused"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "La factura %(bill)s ya esta vinculada al gasto %(expense)s.",
                        bill=expense.company_vendor_bill_id.display_name,
                        expense=duplicate.display_name,
                    )
                )

    @api.onchange("is_company_spend_refund")
    def _onchange_is_company_spend_refund(self):
        for expense in self:
            if expense.is_company_spend_refund:
                expense.payment_mode = "own_account"
                expense.product_id = False
                expense.product_uom_id = False
            else:
                expense.company_vendor_bill_id = False

    @api.onchange("payment_mode")
    def _onchange_payment_mode_company_spend_refund(self):
        for expense in self.filtered(lambda e: e.payment_mode != "own_account"):
            expense.is_company_spend_refund = False
            expense.company_vendor_bill_id = False

    @api.onchange("company_vendor_bill_id")
    def _onchange_company_vendor_bill_id(self):
        for expense in self.filtered(lambda e: e.is_company_spend_refund and e.company_vendor_bill_id):
            expense.vendor_id = expense.company_vendor_bill_id.partner_id
            if expense.company_vendor_bill_id.currency_id:
                expense.currency_id = expense.company_vendor_bill_id.currency_id
            expense.total_amount_currency = expense.company_vendor_bill_id.amount_residual

    def action_open_company_vendor_bill(self):
        self.ensure_one()
        if not self.company_vendor_bill_id:
            raise UserError(_("No hay factura de proveedor vinculada a este gasto."))
        return self.company_vendor_bill_id.get_formview_action()

    def action_open_company_reclass_move(self):
        self.ensure_one()
        if not self.company_reclass_move_id:
            raise UserError(
                _("Aun no se genero el asiento de reclasificacion para este gasto.")
            )
        return self.company_reclass_move_id.get_formview_action()

    def _get_company_spend_refund_partner(self):
        self.ensure_one()
        partner = self.employee_id.sudo().work_contact_id.with_company(self.company_id)
        if not partner:
            raise UserError(
                _(
                    "No se encontro contacto laboral para el empleado %(employee)s.",
                    employee=self.employee_id.name,
                )
            )
        return partner

    def _get_company_spend_refund_account(self, partner):
        self.ensure_one()
        return (
            self.company_id.employee_spend_refund_account_id
            or partner.property_account_payable_id
            or partner.parent_id.property_account_payable_id
        )

    def _get_company_spend_reclass_journal(self):
        self.ensure_one()
        if self.sheet_id and self.sheet_id.journal_id.type == "general":
            return self.sheet_id.journal_id
        return self.env["account.journal"].search(
            [
                ("type", "=", "general"),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )

    def _prepare_company_spend_reclass_vals(
        self, reclass_journal, vendor_payable_lines, employee_partner, employee_account
    ):
        self.ensure_one()
        reference = _(
            "Reclasificacion gasto de empresa - %(expense)s", expense=self.display_name
        )
        line_commands = []
        total_balance = 0.0

        for vendor_line in vendor_payable_lines:
            residual_balance = -vendor_line.amount_residual
            total_balance += residual_balance
            line_vals = {
                "name": reference,
                "account_id": vendor_line.account_id.id,
                "partner_id": vendor_line.partner_id.id,
                "debit": residual_balance if residual_balance > 0 else 0.0,
                "credit": -residual_balance if residual_balance < 0 else 0.0,
                "date_maturity": vendor_line.date_maturity,
            }
            if vendor_line.currency_id:
                line_vals.update(
                    {
                        "currency_id": vendor_line.currency_id.id,
                        "amount_currency": -vendor_line.amount_residual_currency,
                    }
                )
            line_commands.append(Command.create(line_vals))

        employee_line_vals = {
            "name": reference,
            "account_id": employee_account.id,
            "partner_id": employee_partner.id,
            "debit": 0.0,
            "credit": total_balance,
            "date_maturity": self.sheet_id.accounting_date
            or self.date
            or fields.Date.context_today(self),
        }

        if vendor_payable_lines and all(vendor_payable_lines.mapped("currency_id")):
            currency = vendor_payable_lines[0].currency_id
            employee_line_vals.update(
                {
                    "currency_id": currency.id,
                    "amount_currency": sum(vendor_payable_lines.mapped("amount_residual_currency")),
                }
            )
        line_commands.append(Command.create(employee_line_vals))

        return {
            "move_type": "entry",
            "company_id": self.company_id.id,
            "journal_id": reclass_journal.id,
            "date": self.sheet_id.accounting_date
            or self.date
            or fields.Date.context_today(self),
            "ref": reference,
            "expense_sheet_id": self.sheet_id.id,
            "line_ids": line_commands,
        }

    def _create_company_spend_refund_moves(self):
        self.ensure_one()
        if not self.is_company_spend_refund:
            return self.env["account.move"], self.env["account.move"]
        if self.company_reclass_move_id:
            raise UserError(
                _(
                    "La reclasificacion ya fue generada para el gasto %(name)s.",
                    name=self.display_name,
                )
            )
        if not self.company_vendor_bill_id:
            raise UserError(_("Seleccione una factura de proveedor antes de aprobar."))

        vendor_bill = self.company_vendor_bill_id.with_company(self.company_id)
        if vendor_bill.state != "posted" or vendor_bill.move_type != "in_invoice":
            raise UserError(_("El documento seleccionado no es una factura de proveedor publicada."))

        vendor_payable_lines = vendor_bill.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == "liability_payable"
                and line.partner_id == vendor_bill.partner_id
                and not (line.currency_id or line.company_currency_id).is_zero(
                    line.amount_residual_currency if line.currency_id else line.amount_residual
                )
            )
        )
        if not vendor_payable_lines:
            raise UserError(
                _(
                    "La factura %(bill)s no tiene lineas de CxP pendientes.",
                    bill=vendor_bill.display_name,
                )
            )

        reclass_journal = self._get_company_spend_reclass_journal()
        if not reclass_journal:
            raise UserError(
                _("No se encontro un diario miscelaneo para la compania %(company)s.", company=self.company_id.display_name)
            )

        employee_partner = self._get_company_spend_refund_partner()
        employee_account = self._get_company_spend_refund_account(employee_partner)
        if not employee_account:
            raise UserError(
                _(
                    "No hay una cuenta por pagar configurada para %(employee)s. "
                    "Defina una en el partner del empleado o en Ajustes de Contabilidad.",
                    employee=self.employee_id.name,
                )
            )

        reclass_move = (
            self.env["account.move"]
            .sudo()
            .with_company(self.company_id)
            .create(
                self._prepare_company_spend_reclass_vals(
                    reclass_journal,
                    vendor_payable_lines,
                    employee_partner,
                    employee_account,
                )
            )
        )
        reclass_move.action_post()

        reclass_vendor_lines = reclass_move.line_ids.filtered(
            lambda line: (
                line.partner_id == vendor_bill.partner_id
                and line.account_id in vendor_payable_lines.account_id
                and not line.reconciled
            )
        )
        (vendor_payable_lines | reclass_vendor_lines).reconcile()

        self.write({"company_reclass_move_id": reclass_move.id, "vendor_id": vendor_bill.partner_id.id})
        return vendor_bill, reclass_move

    def _get_default_expense_sheet_values(self):
        regular_expenses = self.filtered(lambda expense: not expense.is_company_spend_refund)
        if regular_expenses and regular_expenses != self:
            raise UserError(
                _(
                    "No mezcle gastos normales con gastos de empresa pagados por empleado en el mismo reporte."
                )
            )
        if regular_expenses:
            return super(HrExpense, regular_expenses)._get_default_expense_sheet_values()

        expenses_with_amount = self.filtered(
            lambda expense: not (
                expense.currency_id.is_zero(expense.total_amount_currency)
                or expense.company_currency_id.is_zero(expense.total_amount)
                or float_round(
                    expense.quantity,
                    precision_rounding=(expense.product_uom_id.rounding or 1.0),
                )
                == 0.0
            )
        )
        if any(expense.state != "draft" or expense.sheet_id for expense in expenses_with_amount):
            raise UserError(_("No puede reportar dos veces la misma linea."))
        if not expenses_with_amount:
            raise UserError(_("No puede reportar gastos sin importe."))
        if len(expenses_with_amount.mapped("employee_id")) != 1:
            raise UserError(
                _("No puede reportar gastos de empleados distintos en el mismo reporte.")
            )
        if len(expenses_with_amount.mapped("company_id")) != 1:
            raise UserError(
                _("No puede reportar gastos de companias distintas en el mismo reporte.")
            )
        if any(expense.payment_mode != "own_account" for expense in expenses_with_amount):
            raise UserError(
                _("Este flujo requiere 'Pagado por: Empleado (a reembolsar)'.")
            )
        if any(not expense.company_vendor_bill_id for expense in expenses_with_amount):
            raise UserError(
                _("Todos los gastos deben tener una factura de proveedor vinculada.")
            )

        sheet_name = self.env["hr.expense.sheet"]._get_default_sheet_name(expenses_with_amount)
        return [
            {
                "company_id": expenses_with_amount.company_id.id,
                "employee_id": expenses_with_amount[0].employee_id.id,
                "name": sheet_name,
                "expense_line_ids": [Command.set(expenses_with_amount.ids)],
                "state": "draft",
            }
        ]
