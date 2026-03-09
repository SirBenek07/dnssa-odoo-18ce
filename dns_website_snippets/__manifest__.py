# -*- coding: utf-8 -*-
{
    "name": "DNS Website Snippets",
    "summary": "Snippets de landing CFO Advisory para DNS SA",
    "version": "18.0.1.0.0",
    "category": "Website",
    "author": "DNS SA",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "views/snippets.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "dns_website_snippets/static/src/scss/dns_snippets.scss",
        ],
    },
    "installable": True,
    "application": False,
}
