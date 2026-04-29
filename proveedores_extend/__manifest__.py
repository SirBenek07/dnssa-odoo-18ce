{
    "name": "Proveedores Extend",
    "version": "18.0.1.0.0",
    "summary": "Add timbrado data to vendor bills.",
    "depends": ["account", "account_invoice_document_type"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/account_move_form_ext.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
