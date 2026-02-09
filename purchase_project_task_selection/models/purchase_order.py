from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.onchange("project_id")
    def _onchange_project_id_set_lines_project(self):
        for order in self:
            if not order.project_id:
                continue
            for line in order.order_line:
                line.project_id = order.project_id
                if line.task_id and line.task_id.project_id != order.project_id:
                    line.task_id = False
