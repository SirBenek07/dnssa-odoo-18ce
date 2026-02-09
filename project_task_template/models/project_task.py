from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProjectTask(models.Model):
    _inherit = "project.task"

    is_task_template = fields.Boolean(
        string="Es plantilla de tarea",
        default=False,
        copy=False,
    )
    template_area_id = fields.Many2one(
        comodel_name="project.task.template.area",
        string="Area",
        domain="[('project_id', '=', project_id)]",
    )
    template_area_ids = fields.Many2many(
        comodel_name="project.task.template.area",
        relation="project_task_template_area_rel",
        column1="task_id",
        column2="area_id",
        string="Areas",
        domain="[('project_id', '=', project_id)]",
    )
    template_offset_days = fields.Integer(
        string="Dias",
        default=0,
    )
    template_offset_direction = fields.Selection(
        selection=[
            ("before", "Antes"),
            ("after", "Despues"),
        ],
        string="Respecto a fecha de tarea raiz",
        default="after",
    )

    def _check_template_manage_access(self):
        if not self.env.user.has_group("project.group_project_manager"):
            raise AccessError(
                _("Solo usuarios con rol Proyecto / Administrador pueden gestionar plantillas.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        should_check_access = False
        for vals in vals_list:
            if "template_area_id" in vals and "template_area_ids" not in vals:
                if vals.get("template_area_id"):
                    vals["template_area_ids"] = [(6, 0, [vals["template_area_id"]])]
                else:
                    vals["template_area_ids"] = [(5, 0, 0)]
            parent_id = vals.get("parent_id") or self.env.context.get("default_parent_id")
            if not vals.get("is_task_template") and parent_id:
                parent = self.env["project.task"].browse(parent_id)
                if parent.is_task_template:
                    vals["is_task_template"] = True
            if vals.get("is_task_template"):
                should_check_access = True
        if should_check_access:
            self._check_template_manage_access()
        tasks = super().create(vals_list)
        tasks._sync_template_areas_legacy_fields()
        return tasks

    def write(self, vals):
        vals = dict(vals)
        if "template_area_id" in vals and "template_area_ids" not in vals:
            if vals.get("template_area_id"):
                vals["template_area_ids"] = [(6, 0, [vals["template_area_id"]])]
            else:
                vals["template_area_ids"] = [(5, 0, 0)]
        if "parent_id" in vals and vals["parent_id"] and "is_task_template" not in vals:
            parent = self.env["project.task"].browse(vals["parent_id"])
            if parent.is_task_template:
                vals["is_task_template"] = True
        if "is_task_template" in vals or any(task.is_task_template for task in self):
            self._check_template_manage_access()
        res = super().write(vals)
        if not self.env.context.get("skip_template_area_sync"):
            self._sync_template_areas_legacy_fields()
        return res

    def unlink(self):
        if any(task.is_task_template for task in self):
            self._check_template_manage_access()
        return super().unlink()

    def action_open_generate_from_template_wizard(self):
        self.ensure_one()
        if not self.project_id:
            raise ValidationError(
                _("La tarea debe pertenecer a un proyecto para generar desde plantilla.")
            )
        return self.project_id.action_open_task_template_wizard()

    def action_open_generate_from_template_wizard_project(self):
        project_id = (
            self.env.context.get("default_project_id")
            or self.env.context.get("project_id")
            or self.env.context.get("active_id")
        )
        if not project_id and self:
            project_id = self[0].project_id.id
        if not project_id:
            raise ValidationError(
                _("No se pudo identificar el proyecto para generar tareas desde plantilla.")
            )
        project = self.env["project.project"].browse(project_id)
        return project.action_open_task_template_wizard()

    def _sync_template_areas_legacy_fields(self):
        for task in self:
            if task.template_area_ids:
                first_area = task.template_area_ids[0]
                if task.template_area_id != first_area:
                    super(ProjectTask, task.with_context(skip_template_area_sync=True)).write(
                        {"template_area_id": first_area.id}
                    )
            elif task.template_area_id:
                super(ProjectTask, task.with_context(skip_template_area_sync=True)).write(
                    {"template_area_ids": [(6, 0, [task.template_area_id.id])]}
                )
