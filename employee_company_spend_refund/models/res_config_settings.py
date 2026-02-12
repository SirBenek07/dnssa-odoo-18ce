from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    employee_spend_refund_account_id = fields.Many2one(
        related="company_id.employee_spend_refund_account_id",
        readonly=False,
    )
