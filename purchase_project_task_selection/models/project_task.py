from odoo import _, api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    is_template_project = fields.Boolean(
        string="Proyecto plantilla",
        compute="_compute_is_template_project",
        store=True,
        index=True,
    )

    purchase_line_ids = fields.One2many(
        comodel_name="purchase.order.line",
        inverse_name="task_id",
        string="Lineas de compra",
    )
    vendor_bill_line_ids = fields.One2many(
        comodel_name="account.move.line",
        inverse_name="task_id",
        string="Lineas de factura proveedor",
    )
    purchase_line_count = fields.Integer(
        string="Compras",
        compute="_compute_purchase_line_count",
    )
    expense_ids = fields.One2many(
        comodel_name="hr.expense",
        inverse_name="parent_task_id",
        string="Gastos",
    )
    expense_count = fields.Integer(
        string="Gastos",
        compute="_compute_expense_count",
    )

    @api.depends("project_id", "project_id.name", "project_id.write_date")
    def _compute_is_template_project(self):
        for task in self:
            project = task.project_id
            is_template = False
            if project:
                if "is_template" in project._fields:
                    is_template = bool(project.is_template)
                else:
                    is_template = "(TEMPLATE)" in (project.name or "").upper()
            task.is_template_project = is_template

    def _compute_purchase_line_count(self):
        for task in self:
            vendor_bills = task.vendor_bill_line_ids.move_id.filtered(
                lambda move: move.move_type in ("in_invoice", "in_refund", "in_receipt")
            )
            task.purchase_line_count = len(vendor_bills)

    def _compute_expense_count(self):
        for task in self:
            task.expense_count = len(task.expense_ids)

    def action_view_purchase_lines(self):
        self.ensure_one()
        vendor_bills = self.vendor_bill_line_ids.move_id.filtered(
            lambda move: move.move_type in ("in_invoice", "in_refund", "in_receipt")
        )
        if len(vendor_bills) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Factura de proveedor"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": vendor_bills.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Facturas de proveedor"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", vendor_bills.ids)],
            "context": {
                "default_move_type": "in_invoice",
            },
        }

    def action_view_expenses(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "hr_expense.hr_expense_actions_all"
        )
        action.update(
            {
                "name": _("Gastos"),
                "view_mode": "list,form,graph,pivot",
                "views": [[False, "list"], [False, "form"], [False, "graph"], [False, "pivot"]],
                "domain": [("parent_task_id", "=", self.id)],
                "context": {
                    "default_parent_task_id": self.id,
                    "default_analytic_distribution": self.project_id._get_analytic_distribution()
                    if self.project_id
                    else False,
                },
            }
        )
        return action
