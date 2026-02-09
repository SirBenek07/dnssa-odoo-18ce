# -*- coding: utf-8 -*-
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTaskToolLine(models.Model):
    _name = "project.task.tool.line"
    _description = "Linea de recurso asignada a tarea"
    _rec_name = "resource_name"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="task_id.company_id", store=True, readonly=True)
    resource_type = fields.Selection(
        [("tool", "Herramienta"), ("vehicle", "Vehiculo")],
        string="Tipo de recurso",
        required=True,
        default="tool",
    )
    product_id = fields.Many2one(
        "product.product",
        domain=[("type", "in", ("product", "consu")), ("is_tool", "=", True)],
        string="Herramienta",
    )
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehiculo",
    )
    resource_name = fields.Char(string="Recurso", compute="_compute_resource_name", store=True)
    qty = fields.Float(default=1.0, string="Unidades")
    uom_id = fields.Many2one(related="product_id.uom_id", store=True, readonly=True, string="U. medida")
    date_from = fields.Date(string="Desde", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Hasta", required=True, default=fields.Date.context_today)
    state = fields.Selection(
        [("draft", "Borrador"), ("out", "Entregado"), ("returned", "Devuelto")],
        default="draft",
    )
    picking_out_id = fields.Many2one("stock.picking", readonly=True, string="Transferencia entrega")
    picking_in_id = fields.Many2one("stock.picking", readonly=True, string="Transferencia devolucion")
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Tipo de operacion",
        domain="[('code', '=', 'internal'), ('company_id', '=', company_id)]",
    )
    location_src_id = fields.Many2one(
        "stock.location", string="Desde", help="Ubicacion origen (Herramientas/Deposito)"
    )
    location_dst_id = fields.Many2one(
        "stock.location", string="Hacia", help="Ubicacion destino (p.ej. WH/Proyecto/Tarea)"
    )
    task_use_task_tools = fields.Boolean(related="task_id.use_task_tools", store=False)
    task_done_task_tools = fields.Boolean(related="task_id.done_task_tools", store=False)
    is_currently_in_use = fields.Boolean(string="En uso", compute="_compute_usage_flags")
    calendar_date_start = fields.Datetime(string="Inicio calendario", compute="_compute_calendar_dates")
    calendar_date_stop = fields.Datetime(string="Fin calendario", compute="_compute_calendar_dates")

    @api.depends("resource_type", "product_id", "vehicle_id")
    def _compute_resource_name(self):
        for line in self:
            if line.resource_type == "vehicle":
                line.resource_name = line.vehicle_id.display_name or _("Vehiculo sin seleccionar")
            else:
                line.resource_name = line.product_id.display_name or _("Herramienta sin seleccionar")

    @api.depends("date_from", "date_to", "state")
    def _compute_usage_flags(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.is_currently_in_use = bool(
                line.state in ("draft", "out")
                and line.date_from
                and line.date_to
                and line.date_from <= today <= line.date_to
            )

    @api.depends("date_from", "date_to")
    def _compute_calendar_dates(self):
        for line in self:
            line.calendar_date_start = datetime.combine(line.date_from, time.min) if line.date_from else False
            line.calendar_date_stop = datetime.combine(line.date_to, time.max) if line.date_to else False

    @api.constrains("resource_type", "product_id", "vehicle_id", "qty")
    def _check_resource_fields(self):
        for line in self:
            if line.resource_type == "tool":
                if not line.product_id:
                    raise UserError(_("Debes seleccionar una herramienta."))
                if line.vehicle_id:
                    raise UserError(_("No podes asignar vehiculo en una linea de herramienta."))
                if line.qty <= 0:
                    raise UserError(_("La cantidad debe ser positiva."))
            elif line.resource_type == "vehicle":
                if not line.vehicle_id:
                    raise UserError(_("Debes seleccionar un vehiculo."))
                if line.product_id:
                    raise UserError(_("No podes asignar herramienta en una linea de vehiculo."))
                if line.qty != 1:
                    raise UserError(_("Los vehiculos se reservan de a una unidad."))

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_from > line.date_to:
                raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))

    @api.constrains("resource_type", "product_id", "vehicle_id", "date_from", "date_to", "state")
    def _check_resource_availability(self):
        for line in self:
            if not (line.date_from and line.date_to):
                continue
            if line.resource_type == "tool" and not line.product_id:
                continue
            if line.resource_type == "vehicle" and not line.vehicle_id:
                continue
            domain = [
                ("id", "!=", line.id),
                ("state", "in", ["draft", "out"]),
                ("date_from", "<=", line.date_to),
                ("date_to", ">=", line.date_from),
            ]
            if line.resource_type == "vehicle":
                domain.extend(
                    [
                        ("resource_type", "=", "vehicle"),
                        ("vehicle_id", "=", line.vehicle_id.id),
                    ]
                )
            else:
                domain.extend(
                    [
                        ("resource_type", "=", "tool"),
                        ("product_id", "=", line.product_id.id),
                    ]
                )
            conflict = self.search(domain, limit=1)
            if conflict:
                raise UserError(
                    _(
                        "El recurso %(resource)s ya esta reservado del %(start)s al %(end)s (tarea %(task)s).",
                        resource=conflict.resource_name,
                        start=fields.Date.to_string(conflict.date_from),
                        end=fields.Date.to_string(conflict.date_to),
                        task=conflict.task_id.display_name,
                    )
                )

    def _ensure_locations(self):
        for line in self:
            if line.resource_type != "tool":
                continue
            line._assign_locations_from_type()
            if not (line.location_src_id and line.location_dst_id):
                raise UserError(_("Defini ubicaciones origen/destino para la herramienta."))

    def _ensure_stage_allows_edit(self):
        locked = self.filtered(lambda line: line.task_id.stage_id.done_task_tools)
        if locked:
            raise UserError(_("No podes modificar recursos en esta etapa del proyecto."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("resource_type") == "vehicle":
                vals["qty"] = 1.0
                vals.pop("product_id", None)
            elif vals.get("resource_type") == "tool":
                vals.pop("vehicle_id", None)
            self._set_locations_in_vals(vals)
        records = super().create(vals_list)
        records._ensure_stage_allows_edit()
        records._assign_locations_from_type(force=True)
        return records

    def write(self, vals):
        if not self.env.context.get("tool_line_skip_stage_check"):
            self._ensure_stage_allows_edit()

        write_vals = dict(vals)
        if write_vals.get("resource_type") == "vehicle":
            write_vals["qty"] = 1.0
            write_vals["product_id"] = False
            write_vals["picking_type_id"] = False
            write_vals["location_src_id"] = False
            write_vals["location_dst_id"] = False
        elif write_vals.get("resource_type") == "tool":
            write_vals["vehicle_id"] = False

        if "vehicle_id" in write_vals and write_vals.get("vehicle_id"):
            write_vals["qty"] = 1.0
            write_vals["product_id"] = False
            write_vals.setdefault("resource_type", "vehicle")
            write_vals["picking_type_id"] = False
            write_vals["location_src_id"] = False
            write_vals["location_dst_id"] = False

        if "product_id" in write_vals and write_vals.get("product_id"):
            write_vals["vehicle_id"] = False
            write_vals.setdefault("resource_type", "tool")

        res = super().write(write_vals)
        force_locations = "picking_type_id" in write_vals
        if force_locations:
            self._assign_locations_from_type(force=True)
        else:
            missing = self.filtered(
                lambda line: line.resource_type == "tool" and not (line.location_src_id and line.location_dst_id)
            )
            if missing:
                missing._assign_locations_from_type()
        return res

    def unlink(self):
        self._ensure_stage_allows_edit()
        return super().unlink()

    def action_entregar(self):
        for line in self:
            line._ensure_stage_allows_edit()
            if line.state != "draft":
                raise UserError(_("Solo lineas en borrador."))
            if line.resource_type == "tool":
                line._assign_locations_from_type()
                line._ensure_locations()
                picking = line._make_internal_picking(
                    line.location_src_id,
                    line.location_dst_id,
                    _("Herramientas a Tarea"),
                )
                line.picking_out_id = picking.id
            line.state = "out"

    def action_devolver(self):
        for line in self:
            line._ensure_stage_allows_edit()
            if line.state != "out":
                raise UserError(_("Solo lineas entregadas."))
            if line.resource_type == "tool":
                line._assign_locations_from_type()
                line._ensure_locations()
                picking = line._make_internal_picking(
                    line.location_dst_id,
                    line.location_src_id,
                    _("Devolucion de Herramientas"),
                )
                line.picking_in_id = picking.id
            line.state = "returned"

    def _make_internal_picking(self, loc_from, loc_to, name):
        self.ensure_one()
        if self.resource_type != "tool":
            raise UserError(_("Solo las herramientas generan transferencias internas."))

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_id.id or self._get_internal_type(),
                "origin": f"Tarea {self.task_id.display_name}",
                "location_id": loc_from.id,
                "location_dest_id": loc_to.id,
                "note": name,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": self.product_id.display_name,
                "product_id": self.product_id.id,
                "product_uom": self.uom_id.id,
                "product_uom_qty": self.qty,
                "picking_id": picking.id,
                "location_id": loc_from.id,
                "location_dest_id": loc_to.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        for move_line in move.move_line_ids:
            qty = move_line.quantity or move_line.quantity_product_uom or move_line.move_id.product_uom_qty or self.qty
            move_line.quantity = qty
            move_line.quantity_product_uom = qty
        picking.button_validate()
        return picking

    def _get_internal_type(self):
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("company_id", "=", self.task_id.company_id.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(_("No se encontro un tipo de operacion interna."))
        return picking_type.id

    @api.onchange("picking_type_id")
    def _onchange_picking_type_id(self):
        self._assign_locations_from_type(force=True)

    def _assign_locations_from_type(self, force=False):
        for line in self:
            if line.resource_type != "tool":
                continue
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
        if vals.get("resource_type") == "vehicle":
            vals["location_src_id"] = False
            vals["location_dst_id"] = False
            vals["picking_type_id"] = False
            return

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
        help="Si esta marcado, las tareas en esta etapa muestran la pestana de herramientas.",
    )
    done_task_tools = fields.Boolean(
        string="Herramientas cerradas",
        help="Si esta marcado, los recursos quedan solo de lectura en esta etapa.",
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_tool = fields.Boolean(
        string="Es herramienta?",
        help="Activa esta casilla para indicar que el producto puede asignarse como herramienta en tareas.",
    )
