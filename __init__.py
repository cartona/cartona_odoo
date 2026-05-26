from . import models
from . import wizards


def post_init_hook(env):
    """Create Cartona configuration for the main company on fresh install."""
    main_company = env.ref('base.main_company')
    if not env['cartona.config'].search([('company_id', '=', main_company.id)]):
        env['cartona.config'].create({
            'name': 'Cartona',
            'company_id': main_company.id,
            'auth_token': 'CHANGE_ME',
        })
    admin = env.ref('base.user_admin')
    manager_group = env.ref('cartona_odoo.group_cartona_manager')
    if manager_group not in admin.groups_id:
        admin.write({'groups_id': [(4, manager_group.id)]})


def uninstall_hook(env):
    pass
