{
    "name": "Prestamos Managment",
    "version": "18.0.1.0.0",
    "author": "Federico Fernandez",
    "summary": "Gestion contable de prestamos, cuotas e intereses",
    "depends": ["account", "analytic", "mail", "product"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "wizard/prestamos_payment_register_views.xml",
        "views/res_partner_views.xml",
        "views/prestamos_loan_views.xml",
        "views/prestamos_payment_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
