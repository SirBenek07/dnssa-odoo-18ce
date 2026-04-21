from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    year_result_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de resultados del ejercicio",
        domain="[('is_year_result_account', '=', True), ('deprecated', '=', False)]",
        check_company=True,
    )
