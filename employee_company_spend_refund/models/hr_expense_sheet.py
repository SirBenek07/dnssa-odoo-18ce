from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import clean_context


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _is_company_spend_refund_sheet(self):
        self.ensure_one()
        return (
            self.payment_mode == "own_account"
            and bool(self.expense_line_ids)
            and all(self.expense_line_ids.mapped("is_company_spend_refund"))
        )

    @api.depends("account_move_ids.payment_state", "account_move_ids.amount_residual")
    def _compute_from_account_move_ids(self):
        super()._compute_from_account_move_ids()
        for sheet in self.filtered(lambda s: s._is_company_spend_refund_sheet()):
            posted_moves = sheet.account_move_ids.filtered(lambda move: move.state == "posted")
            if not posted_moves:
                sheet.amount_residual = 0.0
                sheet.payment_state = "not_paid"
                continue

            payable_lines = posted_moves.line_ids.filtered(
                lambda line: line.account_id.account_type == "liability_payable"
            )
            residual = sum(payable_lines.mapped("amount_residual"))
            sheet.amount_residual = residual

            if not payable_lines:
                sheet.payment_state = "not_paid"
            elif sheet.company_currency_id.is_zero(residual):
                sheet.payment_state = "paid"
            else:
                sheet.payment_state = "partial"

    @api.constrains("expense_line_ids")
    def _check_company_spend_refund_expense_mix(self):
        for sheet in self:
            flagged_lines = sheet.expense_line_ids.filtered("is_company_spend_refund")
            if flagged_lines and (sheet.expense_line_ids - flagged_lines):
                raise ValidationError(
                    _(
                        "No puede mezclar gastos normales y gastos de empresa pagados "
                        "por empleado en el mismo reporte."
                    )
                )

    def _do_create_moves(self):
        self = self.with_context(clean_context(self.env.context))
        custom_sheets = self.filtered(
            lambda sheet: (
                sheet.payment_mode == "own_account"
                and sheet.expense_line_ids
                and all(sheet.expense_line_ids.mapped("is_company_spend_refund"))
            )
        )
        regular_sheets = self - custom_sheets

        moves = self.env["account.move"]
        if regular_sheets:
            moves |= super(HrExpenseSheet, regular_sheets)._do_create_moves()

        for sheet in custom_sheets:
            sheet.accounting_date = (
                sheet.accounting_date or sheet._calculate_default_accounting_date()
            )
            for expense in sheet.expense_line_ids:
                _, reclass_move = expense.sudo()._create_company_spend_refund_moves()
                moves |= reclass_move

        return moves

    def action_register_payment(self):
        custom_sheets = self.filtered(lambda sheet: sheet._is_company_spend_refund_sheet())
        regular_sheets = self - custom_sheets

        if regular_sheets and custom_sheets:
            raise UserError(
                _("Seleccione reportes del mismo tipo para registrar el pago.")
            )
        if regular_sheets:
            return super(HrExpenseSheet, regular_sheets).action_register_payment()

        payable_lines = custom_sheets.account_move_ids.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == "liability_payable"
                and not line.reconciled
                and not (line.currency_id or line.company_currency_id).is_zero(
                    line.amount_residual_currency if line.currency_id else line.amount_residual
                )
            )
        )
        if not payable_lines:
            raise UserError(_("No hay lineas pendientes por pagar al empleado."))

        return payable_lines.action_register_payment()
