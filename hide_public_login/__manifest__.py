# -*- coding: utf-8 -*-
{
    'name': 'Ocultar Acceso Publico al Login',
    'version': '18.0.1.0.0',
    'summary': 'Permite ocultar el enlace de inicio de sesion en el sitio web publico.',
    'description': '''
Permite ocultar los accesos visibles al inicio de sesion en el encabezado del
sitio web sin deshabilitar el backend ni la URL /web/login.
    ''',
    'author': 'Federico Fernandez',
    'website': 'https://dns.com.py',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': ['portal', 'website'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
