from datetime import datetime, time

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    calendar_date_start = fields.Datetime(
        compute="_compute_calendar_dates",
        string="Calendar Start",
    )
    calendar_date_stop = fields.Datetime(
        compute="_compute_calendar_dates",
        string="Calendar End",
    )

    @api.depends(
        "planned_date_start",
        "planned_date_end",
        "date_assign",
        "date_deadline",
        "date_end",
        "create_date",
    )
    def _compute_calendar_dates(self):
        today = fields.Date.context_today(self)
        default_stop = datetime.combine(today, time(hour=23, minute=59, second=59))
        for task in self:
            start_date = task.planned_date_start or task.date_assign
            if not start_date and task.date_deadline:
                start_date = datetime.combine(task.date_deadline, time.min)
            if not start_date and task.create_date:
                start_date = task.create_date
            stop_date = False
            if task.date_end:
                stop_date = task.date_end
            elif task.planned_date_end:
                stop_date = task.planned_date_end
            elif start_date:
                stop_date = default_stop
            if start_date and stop_date and stop_date < start_date:
                stop_date = start_date
            task.calendar_date_start = start_date
            task.calendar_date_stop = stop_date
