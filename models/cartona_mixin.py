from odoo import _

CARTONA_AUTH_HEADER = 'AuthorizationToken'


def cartona_sync_enabled(env, company=None):
    """Return True when Cartona sync is active for any config in the company."""
    return bool(env['cartona.config'].enabled_configs_for_company(company))
