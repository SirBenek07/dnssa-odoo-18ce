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
        domain="[('parent_id', '=', False), ('is_closed', '=', False), ('active', '=', True), ('display_in_project', '=', True), ('is_template_project', '=', False), ('is_task_template', '=', False), ('project_id', '=?', expense_project_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    @api.depends("analytic_distribution")
    def _compute_expense_project_id(self):
        for expense in self:
            analytic_ids = expense._extract_analytic_account_ids(
                expense.analytic_distribution
            )
            if not analytic_ids:
                expense.expense_project_id = False
                continue
            projects = self.env["project.project"].search(
                [("account_id", "in", list(analytic_ids))]
            )
            expense.expense_project_id = projects[0] if len(projects) == 1 else False

    @api.model
    def _extract_analytic_account_ids(self, distribution):
        """Odoo 18 stores analytic_distribution as a JSON map whose keys can be
        single ids ('12') or combined ids ('12,34')."""
        analytic_ids = set()
        for key in (distribution or {}):
            if not key:
                continue
            for account_id in str(key).split(","):
                account_id = account_id.strip()
                if account_id.isdigit():
                    analytic_ids.add(int(account_id))
        return analytic_ids

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
                    or expense.parent_task_id.is_template_project
                    or (
                        "is_task_template" in expense.parent_task_id._fields
                        and expense.parent_task_id.is_task_template
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
            if expense.parent_task_id and expense.parent_task_id.is_template_project:
                raise ValidationError(
                    _("No se pueden seleccionar tareas de proyectos plantilla.")
                )
            if (
                expense.parent_task_id
                and "is_task_template" in expense.parent_task_id._fields
                and expense.parent_task_id.is_task_template
            ):
                raise ValidationError(
                    _("No se pueden seleccionar tareas marcadas como plantilla.")
                )
