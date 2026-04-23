# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.tools.float_utils import float_round


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sale_invoiced_qty = fields.Float(
        string="Facturado Venta",
        compute="_compute_sale_invoiced_qty",
        digits="Product Unit of Measure",
    )
    purchase_invoiced_qty = fields.Float(
        string="Facturado Compra",
        compute="_compute_purchase_invoiced_qty",
        digits="Product Unit of Measure",
    )

    @api.depends("product_variant_ids.sale_invoiced_qty")
    def _compute_sale_invoiced_qty(self):
        for template in self:
            template.sale_invoiced_qty = float_round(
                sum(template.with_context(active_test=False).product_variant_ids.mapped("sale_invoiced_qty")),
                precision_rounding=template.uom_id.rounding,
            )

    @api.depends("product_variant_ids.purchase_invoiced_qty")
    def _compute_purchase_invoiced_qty(self):
        for template in self:
            template.purchase_invoiced_qty = float_round(
                sum(template.with_context(active_test=False).product_variant_ids.mapped("purchase_invoiced_qty")),
                precision_rounding=template.uom_id.rounding,
            )

    def action_view_customer_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action["domain"] = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("invoice_line_ids.product_id", "in", self.with_context(active_test=False).product_variant_ids.ids),
        ]
        action["display_name"] = _("Facturas de cliente de %s", self.display_name)
        return action

    def action_view_vendor_bills(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        action["domain"] = [
            ("move_type", "in", ["in_invoice", "in_refund"]),
            ("state", "=", "posted"),
            ("invoice_line_ids.product_id", "in", self.with_context(active_test=False).product_variant_ids.ids),
        ]
        action["display_name"] = _("Facturas de proveedor de %s", self.display_name)
        return action


class ProductProduct(models.Model):
    _inherit = "product.product"

    sale_invoiced_qty = fields.Float(
        string="Facturado Venta",
        compute="_compute_sale_invoiced_qty",
        digits="Product Unit of Measure",
    )
    purchase_invoiced_qty = fields.Float(
        string="Facturado Compra",
        compute="_compute_purchase_invoiced_qty",
        digits="Product Unit of Measure",
    )

    def _get_recent_invoiced_qty(self, invoice_types, refund_types):
        if not self.ids:
            return {}

        date_from = fields.Date.context_today(self) - relativedelta(years=1)
        base_domain = [
            ("product_id", "in", self.ids),
            ("display_type", "=", "product"),
            ("move_id.state", "=", "posted"),
            ("move_id.invoice_date", ">=", date_from),
        ]
        move_line_model = self.env["account.move.line"]

        invoiced_data = {
            product.id: qty
            for product, qty in move_line_model._read_group(
                base_domain + [("move_id.move_type", "in", invoice_types)],
                ["product_id"],
                ["quantity:sum"],
            )
        }
        refund_data = {
            product.id: qty
            for product, qty in move_line_model._read_group(
                base_domain + [("move_id.move_type", "in", refund_types)],
                ["product_id"],
                ["quantity:sum"],
            )
        }
        return {
            product_id: (invoiced_data.get(product_id, 0.0) - refund_data.get(product_id, 0.0))
            for product_id in self.ids
        }

    def _compute_sale_invoiced_qty(self):
        qty_by_product = self._get_recent_invoiced_qty(["out_invoice"], ["out_refund"])
        for product in self:
            product.sale_invoiced_qty = float_round(
                qty_by_product.get(product.id, 0.0),
                precision_rounding=product.uom_id.rounding,
            ) if product.id else 0.0

    def _compute_purchase_invoiced_qty(self):
        qty_by_product = self._get_recent_invoiced_qty(["in_invoice"], ["in_refund"])
        for product in self:
            product.purchase_invoiced_qty = float_round(
                qty_by_product.get(product.id, 0.0),
                precision_rounding=product.uom_id.rounding,
            ) if product.id else 0.0

    def action_view_customer_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action["domain"] = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("invoice_line_ids.product_id", "in", self.ids),
        ]
        action["display_name"] = _("Facturas de cliente de %s", self.display_name)
        return action

    def action_view_vendor_bills(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        action["domain"] = [
            ("move_type", "in", ["in_invoice", "in_refund"]),
            ("state", "=", "posted"),
            ("invoice_line_ids.product_id", "in", self.ids),
        ]
        action["display_name"] = _("Facturas de proveedor de %s", self.display_name)
        return action
