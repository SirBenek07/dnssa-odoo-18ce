# -*- coding: utf-8 -*-
{
    "name": "Account Groups for Community (Expose)",
    "version": "18.0.1.0.0",
    "summary": "Expone account.group en Odoo Community (menús, vistas y permisos).",
    "author": "Federico Fernández",
    "license": "LGPL-3",
    "category": "Accounting",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_group_views.xml",
    ],
    "installable": True,
    "application": False,
}
