from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mostrar_powered_by_sitio = fields.Boolean(
        string="Mostrar 'Powered by Odoo' en sitio web",
        config_parameter='dns_hide_powered_by.mostrar_powered_by_sitio',
        default=True,
        help="Si se desmarca, se oculta el mensaje en el pie del sitio web.",
    )

    mostrar_powered_by_login = fields.Boolean(
        string="Mostrar 'Powered by Odoo' en login",
        config_parameter='dns_hide_powered_by.mostrar_powered_by_login',
        default=False,
        help="Si se marca, se muestra el enlace 'Powered by Odoo' en la pantalla de login.",
    )

    texto_html_footer = fields.Html(
        string="Texto personalizado del footer (HTML)",
        help="Opcional: reemplaza el texto por defecto del footer con contenido HTML.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo()
        res.update({
            'texto_html_footer': param.get_param(
                'dns_hide_powered_by.texto_html_footer',
                default='',
            ),
        })
        return res

    def set_values(self):
        super().set_values()
        param = self.env['ir.config_parameter'].sudo()
        param.set_param(
            'dns_hide_powered_by.texto_html_footer',
            self.texto_html_footer or '',
        )
