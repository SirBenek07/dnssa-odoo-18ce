{
    "name": "Product Invoice Stats",
    "version": "18.0.1.0.0",
    "summary": "Replaces sold/purchased product stats with customer/vendor invoiced stats.",
    "depends": ["account", "product", "purchase", "sale"],
    "data": [
        "views/product_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
