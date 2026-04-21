from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.sql import column_exists, create_column


class AccountAccount(models.Model):
    _inherit = "account.account"

    is_result_account = fields.Boolean(string="Es cuenta de resultado")
    is_renta_account = fields.Boolean(string="Es cuenta de Renta")
    is_year_result_account = fields.Boolean(
        string="Es la cuenta de resultados del ejercicio"
    )
    result_range_ids = fields.One2many(
        comodel_name="account.account.result.range",
        inverse_name="account_id",
        string="Rangos de cuentas",
    )

    def _auto_init(self):
        """Defensive schema sync to avoid runtime crashes after deploys."""
        cr = self.env.cr
        if not column_exists(cr, "account_account", "is_result_account"):
            create_column(cr, "account_account", "is_result_account", "boolean")
        if not column_exists(cr, "account_account", "is_renta_account"):
            create_column(cr, "account_account", "is_renta_account", "boolean")
        if not column_exists(cr, "account_account", "is_year_result_account"):
            create_column(cr, "account_account", "is_year_result_account", "boolean")
        return super()._auto_init()

    @api.onchange("is_year_result_account")
    def _onchange_is_year_result_account(self):
        if self.is_year_result_account:
            self.is_result_account = False
            self.is_renta_account = False
            self.result_range_ids = [(5, 0, 0)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_year_result_account"):
                vals["is_result_account"] = False
                vals["is_renta_account"] = False
                vals["result_range_ids"] = [(5, 0, 0)]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("is_year_result_account"):
            vals = dict(vals)
            vals["is_result_account"] = False
            vals["is_renta_account"] = False
            vals["result_range_ids"] = [(5, 0, 0)]
        return super().write(vals)

    @api.constrains("is_result_account")
    def _check_result_account_without_moves(self):
        move_line_model = self.env["account.move.line"]
        for account in self.filtered("is_result_account"):
            has_moves = bool(move_line_model.search([("account_id", "=", account.id)], limit=1))
            if has_moves:
                raise ValidationError(
                    _(
                        "No se puede marcar la cuenta '%(code)s - %(name)s' como "
                        "cuenta de resultado porque ya tiene movimientos."
                    )
                    % {"code": account.code or "", "name": account.name or ""}
                )

    @api.constrains("is_year_result_account", "company_ids")
    def _check_unique_year_result_account(self):
        for account in self.filtered("is_year_result_account"):
            companies = account.company_ids
            if not companies:
                continue
            duplicate = self.search(
                [
                    ("id", "!=", account.id),
                    ("is_year_result_account", "=", True),
                    ("company_ids", "in", companies.ids),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "Solo puede existir una cuenta marcada como "
                        "'Resultados del ejercicio' por compania."
                    )
                )
