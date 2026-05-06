{
    'name': 'Moo Olympiad Portal',
    'version': '1.0.0',
    'category': 'Events',
    'summary': 'Olympiad event management portal',
    'description': """Moo Olympiad Portal
====================

Provide external access for mentors and jury members.
    """,
    'author': 'Ahmet Cangir',
    'website': 'https://github.com/wpmoo-org/moo_olympiad',
    'license': 'LGPL-3',
    'depends': ['moo_olympiad', 'portal', 'website', 'auth_signup'],
    'data': [
        'security/olympiad_portal_security.xml',
        'security/ir.model.access.csv',
        'views/olympiad_portal_templates.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}