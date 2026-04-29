from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    timbrado_ids = fields.One2many(
        "res.partner.timbrado",
        "partner_id",
        string="Timbrados",
    )
