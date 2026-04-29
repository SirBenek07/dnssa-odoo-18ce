from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartnerTimbrado(models.Model):
    _name = "res.partner.timbrado"
    _description = "Timbrado de contacto"
    _order = "is_default desc, id desc"
    _rec_name = "name"

    partner_id = fields.Many2one(
        "res.partner",
        string="Contacto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(string="Timbrado", required=True)
    is_electronic = fields.Boolean(string="Factura electronica")
    validez_timbrado = fields.Date(string="Validez de timbrado")
    is_default = fields.Boolean(string="Por defecto")

    def write(self, vals):
        vals = vals.copy()
        if vals.get("is_electronic"):
            vals["validez_timbrado"] = False
        res = super().write(vals)
        if (
            not self.env.context.get("skip_timbrado_default_sync")
            and (
                vals.get("is_default")
                or ("partner_id" in vals and any(self.mapped("is_default")))
            )
        ):
            self._keep_single_default_per_partner()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_electronic"):
                vals["validez_timbrado"] = False
        records = super().create(vals_list)
        records._keep_single_default_per_partner()
        return records

    @api.onchange("is_electronic")
    def _onchange_is_electronic(self):
        for timbrado in self:
            if timbrado.is_electronic:
                timbrado.validez_timbrado = False

    def _keep_single_default_per_partner(self):
        default_records = self.filtered("is_default")
        for partner in default_records.mapped("partner_id"):
            partner_defaults = default_records.filtered(
                lambda timbrado: timbrado.partner_id == partner
            ).sorted("id", reverse=True)
            keeper = partner_defaults[:1]
            if keeper:
                self.search(
                    [
                        ("partner_id", "=", partner.id),
                        ("is_default", "=", True),
                        ("id", "!=", keeper.id),
                    ]
                ).with_context(skip_timbrado_default_sync=True).write(
                    {"is_default": False}
                )

    @api.constrains("is_electronic", "validez_timbrado")
    def _check_validez_timbrado_required(self):
        for timbrado in self:
            if not timbrado.is_electronic and not timbrado.validez_timbrado:
                raise ValidationError(
                    _(
                        "La validez de timbrado es obligatoria para timbrados no electronicos."
                    )
                )
