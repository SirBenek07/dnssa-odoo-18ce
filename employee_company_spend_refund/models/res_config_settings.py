from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    employee_spend_refund_account_id = fields.Many2one(
        related="company_id.employee_spend_refund_account_id",
        readonly=False,
    )
    company_spend_refund_default = fields.Boolean(
        related="company_id.company_spend_refund_default",
        readonly=False,
    )
