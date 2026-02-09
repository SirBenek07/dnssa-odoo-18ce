{
    "name": "Purchase Project Task Selection",
    "summary": "Link purchase order lines to project and task",
    "version": "18.0.1.0.0",
    "category": "Purchases",
    "author": "Federico Fernandez",
    "license": "AGPL-3",
    "depends": ["purchase", "project", "account", "hr_expense", "sale_project_task_selection"],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_views.xml",
        "views/project_task_views.xml",
        "views/hr_expense_views.xml",
        "wizard/project_cash_flow_wizard_views.xml",
        "report/project_cash_flow_report.xml"
    ],
    "installable": True
}
