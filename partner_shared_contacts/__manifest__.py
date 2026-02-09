{
    "name": "Partner Shared Contacts",
    "version": "18.0.1.0.0",
    "summary": "Share one contact across multiple partners without duplication.",
    "depends": ["contacts"],
    "post_init_hook": "post_init_hook",
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
