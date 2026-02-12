from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Proyecto",
        help="Proyecto relacionado con esta linea de compra.",
        default=lambda self: self.env.context.get("default_project_id"),
    )
    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
        help="Tarea relacionada con esta linea de compra.",
        domain="[('parent_id', '=', False), ('is_template_project', '=', False), ('is_task_template', '=', False)]",
    )

    @api.onchange("order_id")
    def _onchange_order_id_set_project(self):
        for line in self:
            if not line.project_id and line.order_id and line.order_id.project_id:
                line.project_id = line.order_id.project_id

    @api.onchange("task_id")
    def _onchange_task_id_set_project(self):
        for line in self:
            if line.task_id and not line.project_id:
                line.project_id = line.task_id.project_id
            elif line.task_id and line.project_id != line.task_id.project_id:
                line.project_id = line.task_id.project_id
            if line.task_id and line.task_id.is_template_project:
                line.task_id = False
            if line.task_id and "is_task_template" in line.task_id._fields and line.task_id.is_task_template:
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
                    _(
                        "Solo se pueden seleccionar tareas padre en la linea de compra."
                    )
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
            if vals.get("project_id") or not vals.get("order_id"):
                continue
            order = self.env["purchase.order"].browse(vals["order_id"])
            if order.project_id:
                vals["project_id"] = order.project_id.id
        return super().create(vals_list)
