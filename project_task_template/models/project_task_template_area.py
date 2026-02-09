from odoo import fields, models


class ProjectTaskTemplateArea(models.Model):
    _name = "project.task.template.area"
    _description = "Task Template Area"
    _order = "project_id, name, id"

    name = fields.Char(required=True)
    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "project_task_template_area_project_name_uniq",
            "unique(project_id, name)",
            "El nombre del area debe ser unico por proyecto.",
        )
    ]

