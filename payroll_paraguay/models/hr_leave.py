from odoo import models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    def _generate_timesheets(self, ignored_resource_calendar_leaves=None):
        """Skip timesheet generation for PY leave types used only for payroll.

        `project_timesheet_holidays` tries to create analytic lines on leave validation.
        For Paraguay payroll leave types (vacations / unjustified absence) we only need
        work entries for payroll, not timesheets.
        """
        leave_type_ids = []
        for xmlid in (
            "payroll_paraguay.leave_type_vacaciones_py",
            "payroll_paraguay.leave_type_absence_py",
        ):
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                leave_type_ids.append(rec.id)

        if not leave_type_ids:
            return super()._generate_timesheets(
                ignored_resource_calendar_leaves=ignored_resource_calendar_leaves
            )

        non_py_leaves = self.filtered(lambda l: l.holiday_status_id.id not in leave_type_ids)
        if non_py_leaves:
            return super(HrLeave, non_py_leaves)._generate_timesheets(
                ignored_resource_calendar_leaves=ignored_resource_calendar_leaves
            )
        return None
