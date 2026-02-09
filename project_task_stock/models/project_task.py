# Copyright 2022-2025 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import format_date, format_datetime


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "analytic.mixin", "ir.attachment.action_download"]

    scrap_ids = fields.One2many(
        comodel_name="stock.scrap", inverse_name="task_id", string="Scraps"
    )
    scrap_count = fields.Integer(
        compute="_compute_scrap_move_count", string="Scrap Move"
    )
    move_ids = fields.One2many(
        comodel_name="stock.move",
        inverse_name="raw_material_task_id",
        string="Stock Moves",
        copy=False,
        domain=[("scrapped", "=", False)],
    )
    use_stock_moves = fields.Boolean(related="stage_id.use_stock_moves")
    done_stock_moves = fields.Boolean(related="stage_id.done_stock_moves")
    stock_moves_is_locked = fields.Boolean(default=True)
    allow_moves_action_confirm = fields.Boolean(
        compute="_compute_allow_moves_action_confirm"
    )
    allow_moves_action_assign = fields.Boolean(
        compute="_compute_allow_moves_action_assign"
    )
    stock_state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("assigned", "Assigned"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        compute="_compute_stock_state",
    )
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Operation Type",
        readonly=False,
        domain="[('company_id', '=?', company_id)]",
        index=True,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Source Location",
        readonly=False,
        index=True,
        check_company=True,
    )
    location_dest_id = fields.Many2one(
        comodel_name="stock.location",
        string="Destination Location",
        readonly=False,
        index=True,
        check_company=True,
    )
    stock_analytic_date = fields.Date()
    unreserve_visible = fields.Boolean(
        string="Allowed to Unreserve Inventory",
        compute="_compute_unreserve_visible",
        help="Technical field to check when we can unreserve",
    )
    stock_analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Move Analytic Account",
        help="Move created will be assigned to this analytic account",
    )
    stock_analytic_distribution = fields.Json(
        copy=True,
        readonly=False,
    )
    stock_analytic_line_ids = fields.One2many(
        comodel_name="account.analytic.line",
        inverse_name="stock_task_id",
        string="Stock Analytic Lines",
    )
    group_id = fields.Many2one(
        comodel_name="procurement.group",
    )

    def _get_downloadable_attachments(self):
        tasks = self.env["project.task"].search([("id", "child_of", self.ids)])
        return self.env["ir.attachment"].search(
            [
                ("res_model", "=", "project.task"),
                ("res_id", "in", tasks.ids),
            ]
        )

    def _get_zip_download_name(self):
        if not self:
            return False
        root_task = self[0]
        while root_task.parent_id:
            root_task = root_task.parent_id
        if len(self) > 1:
            return f"{root_task.name}_y_mas.zip"
        return f"{root_task.name}.zip"

    def _get_zip_download_options(self):
        return {
            "selected_task_ids": self.ids,
            "group_by_selected_task": True,
        }

    def _compute_scrap_move_count(self):
        data = self.env["stock.scrap"].read_group(
            [("task_id", "in", self.ids)], ["task_id"], ["task_id"]
        )
        count_data = {item["task_id"][0]: item["task_id_count"] for item in data}
        for item in self:
            item.scrap_count = count_data.get(item.id, 0)

    @api.depends("move_ids", "move_ids.state")
    def _compute_allow_moves_action_confirm(self):
        for item in self:
            item.allow_moves_action_confirm = any(
                move.state == "draft" for move in item.move_ids
            )

    @api.depends("move_ids", "move_ids.state")
    def _compute_allow_moves_action_assign(self):
        for item in self:
            item.allow_moves_action_assign = any(
                move.state in ("confirmed", "partially_available")
                for move in item.move_ids
            )

    @api.depends("move_ids", "move_ids.state")
    def _compute_stock_state(self):
        for task in self:
            task.stock_state = "pending"
            if task.move_ids:
                states = task.mapped("move_ids.state")
                for state in ("confirmed", "assigned", "done", "cancel"):
                    if state in states:
                        task.stock_state = state
                        break

    @api.depends("move_ids", "move_ids.quantity")
    def _compute_unreserve_visible(self):
        for item in self:
            already_reserved = item.mapped("move_ids.move_line_ids")
            any_quantity_done = any(
                [
                    m.quantity > 0
                    for m in item.move_ids.filtered(lambda x: x.state == "done")
                ]
            )
            item.unreserve_visible = not any_quantity_done and already_reserved

    @api.onchange("picking_type_id")
    def _onchange_picking_type_id(self):
        self.location_id = self.picking_type_id.default_location_src_id.id
        self.location_dest_id = self.picking_type_id.default_location_dest_id.id

    def _check_tasks_with_pending_moves(self):
        if self.move_ids and "assigned" in self.mapped("move_ids.state"):
            raise UserError(
                _("It is not possible to change this with reserved movements in tasks.")
            )

    def _update_moves_info(self):
        for item in self:
            item._check_tasks_with_pending_moves()
            picking_type = item.picking_type_id or item.project_id.picking_type_id
            location = item.location_id or item.project_id.location_id
            location_dest = item.location_dest_id or item.project_id.location_dest_id
            moves = item.move_ids.filtered(
                lambda x, location=location, location_dest=location_dest: x.state
                not in ("cancel", "done")
                and (x.location_id != location or x.location_dest_id != location_dest)
            )
            moves.update(
                {
                    "warehouse_id": location.warehouse_id.id,
                    "location_id": location.id,
                    "location_dest_id": location_dest.id,
                    "picking_type_id": picking_type.id,
                }
            )
        self.action_assign()

    @api.model
    def _prepare_procurement_group_vals(self):
        return {"name": f"Task-ID: {self.id}"}

    def _get_task_start_date_label(self, task):
        date_candidates = (
            "date_start",
            "planned_date_begin",
            "planned_date_start",
            "date_begin",
            "date_deadline",
        )
        for field_name in date_candidates:
            if field_name not in task._fields or not task[field_name]:
                continue
            field = task._fields[field_name]
            if field.type == "datetime":
                return format_datetime(self.env, task[field_name])
            if field.type == "date":
                return format_date(self.env, task[field_name])
            return str(task[field_name])
        return _("Sin fecha de inicio")

    def _get_competing_task_requests(self, product, location, current_task):
        move_model = self.env["stock.move"]
        move_domain = [
            ("product_id", "=", product.id),
            ("scrapped", "=", False),
            ("state", "in", ("waiting", "confirmed", "partially_available", "assigned")),
            ("location_id", "child_of", location.id),
        ]
        by_task = {}
        for move in move_model.search(move_domain):
            task = move.raw_material_task_id or move.task_id
            if not task or task == current_task:
                continue
            requested_qty = move.product_uom._compute_quantity(
                move.product_uom_qty, product.uom_id
            )
            reserved_qty = move.product_uom._compute_quantity(
                move.quantity, product.uom_id
            )
            if task.id not in by_task:
                by_task[task.id] = {
                    "task": task,
                    "requested": 0.0,
                    "reserved": 0.0,
                }
            by_task[task.id]["requested"] += requested_qty
            by_task[task.id]["reserved"] += reserved_qty
        return sorted(
            by_task.values(),
            key=lambda x: (x["task"].display_name or "").lower(),
        )

    def _check_stock_shortage_before_assign(self):
        quant_model = self.env["stock.quant"]
        for task in self:
            pending_qty_by_product_location = {}
            moves = task.move_ids.filtered(
                lambda x: x.state not in ("done", "cancel") and x.product_id and x.location_id
            )
            for move in moves:
                pending_qty = max(move.product_uom_qty - move.quantity, 0.0)
                pending_qty = move.product_uom._compute_quantity(
                    pending_qty, move.product_id.uom_id
                )
                if float_is_zero(
                    pending_qty, precision_rounding=move.product_id.uom_id.rounding
                ):
                    continue
                key = (move.product_id.id, move.location_id.id)
                pending_qty_by_product_location[key] = (
                    pending_qty_by_product_location.get(key, 0.0) + pending_qty
                )

            shortage_messages = []
            for (product_id, location_id), pending_qty in pending_qty_by_product_location.items():
                product = self.env["product.product"].browse(product_id)
                location = self.env["stock.location"].browse(location_id)
                free_qty = quant_model._get_available_quantity(
                    product, location, strict=False
                )
                if (
                    float_compare(
                        pending_qty,
                        free_qty,
                        precision_rounding=product.uom_id.rounding,
                    )
                    <= 0
                ):
                    continue

                missing_qty = pending_qty - free_qty
                details = self._get_competing_task_requests(product, location, task)
                detail_lines = []
                for detail in details:
                    detail_lines.append(
                        _(
                            "- %(task)s | Inicio: %(start)s | Solicitado: %(requested).2f %(uom)s | Reservado: %(reserved).2f %(uom)s"
                        )
                        % {
                            "task": detail["task"].display_name,
                            "start": self._get_task_start_date_label(detail["task"]),
                            "requested": detail["requested"],
                            "reserved": detail["reserved"],
                            "uom": product.uom_id.display_name,
                        }
                    )
                if not detail_lines:
                    detail_lines = [_("- No hay otras tareas/eventos con demanda activa.")]

                shortage_messages.append(
                    _(
                        "No hay suficientes insumos para cubrir la necesidad actual.\n"
                        "Tarea: %(task)s\n"
                        "Producto: %(product)s\n"
                        "Ubicacion origen: %(location)s\n"
                        "Necesidad pendiente: %(pending).2f %(uom)s\n"
                        "Stock libre actual: %(free).2f %(uom)s\n"
                        "Faltante: %(missing).2f %(uom)s\n"
                        "Solicitudes en otras tareas/eventos:\n%(details)s"
                    )
                    % {
                        "task": task.display_name,
                        "product": product.display_name,
                        "location": location.display_name,
                        "pending": pending_qty,
                        "free": free_qty,
                        "missing": missing_qty,
                        "uom": product.uom_id.display_name,
                        "details": "\n".join(detail_lines),
                    }
                )

            if shortage_messages:
                raise UserError("\n\n".join(shortage_messages))

    def action_confirm(self):
        self.mapped("move_ids")._action_confirm()

    def action_assign(self):
        self.action_confirm()
        self._check_stock_shortage_before_assign()
        self.mapped("move_ids")._action_assign()

    def button_scrap(self):
        self.ensure_one()
        move_items = self.move_ids.filtered(lambda x: x.state not in ("done", "cancel"))
        return {
            "name": _("Scrap"),
            "view_mode": "form",
            "res_model": "stock.scrap",
            "view_id": self.env.ref("stock.stock_scrap_form_view2").id,
            "type": "ir.actions.act_window",
            "context": {
                "default_task_id": self.id,
                "product_ids": move_items.mapped("product_id").ids,
                "default_company_id": self.company_id.id,
            },
            "target": "new",
        }

    def do_unreserve(self):
        for item in self:
            item.move_ids.filtered(
                lambda x: x.state not in ("done", "cancel")
            )._do_unreserve()
        return True

    def button_unreserve(self):
        self.ensure_one()
        self.do_unreserve()
        return True

    def action_cancel(self):
        """Cancel the stock moves and remove the analytic lines created from
        stock moves when cancelling the task.
        """
        self.mapped("move_ids.move_line_ids").write({"quantity": 0})
        # Use sudo to avoid error for users with no access to analytic
        self.sudo().stock_analytic_line_ids.unlink()
        self.stock_moves_is_locked = True
        return True

    def action_toggle_stock_moves_is_locked(self):
        self.ensure_one()
        self.stock_moves_is_locked = not self.stock_moves_is_locked
        return True

    def action_done(self):
        # Filter valid stock moves (avoiding those done and cancelled).
        price_dp = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        moves_to_skip = self.move_ids.filtered(lambda x: x.state in ("done", "cancel"))
        moves_to_do = self.move_ids - moves_to_skip
        for move in moves_to_do.filtered(
            lambda x: float_is_zero(x.quantity, precision_digits=price_dp)
        ):
            move.quantity = move.product_uom_qty
        moves_to_do.picking_id.with_context(skip_sanity_check=True).button_validate()

    def action_see_move_scrap(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_stock_scrap")
        action["domain"] = [("task_id", "=", self.id)]
        action["context"] = dict(self._context, default_origin=self.name)
        return action

    def write(self, vals):
        res = super().write(vals)
        if "stage_id" in vals:
            stage = self.env["project.task.type"].browse(vals.get("stage_id"))
            if stage.done_stock_moves:
                # Avoid permissions error if the user does not have access to stock.
                self.sudo().action_assign()
        # Update info
        field_names = ("location_id", "location_dest_id")
        if any(vals.get(field) for field in field_names):
            self._update_moves_info()
        return res

    def unlink(self):
        # Use sudo to avoid error to users with no access to analytic
        # related to hr_timesheet addon
        return super(ProjectTask, self.sudo()).unlink()


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    use_stock_moves = fields.Boolean(
        help="If you mark this check, when a task goes to this state, "
        "it will use stock moves",
    )
    done_stock_moves = fields.Boolean(
        help="If you check this box, when a task is in this state, you will not "
        "be able to add more stock moves but they can be viewed."
    )
