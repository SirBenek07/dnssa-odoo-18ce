# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    calendar_event_task_ids = fields.One2many(
        "calendar.event",
        "project_task_id",
        string="Task Calendar Events",
    )

    def _calendar_sync_relevant_values(self):
        return {
            "name",
            "active",
            "user_ids",
            "project_id",
            "date_deadline",
            "stage_id",
            "planned_date_start",
            "planned_date_end",
        }

    def _get_task_calendar_schedule(self):
        self.ensure_one()
        has_planned_start = "planned_date_start" in self._fields and self.planned_date_start
        has_planned_end = "planned_date_end" in self._fields and self.planned_date_end

        if has_planned_start:
            start = self.planned_date_start
            stop = self.planned_date_end if has_planned_end else (start + timedelta(hours=1))
            if stop < start:
                stop = start + timedelta(hours=1)
            return {"start": start, "stop": stop, "allday": False}

        if self.date_deadline:
            start = datetime.combine(self.date_deadline, time.min)
            return {"start": start, "stop": start, "allday": True}

        return {}

    def _is_task_eligible_for_calendar_sync(self):
        self.ensure_one()
        return bool(
            self.active
            and self.project_id
            and self.user_ids
            and self._get_task_calendar_schedule()
        )

    def _prepare_task_calendar_event_vals(self, user, model_task_id):
        self.ensure_one()
        schedule = self._get_task_calendar_schedule()
        return {
            "name": self.name,
            "description": self._get_task_calendar_description(),
            "user_id": user.id,
            "partner_ids": [(6, 0, [user.partner_id.id])],
            "privacy": "private",
            "show_as": "busy",
            "allday": schedule["allday"],
            "start": schedule["start"],
            "stop": schedule["stop"],
            "res_model_id": model_task_id,
            "res_id": self.id,
            "project_task_id": self.id,
            "project_task_assignee_id": user.id,
            "active": True,
        }

    def _get_task_calendar_description(self):
        self.ensure_one()
        project_name = self.project_id.display_name if self.project_id else "-"
        lines = [f"[Proyecto] {project_name}"]
        if self.parent_id:
            lines.append(f"[Evento] {self.parent_id.display_name}")
        lines.append(f"[Tarea] {self.display_name}")
        return "\n".join(lines)

    def _remove_task_calendar_event(self, event):
        owner = event.user_id or event.project_task_assignee_id or self.env.user
        event.with_user(owner).with_context(dont_notify=True)._cancel()

    def _sync_task_calendar_events(self):
        model_task_id = self.env["ir.model"]._get_id("project.task")
        event_model = self.env["calendar.event"].with_context(active_test=False)

        for task in self:
            existing_events = task.with_context(active_test=False).calendar_event_task_ids
            target_users = (
                task.user_ids.filtered(lambda user: bool(user.partner_id))
                if task._is_task_eligible_for_calendar_sync()
                else self.env["res.users"]
            )
            target_map = {
                user.id: task._prepare_task_calendar_event_vals(user, model_task_id)
                for user in target_users
            }

            for event in existing_events:
                assignee_id = event.project_task_assignee_id.id
                if assignee_id not in target_map:
                    task._remove_task_calendar_event(event)
                    continue

                vals = target_map.pop(assignee_id)
                owner = event.user_id or event.project_task_assignee_id
                event.with_user(owner).with_context(dont_notify=True).write(vals)

            for assignee_id, vals in target_map.items():
                owner = self.env["res.users"].browse(assignee_id)
                event_model.with_user(owner).with_context(dont_notify=True).create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._sync_task_calendar_events()
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if self._calendar_sync_relevant_values() & set(vals):
            self._sync_task_calendar_events()
        return res

    def unlink(self):
        for task in self:
            for event in task.with_context(active_test=False).calendar_event_task_ids:
                task._remove_task_calendar_event(event)
        return super().unlink()
