from . import models
from . import wizards


def post_init_hook(env):
    """Grant the Cartona Manager group to admin on install.

    No placeholder config is auto-created: a config now requires a warehouse,
    and managers add one config per warehouse (with its token) from the
    Cartona configs list. This keeps fresh/empty/warehouse-less setups safe.
    """
    admin = env.ref('base.user_admin')
    manager_group = env.ref('cartona_odoo.group_cartona_manager')
    if manager_group not in admin.groups_id:
        admin.write({'groups_id': [(4, manager_group.id)]})


def uninstall_hook(env):
    pass
