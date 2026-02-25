{
    "name": "Payroll Paraguay",
    "version": "18.0.1.0.0",
    "category": "Payroll",
    "summary": "Paraguay payroll presets: IPS and vendor-bill payment flow",
    "author": "Federico Fernandez",
    "license": "LGPL-3",
    "depends": ["payroll_account", "product", "hr_work_entry_holidays"],
    "data": [
        "data/payroll_paraguay_holidays_data.xml",
        "data/payroll_paraguay_data.xml",
        "views/payroll_paraguay_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
