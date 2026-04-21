from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    year_result_account_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.year_result_account_id",
        readonly=False,
        string="Cuenta de resultados del ejercicio",
        domain="[('is_year_result_account', '=', True), ('deprecated', '=', False), ('company_ids', 'in', [company_id])]",
    )
