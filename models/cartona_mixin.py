from odoo import _

CARTONA_AUTH_HEADER = 'AuthorizationToken'


def cartona_sync_enabled(env):
    """Return True when global Cartona sync is active."""
    config = env['cartona.config'].search([], limit=1)
    return bool(config and config.is_cartona_sync_enabled)
