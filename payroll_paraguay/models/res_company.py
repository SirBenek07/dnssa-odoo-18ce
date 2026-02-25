from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    py_default_vendor_product_id = fields.Many2one(
        "product.product",
        string="Producto por defecto (factura proveedor nomina)",
        domain=[("type", "=", "service")],
        help="Producto usado por defecto para generar facturas de proveedor "
        "desde nomina en esquema 'Factura de Proveedor'.",
    )
    py_default_vendor_journal_id = fields.Many2one(
        "account.journal",
        string="Diario por defecto (factura proveedor nomina)",
        domain=[("type", "=", "purchase")],
        help="Diario usado por defecto para facturas de proveedor creadas "
        "desde nomina.",
    )
