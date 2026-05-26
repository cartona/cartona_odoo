from odoo import _

CARTONA_AUTH_HEADER = 'AuthorizationToken'


def cartona_sync_enabled(env, company=None):
    """Return True when Cartona sync is active for the given company."""
    config = env['cartona.config'].get_for_company(company)
    return bool(config and config.is_cartona_sync_enabled)
