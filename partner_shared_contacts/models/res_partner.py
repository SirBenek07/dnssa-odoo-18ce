from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    shared_contact_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="res_partner_shared_contact_rel",
        column1="owner_id",
        column2="contact_id",
        string="Contactos y direcciones",
        help="Contactos vinculados sin crear duplicados.",
    )
    shared_owner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="res_partner_shared_contact_rel",
        column1="contact_id",
        column2="owner_id",
        string="Vinculado a",
        help="Partners a los que este contacto esta vinculado.",
    )

    @api.constrains("shared_contact_ids")
    def _check_shared_contact_ids(self):
        for partner in self:
            if partner in partner.shared_contact_ids:
                raise ValidationError("No se puede vincular un contacto consigo mismo.")

