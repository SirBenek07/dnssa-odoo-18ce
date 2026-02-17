from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountAccountResultRange(models.Model):
    _name = "account.account.result.range"
    _description = "Result Account Range"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    account_id = fields.Many2one(
        comodel_name="account.account",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sign = fields.Selection(
        selection=[("plus", "+ Sumar"), ("minus", "- Restar")],
        default="plus",
        required=True,
        string="Operaci\u00f3n",
    )
    code_from = fields.Char(required=True, string="C\u00f3digo desde")
    code_to = fields.Char(required=True, string="C\u00f3digo hasta")

    @api.constrains("code_from", "code_to")
    def _check_code_range(self):
        for record in self:
            if record.code_from and record.code_to and record.code_from > record.code_to:
                raise ValidationError(
                    _("El c\u00f3digo desde debe ser menor o igual al c\u00f3digo hasta.")
                )
