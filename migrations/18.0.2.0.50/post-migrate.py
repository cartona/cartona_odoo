import logging

_logger = logging.getLogger(__name__)

_MODULE = 'cartona_odoo'


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
        (table,),
    )
    return bool(cr.fetchone())


def _add_index(cr, index_name, table, columns_sql):
    """Plain (non-CONCURRENTLY) index creation.

    Safe here because this runs during the standard deploy window where
    cartona-shops-web/queue are scaled to 0 (see README rollout checklist),
    so nothing else is writing to these tables while the index builds.
    """
    cr.execute(
        "SELECT 1 FROM pg_indexes WHERE indexname = %s",
        (index_name,),
    )
    if cr.fetchone():
        _logger.info('Cartona 18.0.2.0.50: index %s already exists, skipping', index_name)
        return
    _logger.info('Cartona 18.0.2.0.50: creating index %s on %s ...', index_name, table)
    cr.execute(f"CREATE INDEX {index_name} ON {table} ({columns_sql})")
    _logger.info('Cartona 18.0.2.0.50: index %s created', index_name)


def migrate(cr, version):
    _logger.info('Running cartona_odoo 18.0.2.0.50 post-migration (dashboard issue query indexes)')

    # cartona.sync.log.line had grown to ~9.4M rows with only (id) and
    # (sync_log_id) indexed. The dashboard "product mapping issue" query
    # filters on entry_type/status/error_code (matches >1M rows on its own -
    # not selective) then semi-joins against a small (~300 row) set of
    # recent sync_log ids for one config. sync_log_id MUST lead the index so
    # Postgres drives from that small side with a nested loop instead of
    # bitmap-scanning >1M line rows first: verified in production this drops
    # the query from ~120s to ~0.07s. (entry_type, status, error_code) alone,
    # without sync_log_id leading, still picked the same ~120s plan.
    if _table_exists(cr, 'cartona_sync_log_line'):
        _add_index(
            cr,
            'cartona_sync_log_line_issue_idx',
            'cartona_sync_log_line',
            'sync_log_id, entry_type, status, error_code',
        )
    else:
        _logger.info('Cartona 18.0.2.0.50: cartona_sync_log_line missing; skipping')

    # cartona.sync.log had only (id) indexed. The dashboard "recent sync
    # issue" query filters on cartona_config_id + create_date + status
    # directly, and the same columns are needed as the join target for the
    # line-table query above.
    if _table_exists(cr, 'cartona_sync_log'):
        _add_index(
            cr,
            'cartona_sync_log_config_date_status_idx',
            'cartona_sync_log',
            'cartona_config_id, create_date, status',
        )
    else:
        _logger.info('Cartona 18.0.2.0.50: cartona_sync_log missing; skipping')

    _logger.info('cartona_odoo 18.0.2.0.50 post-migration complete')
