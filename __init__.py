from . import models
from . import wizards


def post_init_hook(env):
    """Create singleton Cartona configuration on install."""
    if not env['cartona.config'].search([]):
        env['cartona.config'].create({
            'name': 'Cartona',
            'auth_token': 'CHANGE_ME',
        })
    admin = env.ref('base.user_admin')
    manager_group = env.ref('cartona_odoo.group_cartona_manager')
    if manager_group not in admin.groups_id:
        admin.write({'groups_id': [(4, manager_group.id)]})


def uninstall_hook(env):
    pass
