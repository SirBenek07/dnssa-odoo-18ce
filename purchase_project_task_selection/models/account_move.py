from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Proyecto",
        help="Proyecto relacionado con esta factura.",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        copy=False,
    )

    @api.onchange("project_id")
    def _onchange_project_id_set_lines_project(self):
        for move in self:
            if not move.project_id:
                continue
            for line in move.invoice_line_ids:
                line.project_id = move.project_id
                if line.task_id and line.task_id.project_id != move.project_id:
                    line.task_id = False
                line._sync_analytic_distribution_from_project()
