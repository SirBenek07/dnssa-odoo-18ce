{
    "name": "Cheque Managment",
    "version": "18.0.1.0.0",
    "author": "Federico Fernandez",
    "summary": "Gestion de cheques emitidos por diarios bancarios",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/account_payment_method_data.xml",
        "views/account_journal_views.xml",
        "views/account_cheque_views.xml",
        "views/account_payment_views.xml",
        "views/account_payment_register_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
