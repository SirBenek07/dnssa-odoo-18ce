from babel.dates import format_date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    py_payment_scheme = fields.Selection(
        related="contract_id.py_payment_scheme",
        string="Esquema de pago",
        store=True,
        readonly=True,
    )
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Factura proveedor",
        copy=False,
        readonly=True,
    )
    py_provision_move_id = fields.Many2one(
        "account.move",
        string="Asiento provision",
        copy=False,
        readonly=True,
    )
    py_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    py_amount_to_pay = fields.Monetary(
        string="Monto a pagar",
        currency_field="py_currency_id",
        compute="_compute_py_amount_to_pay",
        store=True,
    )
    py_payment_state = fields.Selection(
        [("pending", "Pendiente"), ("partial", "Parcial"), ("paid", "Pagada")],
        string="Estado de pago",
        compute="_compute_py_payment_state",
        store=True,
    )
    payment_ids = fields.One2many(
        "account.payment",
        "payroll_payslip_id",
        string="Pagos",
        readonly=True,
    )
    py_amount_paid = fields.Monetary(
        string="Monto pagado",
        currency_field="py_currency_id",
        compute="_compute_py_payment_amounts",
        store=True,
    )
    py_amount_due = fields.Monetary(
        string="Saldo a pagar",
        currency_field="py_currency_id",
        compute="_compute_py_payment_amounts",
        store=True,
    )

    @api.depends("line_ids.total", "line_ids.category_id.code")
    def _compute_py_amount_to_pay(self):
        for slip in self:
            net_lines = slip.line_ids.filtered(
                lambda line: line.category_id and line.category_id.code == "NET"
            )
            if net_lines:
                slip.py_amount_to_pay = sum(net_lines.mapped("total"))
            else:
                slip.py_amount_to_pay = 0.0

    @api.depends("state", "py_payment_scheme", "paid", "vendor_bill_id.payment_state", "py_amount_due")
    def _compute_py_payment_state(self):
        for slip in self:
            if slip.state != "done":
                slip.py_payment_state = "pending"
                continue
            if slip.py_payment_scheme == "factura_proveedor":
                if not slip.vendor_bill_id:
                    slip.py_payment_state = "pending"
                elif slip.vendor_bill_id.payment_state in ("paid", "in_payment"):
                    slip.py_payment_state = "paid"
                elif slip.vendor_bill_id.payment_state == "partial":
                    slip.py_payment_state = "partial"
                else:
                    slip.py_payment_state = "pending"
            else:
                if slip.py_amount_due <= 0:
                    slip.py_payment_state = "paid"
                elif slip.py_amount_paid > 0:
                    slip.py_payment_state = "partial"
                else:
                    slip.py_payment_state = "pending"

    @api.depends(
        "state",
        "py_payment_scheme",
        "py_amount_to_pay",
        "payment_ids.state",
        "payment_ids.amount",
        "vendor_bill_id.state",
        "vendor_bill_id.amount_total",
        "vendor_bill_id.amount_residual",
    )
    def _compute_py_payment_amounts(self):
        for slip in self:
            if slip.py_payment_scheme == "factura_proveedor":
                if slip.vendor_bill_id and slip.vendor_bill_id.state == "posted":
                    residual = abs(slip.vendor_bill_id.amount_residual)
                    total = abs(slip.vendor_bill_id.amount_total)
                    slip.py_amount_paid = total - residual
                    slip.py_amount_due = residual
                else:
                    slip.py_amount_paid = 0.0
                    slip.py_amount_due = slip.py_amount_to_pay
                slip.paid = slip.py_amount_due <= 0 and slip.py_amount_to_pay > 0
                continue

            posted_amount = sum(
                slip.payment_ids.filtered(
                    lambda p: p.state in ("paid", "in_process")
                ).mapped("amount")
            )
            amount_due = slip.py_amount_to_pay - posted_amount
            slip.py_amount_paid = posted_amount
            slip.py_amount_due = amount_due if amount_due > 0 else 0.0
            slip.paid = slip.py_amount_due <= 0 and slip.py_amount_to_pay > 0

    def _compute_payslip_line(self, rule, localdict, lines_dict):
        localdict, lines_dict = super()._compute_payslip_line(rule, localdict, lines_dict)
        slip = localdict["payslip"]
        if slip.py_payment_scheme != "ips_dependiente":
            return localdict, lines_dict

        contract = localdict["contract"]
        key = (rule.code or "id" + str(rule.id)) + "-" + str(contract.id)
        if key not in lines_dict or not rule.code:
            return localdict, lines_dict

        forced_amount = None
        if rule.code.startswith("IPS_BASIC"):
            forced_amount = contract.wage * 0.91
        elif rule.code.startswith("IPS_EMP_9"):
            forced_amount = contract.wage * 0.09
        elif rule.code.startswith("IPS_PAT_165"):
            forced_amount = contract.wage * 0.165
        elif rule.code.startswith("IPS_NET"):
            forced_amount = contract.wage * 0.91

        if forced_amount is None:
            return localdict, lines_dict

        line = lines_dict[key]
        old_total = line.get("total", 0.0)
        line["amount"] = forced_amount
        line["quantity"] = 1.0
        line["rate"] = 100.0
        line["total"] = forced_amount

        if rule.code:
            localdict[rule.code] = forced_amount

        localdict = slip._sum_salary_rule_category(
            localdict, rule.category_id, forced_amount - old_total
        )
        lines_dict[key] = line
        return localdict, lines_dict

    def _compute_name(self):
        for record in self:
            if record.py_payment_scheme in ("ips_dependiente", "factura_proveedor"):
                month_year = format_date(
                    record.date_from or fields.Date.today(),
                    format="MMMM-y",
                    locale="es_PY",
                )
                record.name = _("Recibo de salarios de %(name)s para %(period)s") % {
                    "name": record.employee_id.name,
                    "period": month_year,
                }
            else:
                super(HrPayslip, record)._compute_name()

    def action_payslip_done(self):
        factura_slips = self.filtered(
            lambda slip: slip.py_payment_scheme == "factura_proveedor"
        )
        normal_slips = self - factura_slips

        res = True
        if normal_slips:
            res = super(HrPayslip, normal_slips).action_payslip_done()

        for slip in factura_slips:
            if (
                not self.env.context.get("without_compute_sheet")
                and not slip.prevent_compute_on_confirm
            ):
                slip.compute_sheet()
            if not slip.number:
                slip.number = self.env["ir.sequence"].next_by_code("salary.slip")
            slip.write({"state": "done"})
            slip._create_vendor_bill()
            slip._create_factura_provision_move()

        return res

    def action_payslip_cancel(self):
        factura_slips = self.filtered(
            lambda slip: slip.py_payment_scheme == "factura_proveedor"
        )
        normal_slips = self - factura_slips

        res = True
        if normal_slips:
            res = super(HrPayslip, normal_slips).action_payslip_cancel()

        for slip in factura_slips:
            # For vendor-bill payroll flow, allow cancellation of done payslips as long
            # as the linked vendor bill is not paid. This enables corrections by first
            # cancelling the bill and then the payslip in one flow.
            if slip.refunded_id and slip.refunded_id.state != "cancel":
                raise ValidationError(
                    _(
                        "To cancel the Original Payslip the Refunded Payslip "
                        "needs to be canceled first!"
                    )
                )
            slip._cancel_vendor_bill()
            slip._cancel_factura_provision_move()

        if factura_slips:
            factura_slips.write({"state": "cancel"})

        return res

    def _cancel_vendor_bill(self):
        self.ensure_one()
        if self.env.context.get("skip_vendor_bill_cancel_sync"):
            return
        bill = self.vendor_bill_id
        if not bill:
            return
        if bill.payment_state in ("paid", "in_payment"):
            raise UserError(
                _(
                    "No se puede cancelar la nomina %(slip)s porque su factura "
                    "proveedor %(bill)s ya tiene pagos registrados."
                )
                % {"slip": self.display_name, "bill": bill.display_name}
            )
        if bill.state == "posted":
            bill.button_draft()
        if bill.state == "draft":
            bill.with_context(skip_payroll_bill_cancel_sync=True).button_cancel()

    def _get_factura_provision_lines(self):
        self.ensure_one()
        return self.line_ids.sorted(lambda l: (l.sequence, l.id)).filtered(
            lambda l: l.salary_rule_id
            and l.code
            and "AGUINALDO_PROV" in l.code
            and not self.company_id.currency_id.is_zero(abs(l.total))
            and l.salary_rule_id.account_debit
            and l.salary_rule_id.account_credit
        )

    def _create_factura_provision_move(self):
        self.ensure_one()
        if self.py_payment_scheme != "factura_proveedor":
            return False
        if self.py_provision_move_id:
            return self.py_provision_move_id

        provision_lines = self._get_factura_provision_lines()
        if not provision_lines:
            return False
        if not self.journal_id:
            raise UserError(
                _(
                    "La nomina %(slip)s no tiene diario contable configurado para registrar la provision."
                )
                % {"slip": self.display_name}
            )

        currency = self.company_id.currency_id
        date = self.date or self.date_to or fields.Date.today()
        partner_id = self._get_employee_partner_id_for_payment(
            provision_lines[:1]
        ) if provision_lines else False
        line_label_suffix = self._get_provision_move_line_label_suffix()
        line_ids = []
        debit_sum = 0.0
        credit_sum = 0.0

        for line in provision_lines:
            amount = currency.round(self.credit_note and -line.total or line.total)
            if currency.is_zero(amount):
                continue
            analytic = {}
            if self.contract_id.analytic_account_id:
                analytic[self.contract_id.analytic_account_id.id] = 100
            elif line.salary_rule_id.analytic_account_id:
                analytic[line.salary_rule_id.analytic_account_id.id] = 100

            debit_vals = self._prepare_debit_line(
                line, amount, date, line.salary_rule_id.account_debit.id, analytic
            )
            credit_vals = self._prepare_credit_line(
                line, amount, date, line.salary_rule_id.account_credit.id, analytic
            )
            if line_label_suffix:
                debit_vals["name"] = f"{line.name} - {line_label_suffix}"
                credit_vals["name"] = f"{line.name} - {line_label_suffix}"
            if partner_id:
                debit_vals["partner_id"] = partner_id
                credit_vals["partner_id"] = partner_id
            line_ids.append((0, 0, debit_vals))
            line_ids.append((0, 0, credit_vals))
            debit_sum += debit_vals["debit"] - debit_vals["credit"]
            credit_sum += credit_vals["credit"] - credit_vals["debit"]

        if not line_ids:
            return False

        if currency.compare_amounts(credit_sum, debit_sum) == -1:
            if not self.journal_id.default_account_id:
                raise UserError(
                    _(
                        'El diario "%(journal)s" no tiene cuenta por defecto para ajuste de provision.'
                    )
                    % {"journal": self.journal_id.display_name}
                )
            line_ids.append(
                (0, 0, self._prepare_adjust_credit_line(currency, credit_sum, debit_sum, self.journal_id, date))
            )
        elif currency.compare_amounts(debit_sum, credit_sum) == -1:
            if not self.journal_id.default_account_id:
                raise UserError(
                    _(
                        'El diario "%(journal)s" no tiene cuenta por defecto para ajuste de provision.'
                    )
                    % {"journal": self.journal_id.display_name}
                )
            line_ids.append(
                (0, 0, self._prepare_adjust_debit_line(currency, credit_sum, debit_sum, self.journal_id, date))
            )

        move = self.env["account.move"].create(
            {
                "ref": "%s/PROV" % (self.number or self.name),
                "date": date,
                "journal_id": self.journal_id.id,
                "narration": _("Provision aguinaldo de %(slip)s") % {"slip": self.display_name},
                "line_ids": line_ids,
            }
        )
        move.action_post()
        self.py_provision_move_id = move.id
        return move

    def _cancel_factura_provision_move(self):
        self.ensure_one()
        move = self.py_provision_move_id
        if not move:
            return
        if move.state == "posted":
            move.button_draft()
        if move.state == "draft":
            move.button_cancel()
        self.py_provision_move_id = False

    def _get_provision_move_line_label_suffix(self):
        self.ensure_one()
        month_year = format_date(
            self.date_to or self.date_from or fields.Date.today(),
            format="MMMM-y",
            locale="es_PY",
        )
        return _("%(employee)s / %(period)s") % {
            "employee": self.employee_id.name,
            "period": month_year,
        }

    def _create_vendor_bill(self):
        self.ensure_one()
        if self.vendor_bill_id:
            return self.vendor_bill_id

        contract = self.contract_id
        product = self._validate_vendor_bill_config(contract)
        vendor = contract.py_vendor_partner_id
        if not self.py_amount_to_pay:
            raise UserError(
                _(
                    "No hay monto neto para facturar en la nomina %(slip)s."
                )
                % {"slip": self.display_name}
            )

        taxes = product.supplier_taxes_id.filtered(
            lambda tax: tax.company_id == self.company_id
        ) or product.supplier_taxes_id.filtered(lambda tax: not tax.company_id)

        expense_account = self._get_vendor_bill_expense_account(product)

        bill_vals = {
            "move_type": "in_invoice",
            "partner_id": vendor.id,
            "journal_id": (
                contract.py_vendor_journal_id.id
                or contract.company_id.py_default_vendor_journal_id.id
                or False
            ),
            "invoice_date": self.date_to or fields.Date.today(),
            "invoice_origin": self.number or self.name,
            "ref": self.number or self.name,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": self._get_vendor_bill_line_name(product),
                        "product_id": product.id,
                        "price_unit": self.py_amount_to_pay,
                        "quantity": 1.0,
                        "account_id": expense_account.id if expense_account else False,
                        "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
                    },
                )
            ],
        }
        bill = self.env["account.move"].create(bill_vals)
        self._apply_vendor_payable_account(bill)
        self.vendor_bill_id = bill.id
        return bill

    def _get_vendor_bill_expense_account(self, product):
        """Prefer the expense account configured on payroll salary rules.

        For factura-based payroll, the vendor bill line should mirror the payroll
        accounting setup. If no suitable salary rule account is configured, fall
        back to the product expense account.
        """
        self.ensure_one()

        # Prefer the first positive non-NET line with an explicit debit account.
        candidate_lines = self.line_ids.sorted(lambda l: (l.sequence, l.id)).filtered(
            lambda l: l.total > 0
            and l.salary_rule_id
            and l.salary_rule_id.account_debit
            and (l.category_id.code if l.category_id else "") != "NET"
        )
        if candidate_lines:
            return candidate_lines[0].salary_rule_id.account_debit

        # Fallback: if only NET carries the configured account, use it.
        net_lines = self.line_ids.sorted(lambda l: (l.sequence, l.id)).filtered(
            lambda l: l.total > 0 and l.salary_rule_id and l.salary_rule_id.account_debit
        )
        if net_lines:
            return net_lines[0].salary_rule_id.account_debit

        return (
            product.property_account_expense_id
            or product.categ_id.property_account_expense_categ_id
        )

    def _get_vendor_bill_line_name(self, product):
        self.ensure_one()
        month_year = format_date(
            self.date_to or fields.Date.today(),
            format="MMMM-y",
            locale="es_PY",
        )
        return _("Recibo de salarios de %(employee)s para %(period)s") % {
            "employee": self.employee_id.name,
            "period": month_year,
        }

    def _apply_vendor_payable_account(self, bill):
        self.ensure_one()
        payable_account = self.contract_id.py_vendor_payable_account_id
        if not payable_account:
            return
        payable_lines = bill.line_ids.filtered(lambda l: l.display_type == "payment_term")
        if not payable_lines:
            payable_lines = bill.line_ids.filtered(
                lambda l: l.account_id.account_type == "liability_payable"
            )
        if payable_lines:
            payable_lines.with_context(check_move_validity=False).write(
                {"account_id": payable_account.id}
            )

    def _validate_vendor_bill_config(self, contract):
        product = (
            contract.py_vendor_product_id
            or contract.company_id.py_default_vendor_product_id
        )
        missing_fields = []
        if not contract.py_vendor_partner_id:
            missing_fields.append(_("Proveedor para facturacion"))
        if not product:
            missing_fields.append(_("Producto para facturacion"))
        if missing_fields:
            raise UserError(
                _(
                    "Falta configurar campos en el contrato %(contract)s para "
                    "factura de proveedor: %(fields)s."
                )
                % {
                    "contract": contract.display_name,
                    "fields": ", ".join(missing_fields),
                }
            )
        return product

    def _get_ips_base_accounts(self, line):
        basic_line = line.slip_id.line_ids.filtered(
            lambda l: l.contract_id == line.contract_id and l.code and l.code.startswith("IPS_BASIC")
        )[:1]
        if not basic_line:
            return False, False
        return (
            basic_line.salary_rule_id.account_debit.id,
            basic_line.salary_rule_id.account_credit.id,
        )

    def _get_employee_partner_id_for_payment(self, line):
        partner = (
            line.employee_id.work_contact_id
            or line.employee_id.address_home_id
            or line.employee_id.address_id
        )
        return partner.id if partner else False

    def _get_ips_payment_account_id(self):
        self.ensure_one()
        payable_lines = self.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        if not payable_lines:
            return False
        # Prefer the account with highest payable balance in payroll move.
        line = payable_lines.sorted(lambda l: abs(l.balance), reverse=True)[0]
        return line.account_id.id

    def _prepare_debit_line(
        self, line, amount, date, debit_account_id, move_line_analytic_ids
    ):
        if (
            line.slip_id.py_payment_scheme == "ips_dependiente"
            and line.code
            and line.code.startswith("IPS_EMP_9")
        ):
            base_debit, base_credit = self._get_ips_base_accounts(line)
            if base_credit:
                debit_account_id = base_credit
        vals = super()._prepare_debit_line(
            line, amount, date, debit_account_id, move_line_analytic_ids
        )
        account = self.env["account.account"].browse(vals["account_id"])
        if (
            line.slip_id.py_payment_scheme == "ips_dependiente"
            and account.account_type == "liability_payable"
            and not vals.get("partner_id")
        ):
            vals["partner_id"] = self._get_employee_partner_id_for_payment(line)
        return vals

    def _prepare_credit_line(
        self, line, amount, date, credit_account_id, move_line_analytic_ids
    ):
        if (
            line.slip_id.py_payment_scheme == "ips_dependiente"
            and line.code
            and line.code.startswith("IPS_EMP_9")
        ):
            base_debit, base_credit = self._get_ips_base_accounts(line)
            if base_debit:
                credit_account_id = base_debit
        vals = super()._prepare_credit_line(
            line, amount, date, credit_account_id, move_line_analytic_ids
        )
        account = self.env["account.account"].browse(vals["account_id"])
        if (
            line.slip_id.py_payment_scheme == "ips_dependiente"
            and account.account_type == "liability_payable"
            and not vals.get("partner_id")
        ):
            vals["partner_id"] = self._get_employee_partner_id_for_payment(line)
        return vals

    def action_open_payroll_payment(self):
        self.ensure_one()
        if self.state != "done":
            raise UserError(_("Solo se puede pagar una nomina confirmada."))

        if self.py_payment_scheme == "factura_proveedor":
            if not self.vendor_bill_id:
                self._create_vendor_bill()
            if self.vendor_bill_id.state != "posted":
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Completar factura proveedor"),
                    "res_model": "account.move",
                    "view_mode": "form",
                    "res_id": self.vendor_bill_id.id,
                    "target": "current",
                }
            return self.vendor_bill_id.action_register_payment()

        if self.py_amount_due <= 0:
            raise UserError(_("Esta nomina ya fue marcada como pagada."))

        partner = (
            self.employee_id.work_contact_id
            or self.employee_id.address_home_id
            or self.employee_id.address_id
        )
        if not partner:
            raise UserError(
                _(
                    "El empleado %(emp)s no tiene un contacto para registrar el pago."
                )
                % {"emp": self.employee_id.name}
            )
        if self.py_amount_to_pay <= 0:
            raise UserError(
                _("El monto a pagar debe ser mayor que cero para registrar un pago.")
            )

        journal = self.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if not journal:
            raise UserError(
                _(
                    "No existe diario de banco/caja en la compania %(company)s."
                )
                % {"company": self.company_id.display_name}
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar pago de nomina"),
            "res_model": "account.payment",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_payment_type": "outbound",
                "default_partner_type": "supplier",
                "default_partner_id": partner.id,
                "default_amount": self.py_amount_due,
                "default_journal_id": journal.id,
                "default_destination_account_id": self._get_ips_payment_account_id(),
                "default_date": self.date_to or fields.Date.today(),
                "default_ref": self.number or self.name,
                "default_payroll_payslip_id": self.id,
            },
        }
