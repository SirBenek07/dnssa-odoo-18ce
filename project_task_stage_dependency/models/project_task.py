from odoo import _, models, fields
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_datetime

TASK_CLOSED_STATES = {"1_done", "1_canceled"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    dependency_task_ids = fields.Many2many(
        comodel_name="project.task",
        relation="project_task_stage_dependency_rel",
        column1="task_id",
        column2="dependency_task_id",
        string="Blocking Tasks",
        help="Tasks that must be finished before this task can change stage.",
    )
    completion_stage_id = fields.Many2one(
        comodel_name="project.task.type",
        string="Required Completion Stage",
        help="Stage that must be reached before the task can be considered done.",
    )

    def write(self, vals):
        stage_id = vals.get("stage_id")
        new_stage = (
            self.env["project.task.type"].browse(stage_id) if stage_id else False
        )
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
                task._check_stage_dependencies(new_stage or task.stage_id)
        new_state = vals.get("state")
        if new_state in TASK_CLOSED_STATES:
            for task in self:
                future_stage = new_stage or task.stage_id
                task._check_completion_stage(future_stage)
        res = super().write(vals)
        if track_planned_dates:
            self._log_planned_date_changes(previous_dates, vals)
        return res

    def _check_stage_dependencies(self, target_stage):
        if not target_stage or target_stage == self.stage_id:
            return
        incomplete_tasks = self.dependency_task_ids.filtered(
            lambda task: not task.is_closed
        )
        if incomplete_tasks:
            raise ValidationError(
                _(
                    "You cannot move '%(task)s' to stage '%(stage)s' until these tasks are done: %(deps)s",
                    task=self.display_name,
                    stage=target_stage.display_name,
                    deps=", ".join(incomplete_tasks.mapped("display_name")),
                )
            )

    def _check_completion_stage(self, target_stage):
        if not target_stage:
            return
        if self.completion_stage_id and target_stage != self.completion_stage_id:
            raise ValidationError(
                _(
                    "Task '%(task)s' can only be completed when it is in stage '%(required)s'.",
                    task=self.display_name,
                    required=self.completion_stage_id.display_name,
                )
            )

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
                            "- %(label)s: %(old)s → %(new)s",
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
                            "- %(label)s: %(old)s → %(new)s",
                            label=labels["planned_date_end"],
                            old=self._format_datetime_for_log(old_end),
                            new=self._format_datetime_for_log(new_end),
                        )
                    )
            if messages:
                lines = [
                    _("Planned dates updated:"),
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
            return _("Not set")
        return format_datetime(self.env, value, tz=self.env.user.tz or "UTC")
