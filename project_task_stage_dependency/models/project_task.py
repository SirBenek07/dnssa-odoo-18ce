from odoo import _, api, models, fields
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_datetime


class ProjectTask(models.Model):
    _inherit = "project.task"

    dependency_task_ids = fields.Many2many(
        comodel_name="project.task",
        relation="project_task_stage_dependency_rel",
        column1="task_id",
        column2="dependency_task_id",
        string="Tareas bloqueantes",
        help="Tareas recomendadas a finalizar antes de cambiar esta tarea de etapa.",
    )
    completion_stage_id = fields.Many2one(
        comodel_name="project.task.type",
        string="Etapa obligatoria de cierre",
        help="Etapa que debe alcanzarse antes de considerar la tarea como finalizada.",
    )
    completion_stage_enforcement = fields.Selection(
        selection=[
            ("block", "Bloquear"),
            ("warn", "Advertir"),
        ],
        string="Comportamiento de dependencia",
        default="block",
        help=(
            "Define que pasa al mover la etapa de la tarea padre si esta subtarea "
            "no esta cerrada y su etapa obligatoria ya debio cumplirse."
        ),
    )
    warn_stage_change_ack = fields.Boolean(
        string="Confirmacion interna de advertencia de etapa",
        default=False,
        copy=False,
    )

    def write(self, vals):
        stage_id = vals.get("stage_id")
        new_stage = (
            self.env["project.task.type"].browse(stage_id) if stage_id else False
        )
        warn_by_task = {}
        warn_details_by_task = {}
        planned_fields = {"planned_date_start", "planned_date_end"}
        track_planned_dates = bool(planned_fields & vals.keys())
        previous_dates = {}
        if track_planned_dates:
            previous_dates = {
                task.id: {
                    "start": task.planned_date_start,
                    "end": task.planned_date_end,
                }
                for task in self
            }
        if stage_id:
            for task in self:
                if task.stage_id.id == stage_id:
                    continue
                task._check_dependency_tasks_for_stage_change()
                task._check_subtask_stage_change_forbidden()
                task._check_descendants_completion_for_parent_stage_change(new_stage)
                warn_message = task._get_descendant_warn_message(new_stage)
                warn_by_task[task.id] = warn_message
                warn_details_by_task[task.id] = task._get_descendant_warn_details(new_stage)

        has_warn = any(warn_by_task.values())
        ui_ack = bool(vals.get("warn_stage_change_ack"))
        if (
            has_warn
            and not self.env.context.get("allow_warn_stage_change")
            and not ui_ack
        ):
            first_details = next(
                details for details in warn_details_by_task.values() if details
            )
            raise ValidationError(
                _(
                    "Advertencia\n"
                    "No puede cambiar de etapa desde esta vista porque hay subtareas pendientes en modo Advertir.\n\n"
                    "Si estas seguro de cambiar de etapa igualmente:\n"
                    "1. Abra la tarea en vista formulario.\n"
                    "2. Cambie la etapa desde el formulario.\n\n"
                    "Subtareas pendientes:\n"
                    "%(details)s",
                    details=first_details,
                )
            )
        res = super().write(vals)
        warned_tasks = self.filtered(lambda task: warn_by_task.get(task.id))
        if warned_tasks.filtered("warn_stage_change_ack"):
            warned_tasks.with_context(skip_warn_ack_reset=True).write(
                {"warn_stage_change_ack": False}
            )
        for task in self:
            warning_message = warn_by_task.get(task.id)
            if warning_message:
                task.message_post(
                    body=_("Advertencia\n%(message)s", message=warning_message),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
        if track_planned_dates:
            self._log_planned_date_changes(previous_dates, vals)
        return res

    @api.onchange("stage_id")
    def _onchange_stage_dependency_warning(self):
        for task in self:
            if not task.stage_id or task.stage_id == task._origin.stage_id:
                continue
            incomplete_tasks = task.dependency_task_ids.filtered(
                lambda dependency_task: not dependency_task.is_closed
            )
            if incomplete_tasks:
                details = self._format_dependency_issue_lines(incomplete_tasks)
                return {
                    "warning": {
                        "title": _("Advertencia"),
                        "message": _(
                            "Hay tareas bloqueantes pendientes:\n%(details)s",
                            details=details,
                        ),
                    }
                }
            if not task.parent_id:
                blocking_descendants, warn_descendants = task._get_descendant_completion_issues(task.stage_id)
                if blocking_descendants:
                    # El bloqueo tiene prioridad; se evita mostrar advertencia en onchange.
                    return {}
                if warn_descendants:
                    task.warn_stage_change_ack = True
                    details = self._format_descendant_issue_lines(warn_descendants)
                    return {
                        "warning": {
                            "title": _("Advertencia"),
                            "message": _(
                                "La tarea cambiara de etapa igualmente, pero tenga en cuenta "
                                "que hay subtareas pendientes:\n%(details)s",
                                details=details,
                            ),
                        }
                    }

    def _check_dependency_tasks_for_stage_change(self):
        incomplete_tasks = self.dependency_task_ids.filtered(
            lambda dependency_task: not dependency_task.is_closed
        )
        if incomplete_tasks:
            raise ValidationError(
                _(
                    "No se puede cambiar la etapa de '%(task)s' porque tiene tareas "
                    "bloqueantes pendientes: %(deps)s.",
                    task=self.display_name,
                    deps=", ".join(incomplete_tasks.mapped("display_name")),
                )
            )

    def _check_subtask_stage_change_forbidden(self):
        if self.parent_id and not self.env.context.get("allow_subtask_stage_change"):
            raise ValidationError(
                _(
                    "Las subtareas no permiten cambio de etapa. Use el campo Estado "
                    "(En progreso / Cambios solicitados / Aprobada / Cancelada / Hecha)."
                )
            )

    def _check_descendants_completion_for_parent_stage_change(self, target_stage):
        """Block moving a parent task forward if descendants are still open and
        declare a mandatory completion stage that should have been completed
        before (or at) the target parent stage.
        """
        if not target_stage or self.parent_id:
            return
        blocking_descendants, _warn_descendants = self._get_descendant_completion_issues(
            target_stage
        )
        if blocking_descendants:
            details = self._format_descendant_issue_lines(blocking_descendants)
            raise ValidationError(
                _(
                    "Bloqueo\n"
                    "No puede cambiar de etapa porque hay subtareas pendientes:\n"
                    "%(details)s",
                    details=details,
                )
            )

    def _get_descendant_completion_issues(self, target_stage):
        base_id = self.id if isinstance(self.id, int) else self._origin.id
        if not base_id:
            return self.browse(), self.browse()
        descendants = self.search(
            [("id", "child_of", [base_id]), ("id", "!=", base_id)]
        )
        relevant_descendants = descendants.filtered(
            lambda task: (
                not task.is_closed
                and task.completion_stage_id
                and task.completion_stage_id.sequence < target_stage.sequence
            )
        )
        blocking_descendants = relevant_descendants.filtered(
            lambda task: task.completion_stage_enforcement != "warn"
        )
        warn_descendants = relevant_descendants - blocking_descendants
        return blocking_descendants, warn_descendants

    def _format_descendant_issue_lines(self, tasks):
        lines = [
            "- %s (%s)" % (task.display_name, task.completion_stage_id.display_name)
            for task in tasks[:10]
        ]
        if len(tasks) > 10:
            lines.append(_("- ... y %(count)s mas", count=len(tasks) - 10))
        return "\n".join(lines)

    def _format_dependency_issue_lines(self, tasks):
        lines = [
            "- %s" % task.display_name
            for task in tasks[:10]
        ]
        if len(tasks) > 10:
            lines.append(_("- ... y %(count)s mas", count=len(tasks) - 10))
        return "\n".join(lines)

    def _get_descendant_warn_message(self, target_stage):
        if not target_stage or self.parent_id:
            return False
        blocking_descendants, warn_descendants = self._get_descendant_completion_issues(
            target_stage
        )
        if blocking_descendants or not warn_descendants:
            return False
        details = self._format_descendant_issue_lines(warn_descendants)
        return _(
            "La tarea cambiara de etapa igualmente, pero tenga en cuenta "
            "que hay subtareas pendientes:\n%(details)s",
            details=details,
        )

    def _get_descendant_warn_details(self, target_stage):
        if not target_stage or self.parent_id:
            return False
        blocking_descendants, warn_descendants = self._get_descendant_completion_issues(
            target_stage
        )
        if blocking_descendants or not warn_descendants:
            return False
        return self._format_descendant_issue_lines(warn_descendants)

    def _is_kanban_write_context(self):
        params = self.env.context.get("params") or {}
        if isinstance(params, dict):
            if params.get("view_type") == "kanban":
                return True
            action_ctx = params.get("context")
            if isinstance(action_ctx, dict) and action_ctx.get("view_type") == "kanban":
                return True
        return False

    def _is_form_write_context(self):
        params = self.env.context.get("params") or {}
        if not isinstance(params, dict):
            return False
        if params.get("view_type") == "form":
            return True
        action_ctx = params.get("context")
        if isinstance(action_ctx, dict) and action_ctx.get("view_type") == "form":
            return True
        return False

    def _log_planned_date_changes(self, previous_dates, vals):
        for task in self:
            old_dates = previous_dates.get(task.id, {})
            messages = []
            labels = {
                "planned_date_start": self._fields["planned_date_start"].string,
                "planned_date_end": self._fields["planned_date_end"].string,
            }
            if "planned_date_start" in vals:
                old_start = old_dates.get("start")
                new_start = task.planned_date_start
                if old_start != new_start:
                    messages.append(
                        _(
                            "- %(label)s: %(old)s -> %(new)s",
                            label=labels["planned_date_start"],
                            old=self._format_datetime_for_log(old_start),
                            new=self._format_datetime_for_log(new_start),
                        )
                    )
            if "planned_date_end" in vals:
                old_end = old_dates.get("end")
                new_end = task.planned_date_end
                if old_end != new_end:
                    messages.append(
                        _(
                            "- %(label)s: %(old)s -> %(new)s",
                            label=labels["planned_date_end"],
                            old=self._format_datetime_for_log(old_end),
                            new=self._format_datetime_for_log(new_end),
                        )
                    )
            if messages:
                lines = [
                    _("Fechas planificadas actualizadas:"),
                    *messages,
                ]
                body = "\n".join(lines)
                task.message_post(
                    body=body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

    def _format_datetime_for_log(self, value):
        if not value:
            return _("Sin definir")
        return format_datetime(self.env, value, tz=self.env.user.tz or "UTC")
