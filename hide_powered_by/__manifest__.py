{
    'name': 'Ocultar Powered by Odoo',
    'version': '18.0.1.0.0',
    'summary': 'Unifica el control del Powered by Odoo en login y sitio web.',
    'description': '''
Módulo unificado para:
- Ocultar o mostrar el mensaje "Powered by Odoo" en el login.
- Ocultar o mostrar el mensaje "Powered by Odoo" en el pie del sitio web.
- Definir texto HTML personalizado para el pie del sitio web.

Todas las configuraciones se gestionan desde Ajustes en español.
    ''',
    'author': 'Federico Fernández',
    'website': 'https://dns.com.py',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': ['base', 'web', 'website'],
    'data': [
        'views/res_config_settings_view.xml',
        'views/brand_promotion_override.xml',
        'views/login_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
