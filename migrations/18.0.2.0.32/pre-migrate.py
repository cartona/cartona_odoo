import logging

_logger = logging.getLogger(__name__)


def _legacy_columns_exist(cr):
    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_product'
          AND column_name = 'cartona_sync_status'
        LIMIT 1
    """)
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _legacy_columns_exist(cr):
        _logger.info('Cartona pivot pre-migrate: no legacy product sync columns, skipping')
        return

    cr.execute("""
        CREATE TABLE IF NOT EXISTS _cartona_sync_migrate (
            product_id integer NOT NULL,
            cartona_config_id integer NOT NULL,
            sync_status varchar,
            sync_date timestamp without time zone,
            sync_error text,
            PRIMARY KEY (product_id, cartona_config_id)
        )
    """)
    cr.execute("DELETE FROM _cartona_sync_migrate")
    cr.execute("""
        INSERT INTO _cartona_sync_migrate (
            product_id, cartona_config_id, sync_status, sync_date, sync_error
        )
        SELECT
            pp.id,
            cc.id,
            pp.cartona_sync_status,
            pp.cartona_sync_date,
            pp.cartona_sync_error
        FROM product_product pp
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        CROSS JOIN cartona_config cc
        WHERE (pt.company_id IS NULL OR pt.company_id = cc.company_id)
          AND pp.cartona_sync_status IS NOT NULL
          AND pp.cartona_sync_status != 'not_synced'
    """)
    _logger.info(
        'Cartona pivot pre-migrate: staged %s legacy sync rows',
        cr.rowcount,
    )
