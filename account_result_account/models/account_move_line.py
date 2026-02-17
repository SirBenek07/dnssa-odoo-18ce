from odoo import _, api, models
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.constrains("account_id")
    def _check_account_is_not_result_account(self):
        for line in self:
            if line.account_id and line.account_id.is_result_account:
                raise ValidationError(
                    _(
                        "No se puede cargar movimientos en la cuenta de resultado "
                        "'%(code)s - %(name)s'."
                    )
                    % {
                        "code": line.account_id.code or "",
                        "name": line.account_id.name or "",
                    }
                )
