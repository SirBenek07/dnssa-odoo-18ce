from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = "account.account"

    is_result_account = fields.Boolean(string="Es cuenta de resultado")
    result_range_ids = fields.One2many(
        comodel_name="account.account.result.range",
        inverse_name="account_id",
        string="Rangos de cuentas",
    )

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
