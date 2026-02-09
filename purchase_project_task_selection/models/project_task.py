from odoo import _, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    purchase_line_ids = fields.One2many(
        comodel_name="purchase.order.line",
        inverse_name="task_id",
        string="Lineas de compra",
    )
    purchase_line_count = fields.Integer(
        string="Compras",
        compute="_compute_purchase_line_count",
    )

    def _compute_purchase_line_count(self):
        for task in self:
            task.purchase_line_count = len(task.purchase_line_ids)

    def action_view_purchase_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Lineas de compra"),
            "res_model": "purchase.order.line",
            "view_mode": "list,form,pivot,graph",
            "domain": [("task_id", "=", self.id)],
            "context": {
                "default_task_id": self.id,
                "default_project_id": self.project_id.id,
            },
        }
