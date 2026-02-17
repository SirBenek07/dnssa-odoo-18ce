{
    "name": "Reportes Financieros",
    "version": "18.0.1.0.0",
    "category": "Accounting/Reporting",
    "summary": "Balance general y flujo de caja",
    "author": "DNS",
    "license": "LGPL-3",
    "depends": ["account", "date_range"],
    "data": [
        "security/ir.model.access.csv",
        "views/balance_general_wizard_views.xml",
        "report/paperformat.xml",
        "report/report_actions.xml",
        "report/balance_general_templates.xml",
    ],
    "installable": True,
    "application": False,
}
