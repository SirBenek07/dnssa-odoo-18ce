from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    timbrado = fields.Char(string="Timbrado")
    validez_timbrado = fields.Date(string="Validez de timbrado")

    @api.constrains("timbrado", "move_type", "state")
    def _check_timbrado_required_for_vendor_bill(self):
        for move in self:
            if (
                move.move_type == "in_invoice"
                and move.state == "posted"
                and not move.timbrado
            ):
                raise ValidationError(_("El timbrado es obligatorio en facturas de proveedor."))

    @api.constrains("validez_timbrado", "invoice_date", "move_type")
    def _check_validez_timbrado_after_invoice_date(self):
        """Keep timbrado validity aligned with the invoice date on vendor bills."""
        for move in self:
            if (
                move.move_type == "in_invoice"
                and move.validez_timbrado
                and move.invoice_date
                and move.validez_timbrado < move.invoice_date
            ):
                raise ValidationError(
                    _("La validez de timbrado no puede ser anterior a la fecha de la factura.")
                )
