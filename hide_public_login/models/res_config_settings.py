# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    website_hide_public_login = fields.Boolean(
        string="Ocultar acceso publico al login",
        related='website_id.hide_public_login',
        readonly=False,
        help="Oculta el enlace de inicio de sesion visible en el sitio web publico.",
    )
