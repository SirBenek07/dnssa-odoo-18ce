from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Proyecto",
        help="Proyecto relacionado con esta linea de factura.",
        default=lambda self: self.env.context.get("default_project_id"),
    )
    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
        help="Tarea relacionada con esta linea de factura.",
        domain="[('parent_id', '=', False), ('is_closed', '=', False), ('active', '=', True), ('display_in_project', '=', True), ('is_template_project', '=', False), ('is_task_template', '=', False)]",
    )

    @api.onchange("move_id")
    def _onchange_move_id_set_project(self):
        for line in self:
            if not line.project_id and line.move_id and line.move_id.project_id:
                line.project_id = line.move_id.project_id

    @api.onchange("task_id")
    def _onchange_task_id_set_project(self):
        for line in self:
            if line.task_id and not line.project_id:
                line.project_id = line.task_id.project_id
            elif line.task_id and line.project_id != line.task_id.project_id:
                line.project_id = line.task_id.project_id
            if line.task_id and line.task_id.is_template_project:
                line.task_id = False
            if (
                line.task_id
                and "is_task_template" in line.task_id._fields
                and line.task_id.is_task_template
            ):
                line.task_id = False

    @api.onchange("project_id")
    def _onchange_project_id_clear_task_if_mismatch(self):
        for line in self:
            if line.project_id and line.task_id and line.task_id.project_id != line.project_id:
                line.task_id = False

    @api.constrains("project_id", "task_id")
    def _check_project_task_consistency(self):
        for line in self:
            if line.task_id and line.project_id and line.task_id.project_id != line.project_id:
                raise ValidationError(
                    _(
                        "La tarea '%(task)s' no pertenece al proyecto '%(project)s'.",
                        task=line.task_id.display_name,
                        project=line.project_id.display_name,
                    )
                )

    @api.constrains("task_id", "company_id")
    def _check_task_company_consistency(self):
        for line in self:
            if (
                line.task_id
                and line.task_id.company_id
                and line.company_id
                and line.task_id.company_id != line.company_id
            ):
                raise ValidationError(
                    _(
                        "La tarea '%(task)s' pertenece a otra compania (%(company)s).",
                        task=line.task_id.display_name,
                        company=line.task_id.company_id.display_name,
                    )
                )

    @api.constrains("task_id")
    def _check_task_is_parent(self):
        for line in self:
            if line.task_id and line.task_id.parent_id:
                raise ValidationError(
                    _("Solo se pueden seleccionar tareas padre en la linea de factura.")
                )
            if line.task_id and line.task_id.is_closed:
                raise ValidationError(
                    _("No se pueden seleccionar tareas cerradas en la linea de factura.")
                )
            if line.task_id and not line.task_id.active:
                raise ValidationError(
                    _("No se pueden seleccionar tareas archivadas en la linea de factura.")
                )
            if line.task_id and not line.task_id.display_in_project:
                raise ValidationError(
                    _("No se pueden seleccionar subtareas ocultas en la linea de factura.")
                )
            if line.task_id and line.task_id.is_template_project:
                raise ValidationError(
                    _("No se pueden seleccionar tareas de proyectos plantilla.")
                )
            if (
                line.task_id
                and "is_task_template" in line.task_id._fields
                and line.task_id.is_task_template
            ):
                raise ValidationError(
                    _("No se pueden seleccionar tareas marcadas como plantilla.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_id") or not vals.get("move_id"):
                continue
            move = self.env["account.move"].browse(vals["move_id"])
            if move.project_id:
                vals["project_id"] = move.project_id.id
        return super().create(vals_list)
