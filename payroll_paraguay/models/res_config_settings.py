from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    py_default_vendor_product_id = fields.Many2one(
        related="company_id.py_default_vendor_product_id",
        readonly=False,
        string="Producto por defecto (factura proveedor nomina)",
    )
    py_default_vendor_journal_id = fields.Many2one(
        related="company_id.py_default_vendor_journal_id",
        readonly=False,
        string="Diario por defecto (factura proveedor nomina)",
    )
