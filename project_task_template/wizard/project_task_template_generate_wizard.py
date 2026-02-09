from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectTaskTemplateGenerateWizard(models.TransientModel):
    _name = "project.task.template.generate.wizard"
    _description = "Generate Tasks From Template Wizard"

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        readonly=True,
    )
    template_task_id = fields.Many2one(
        comodel_name="project.task",
        string="Plantilla",
        required=True,
        domain="[('project_id', '=', project_id), ('is_task_template', '=', True), ('parent_id', '=', False)]",
    )
    root_planned_date_start = fields.Datetime(
        string="Fecha Inicio",
        required=True,
    )
    root_planned_date_end = fields.Datetime(
        string="Fecha Fin",
        required=True,
    )
    generated_task_name = fields.Char(string="Nombre de tarea raiz")
    area_line_ids = fields.One2many(
        comodel_name="project.task.template.generate.wizard.area.line",
        inverse_name="wizard_id",
        string="Encargados por area",
    )

    @api.onchange("project_id", "template_task_id")
    def _onchange_template_values(self):
        for wizard in self:
            line_commands = [(5, 0, 0)]
            if wizard.template_task_id:
                template_tasks = self.env["project.task"].search(
                    [
                        ("id", "child_of", wizard.template_task_id.id),
                        ("project_id", "=", wizard.project_id.id),
                        ("is_task_template", "=", True),
                    ]
                )
                areas = template_tasks.mapped("template_area_ids")
                legacy_areas = template_tasks.mapped("template_area_id")
                areas |= legacy_areas
                areas = areas.sorted("name")
            else:
                areas = wizard.project_id.template_area_ids.sorted("name")
            for area in areas.filtered("id"):
                line_commands.append(
                    (
                        0,
                        0,
                        {
                            "area_id": area.id,
                        },
                    )
                )
            wizard.area_line_ids = line_commands

    def action_generate(self):
        self.ensure_one()
        if not self.root_planned_date_start or not self.root_planned_date_end:
            raise ValidationError(
                _("Para generar tareas se necesita asignar fecha de Inicio/Fin.")
            )
        invalid_lines = self.area_line_ids.filtered(lambda line: not line.area_id)
        if invalid_lines:
            raise ValidationError(
                _("Se detectaron lineas de encargado sin Area. Vuelva a seleccionar la plantilla.")
            )
        assignee_by_template_area = {
            line.area_id.id: line.user_id
            for line in self.area_line_ids
            if line.area_id and line.user_id
        }
        assignee_by_template_area_name = {
            line.area_id.name: line.user_id
            for line in self.area_line_ids
            if line.area_id and line.area_id.name and line.user_id
        }
        self.project_id.generate_tasks_from_template(
            template_root_task=self.template_task_id,
            root_planned_date_start=self.root_planned_date_start,
            root_planned_date_end=self.root_planned_date_end,
            assignee_by_template_area=assignee_by_template_area,
            assignee_by_template_area_name=assignee_by_template_area_name,
            generated_task_name=self.generated_task_name,
        )
        return {"type": "ir.actions.act_window_close"}


class ProjectTaskTemplateGenerateWizardAreaLine(models.TransientModel):
    _name = "project.task.template.generate.wizard.area.line"
    _description = "Generate Tasks From Template Wizard Area Line"

    wizard_id = fields.Many2one(
        comodel_name="project.task.template.generate.wizard",
        required=True,
        ondelete="cascade",
    )
    area_id = fields.Many2one(
        comodel_name="project.task.template.area",
        required=True,
        readonly=True,
        string="Area",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Encargado",
        domain="[('share', '=', False)]",
    )
