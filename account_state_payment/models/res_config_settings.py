from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_in_payment_state_until_bank_match = fields.Boolean(
        related="company_id.use_in_payment_state_until_bank_match",
        readonly=False,
        string="Estado 'En proceso de pago' hasta conciliacion bancaria",
    )
