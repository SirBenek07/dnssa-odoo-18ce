# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTaskToolLine(models.Model):
    _name = "project.task.tool.line"
    _description = "Línea de herramienta asignada a tarea"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="task_id.company_id", store=True, readonly=True)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain=[("type", "in", ("product", "consu")), ("is_tool", "=", True)],
    )
    qty = fields.Float(default=1.0, string="Unidades")
    uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True, string="U. medida")
    date_from = fields.Date(string="Desde", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Hasta", required=True, default=fields.Date.context_today)
    state = fields.Selection([("draft","Borrador"),("out","Entregado"),("returned","Devuelto")], default="draft")
    picking_out_id = fields.Many2one("stock.picking", readonly=True, string="Transferencia entrega")
    picking_in_id = fields.Many2one("stock.picking", readonly=True, string="Transferencia devolución")
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Tipo de operación",
        domain="[('code', '=', 'internal'), ('company_id', '=', company_id)]",
    )
    location_src_id = fields.Many2one("stock.location", string="Desde", help="Ubicación origen (Herramientas/Depósito)")
    location_dst_id = fields.Many2one("stock.location", string="Hacia", help="Ubicación destino (p.ej. WH/Proyecto/Tarea)")
    task_use_task_tools = fields.Boolean(related="task_id.use_task_tools", store=False)
    task_done_task_tools = fields.Boolean(related="task_id.done_task_tools", store=False)

    @api.constrains("qty")
    def _check_qty(self):
        for r in self:
            if r.qty <= 0:
                raise UserError(_("La cantidad debe ser positiva."))

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_from > line.date_to:
                raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))

    @api.constrains("product_id", "date_from", "date_to", "state")
    def _check_tool_availability(self):
        for line in self:
            if not (line.product_id and line.date_from and line.date_to):
                continue
            domain = [
                ("id", "!=", line.id),
                ("product_id", "=", line.product_id.id),
                ("state", "in", ["draft", "out"]),
                ("date_from", "<=", line.date_to),
                ("date_to", ">=", line.date_from),
            ]
            conflict = self.search(domain, limit=1)
            if conflict:
                raise UserError(
                    _(
                        "La herramienta %(tool)s ya está reservada del %(start)s al %(end)s (tarea %(task)s).",
                        tool=conflict.product_id.display_name,
                        start=fields.Date.to_string(conflict.date_from),
                        end=fields.Date.to_string(conflict.date_to),
                        task=conflict.task_id.display_name,
                    )
                )

    def _ensure_locations(self):
        for r in self:
            r._assign_locations_from_type()
            if not (r.location_src_id and r.location_dst_id):
                raise UserError(_("Definí ubicaciones origen/destino para la herramienta."))

    def _ensure_stage_allows_edit(self):
        locked = self.filtered(lambda line: line.task_id.stage_id.done_task_tools)
        if locked:
            raise UserError(_("No podés modificar herramientas en esta etapa del proyecto."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._set_locations_in_vals(vals)
        records = super().create(vals_list)
        records._ensure_stage_allows_edit()
        records._assign_locations_from_type(force=True)
        return records

    def write(self, vals):
        if not self.env.context.get("tool_line_skip_stage_check"):
            self._ensure_stage_allows_edit()
        res = super().write(vals)
        force_locations = "picking_type_id" in vals
        if force_locations:
            self._assign_locations_from_type(force=True)
        else:
            missing = self.filtered(lambda l: not (l.location_src_id and l.location_dst_id))
            if missing:
                missing._assign_locations_from_type()
        return res

    def unlink(self):
        self._ensure_stage_allows_edit()
        return super().unlink()

    def action_entregar(self):
        for r in self:
            r._ensure_stage_allows_edit()
            r._assign_locations_from_type()
            r._ensure_locations()
            if r.state != "draft":
                raise UserError(_("Solo líneas en borrador."))
            picking = r._make_internal_picking(r.location_src_id, r.location_dst_id, _("Herramientas a Tarea"))
            r.picking_out_id = picking.id
            r.state = "out"

    def action_devolver(self):
        for r in self:
            r._ensure_stage_allows_edit()
            r._assign_locations_from_type()
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
        picking_type_id = self.picking_type_id.id or self._get_internal_type()
        picking = Picking.create({
            "picking_type_id": picking_type_id,
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
        for ml in move.move_line_ids:
            qty = ml.quantity or ml.quantity_product_uom or ml.move_id.product_uom_qty or self.qty
            ml.quantity = qty
            ml.quantity_product_uom = qty
        picking.button_validate()
        return picking

    def _get_internal_type(self):
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("company_id", "=", self.task_id.company_id.id)
        ], limit=1)
        if not picking_type:
            raise UserError(_("No se encontró un tipo de operación interna."))
        return picking_type.id

    @api.onchange("picking_type_id")
    def _onchange_picking_type_id(self):
        self._assign_locations_from_type(force=True)

    def _assign_locations_from_type(self, force=False):
        for line in self:
            picking_type = line.picking_type_id
            if not picking_type:
                continue
            updates = {}
            if picking_type.default_location_src_id and (force or not line.location_src_id):
                updates["location_src_id"] = picking_type.default_location_src_id.id
            if picking_type.default_location_dest_id and (force or not line.location_dst_id):
                updates["location_dst_id"] = picking_type.default_location_dest_id.id
            if updates:
                if line.id:
                    line.with_context(tool_line_skip_stage_check=True).write(updates)
                else:
                    for field_name, value in updates.items():
                        line[field_name] = value

    def _set_locations_in_vals(self, vals):
        if vals.get("location_src_id") and vals.get("location_dst_id"):
            return
        picking_type = vals.get("picking_type_id") and self.env["stock.picking.type"].browse(vals["picking_type_id"])
        if not picking_type:
            return
        if picking_type.default_location_src_id and not vals.get("location_src_id"):
            vals["location_src_id"] = picking_type.default_location_src_id.id
        if picking_type.default_location_dest_id and not vals.get("location_dst_id"):
            vals["location_dst_id"] = picking_type.default_location_dest_id.id


class ProjectTask(models.Model):
    _inherit = "project.task"

    tool_line_ids = fields.One2many("project.task.tool.line", "task_id", string="Herramientas")
    use_task_tools = fields.Boolean(related="stage_id.use_task_tools", store=True)
    done_task_tools = fields.Boolean(related="stage_id.done_task_tools", store=True)


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    use_task_tools = fields.Boolean(
        string="Usar herramientas",
        help="Si está marcado, las tareas en esta etapa muestran la pestaña de herramientas."
    )
    done_task_tools = fields.Boolean(
        string="Herramientas cerradas",
        help="Si está marcado, las herramientas quedan solo de lectura en esta etapa."
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_tool = fields.Boolean(
        string="Es herramienta?",
        help="Activa esta casilla para indicar que el producto puede asignarse como herramienta a tareas.",
    )
