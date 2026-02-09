from odoo import _, api, fields, models


class ProjectTaskDependencyCloseWarnWizard(models.TransientModel):
    _name = "project.task.dependency.close.warn.wizard"
    _description = "Confirmar cierre de tarea con dependencias en advertencia"

    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tarea",
        required=True,
        readonly=True,
    )
    warning_message = fields.Text(
        string="Mensaje",
        readonly=True,
        compute="_compute_warning_message",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get("task_id"):
            task_id = self.env.context.get("default_task_id") or self.env.context.get(
                "active_id"
            )
            if task_id:
                res["task_id"] = task_id
        return res

    @api.depends("task_id")
    def _compute_warning_message(self):
        for wizard in self:
            if not wizard.task_id:
                wizard.warning_message = False
                continue
            pending = wizard.task_id.dependency_task_ids.filtered(
                lambda dependency_task: not dependency_task.is_closed
            )
            if not pending:
                wizard.warning_message = _(
                    "No hay tareas bloqueantes pendientes."
                )
                continue
            details = "\n".join(f"- {task.display_name}" for task in pending)
            wizard.warning_message = _(
                "La tarea se marcara como hecha igualmente, pero tenga en cuenta "
                "que hay tareas bloqueantes pendientes:\n%(details)s",
                details=details,
            )

    def action_confirm(self):
        self.ensure_one()
        self.task_id.with_context(allow_dependency_warn_close_confirm=True).write(
            {"state": "1_done"}
        )
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
