import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table_name):
    cr.execute("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = %s
        LIMIT 1
    """, (table_name,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, '_cartona_sync_migrate'):
        _logger.info('Cartona pivot post-migrate: no staging table, skipping')
        return
    if not _table_exists(cr, 'cartona_product_sync'):
        _logger.warning(
            'Cartona pivot post-migrate: pivot table missing, keeping staging data',
        )
        return

    cr.execute("""
        INSERT INTO cartona_product_sync (
            product_id,
            cartona_config_id,
            company_id,
            sync_status,
            sync_date,
            sync_error,
            create_uid,
            write_uid,
            create_date,
            write_date
        )
        SELECT
            m.product_id,
            m.cartona_config_id,
            cc.company_id,
            COALESCE(m.sync_status, 'not_synced'),
            m.sync_date,
            m.sync_error,
            1,
            1,
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC'
        FROM _cartona_sync_migrate m
        JOIN cartona_config cc ON cc.id = m.cartona_config_id
        ON CONFLICT (product_id, cartona_config_id) DO NOTHING
    """)
    _logger.info(
        'Cartona pivot post-migrate: loaded %s rows into cartona_product_sync',
        cr.rowcount,
    )
    cr.execute("DROP TABLE IF EXISTS _cartona_sync_migrate")
