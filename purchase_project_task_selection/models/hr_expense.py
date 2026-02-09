from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrExpense(models.Model):
    _inherit = "hr.expense"

    expense_project_id = fields.Many2one(
        comodel_name="project.project",
        compute="_compute_expense_project_id",
        readonly=True,
    )
    parent_task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
        domain="[('parent_id', '=', False), ('is_closed', '=', False), ('active', '=', True), ('display_in_project', '=', True), ('project_id.name', 'not ilike', '(TEMPLATE)'), ('project_id', '=?', expense_project_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    @api.depends("analytic_distribution")
    def _compute_expense_project_id(self):
        for expense in self:
            analytic_ids = expense._get_analytic_account_ids_from_distributions(
                expense.analytic_distribution
            )
            if not analytic_ids:
                expense.expense_project_id = False
                continue
            projects = self.env["project.project"].search(
                [("account_id", "in", list(analytic_ids))]
            )
            expense.expense_project_id = projects[0] if len(projects) == 1 else False

    @api.onchange("analytic_distribution")
    def _onchange_analytic_distribution_parent_task_id(self):
        for expense in self:
            if (
                expense.parent_task_id
                and (
                    expense.parent_task_id.parent_id
                    or expense.parent_task_id.is_closed
                    or not expense.parent_task_id.active
                    or not expense.parent_task_id.display_in_project
                    or (
                        "is_template" in expense.parent_task_id.project_id._fields
                        and expense.parent_task_id.project_id.is_template
                    )
                    or expense.parent_task_id.project_id != expense.expense_project_id
                )
            ):
                expense.parent_task_id = False

    @api.constrains("parent_task_id")
    def _check_parent_task_id_is_parent(self):
        for expense in self:
            if expense.parent_task_id and expense.parent_task_id.parent_id:
                raise ValidationError(
                    _("Solo se pueden seleccionar tareas padre en el gasto.")
                )
            if expense.parent_task_id and expense.parent_task_id.is_closed:
                raise ValidationError(
                    _("Solo se pueden seleccionar tareas no finalizadas en el gasto.")
                )
            if expense.parent_task_id and not expense.parent_task_id.active:
                raise ValidationError(
                    _("Solo se pueden seleccionar tareas activas en el gasto.")
                )
            if expense.parent_task_id and not expense.parent_task_id.display_in_project:
                raise ValidationError(
                    _("Solo se pueden seleccionar tareas visibles del proyecto.")
                )
            if (
                expense.parent_task_id
                and "is_template" in expense.parent_task_id.project_id._fields
                and expense.parent_task_id.project_id.is_template
            ):
                raise ValidationError(
                    _("No se pueden seleccionar tareas de proyectos plantilla.")
                )
