# -*- coding: utf-8 -*-

from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    project_task_id = fields.Many2one(
        "project.task",
        string="Project Task",
        index=True,
        copy=False,
        ondelete="set null",
    )
    project_task_assignee_id = fields.Many2one(
        "res.users",
        string="Task Assignee",
        index=True,
        copy=False,
        ondelete="set null",
    )
