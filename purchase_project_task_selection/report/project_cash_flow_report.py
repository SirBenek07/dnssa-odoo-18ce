from odoo import models


class ReportProjectCashFlow(models.AbstractModel):
    _name = "report.purchase_project_task_selection.report_project_cash_flow"
    _description = "Project Cash Flow Report"

    def _get_report_values(self, docids, data=None):
        docs = self.env["project.cash.flow.wizard"].browse(docids)
        docs.ensure_one()
        report_data = docs._prepare_report_data()
        return {
            "doc_ids": docs.ids,
            "doc_model": "project.cash.flow.wizard",
            "docs": docs,
            "data": report_data,
        }
