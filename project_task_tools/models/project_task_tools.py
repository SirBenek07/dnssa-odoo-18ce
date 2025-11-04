# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTaskToolLine(models.Model):
    _name = "project.task.tool.line"
    _description = "Línea de herramienta asignada a tarea"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True, domain=[("type", "in", ("product","consu"))])
    qty = fields.Float(default=1.0)
    uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True)
    lot_id = fields.Many2one("stock.lot", domain="[('product_id','=',product_id)]")
    state = fields.Selection([("draft","Borrador"),("out","Entregado"),("returned","Devuelto")], default="draft")
    picking_out_id = fields.Many2one("stock.picking", readonly=True)
    picking_in_id = fields.Many2one("stock.picking", readonly=True)
    location_src_id = fields.Many2one("stock.location", string="Desde", help="Ubicación origen (Herramientas/Depósito)")
    location_dst_id = fields.Many2one("stock.location", string="Hacia", help="Ubicación destino (p.ej. WH/Proyecto/Tarea)")

    @api.constrains("qty")
    def _check_qty(self):
        for r in self:
            if r.qty <= 0:
                raise UserError(_("La cantidad debe ser positiva."))

    def _ensure_locations(self):
        for r in self:
            if not (r.location_src_id and r.location_dst_id):
                raise UserError(_("Definí ubicaciones origen/destino para la herramienta."))

    def action_entregar(self):
        for r in self:
            r._ensure_locations()
            if r.state != "draft":
                raise UserError(_("Solo líneas en borrador."))
            picking = r._make_internal_picking(r.location_src_id, r.location_dst_id, _("Herramientas a Tarea"))
            r.picking_out_id = picking.id
            r.state = "out"

    def action_devolver(self):
        for r in self:
            r._ensure_locations()
            if r.state != "out":
                raise UserError(_("Solo líneas entregadas."))
            picking = r._make_internal_picking(r.location_dst_id, r.location_src_id, _("Devolución de Herramientas"))
            r.picking_in_id = picking.id
            r.state = "returned"

    def _make_internal_picking(self, loc_from, loc_to, name):
        self.ensure_one()
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        picking = Picking.create({
            "picking_type_id": self._get_internal_type(),
            "origin": f"Tarea {self.task_id.display_name}",
            "location_id": loc_from.id,
            "location_dest_id": loc_to.id,
            "note": name,
        })
        move_vals = {
            "name": self.product_id.display_name,
            "product_id": self.product_id.id,
            "product_uom": self.uom_id.id,
            "product_uom_qty": self.qty,
            "picking_id": picking.id,
            "location_id": loc_from.id,
            "location_dest_id": loc_to.id,
        }
        move = Move.create(move_vals)
        move._action_confirm()
        move._action_assign()
        # Si se usa lote/serie
        if self.lot_id and move.move_line_ids:
            for ml in move.move_line_ids:
                ml.lot_id = self.lot_id
                ml.qty_done = self.qty
        else:
            for ml in move.move_line_ids:
                ml.qty_done = ml.product_uom_qty
        picking.action_set_quantities_to_reservation()
        picking.button_validate()
        return picking

    def _get_internal_type(self):
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id.company_id", "=", self.task_id.company_id.id)
        ], limit=1)
        if not picking_type:
            raise UserError(_("No se encontró un tipo de operación interna."))
        return picking_type.id


class ProjectTask(models.Model):
    _inherit = "project.task"
    tool_line_ids = fields.One2many("project.task.tool.line", "task_id", string="Herramientas")
