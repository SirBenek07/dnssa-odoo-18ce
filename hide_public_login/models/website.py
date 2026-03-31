# -*- coding: utf-8 -*-

from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    hide_public_login = fields.Boolean(
        string="Ocultar acceso publico al login",
        default=True,
        help="Oculta el enlace de inicio de sesion en la cabecera del sitio web publico.",
    )
