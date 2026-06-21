import logging

_logger = logging.getLogger(__name__)

_MODULE = 'cartona_odoo'


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
        (table,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _pick_warehouse(cr, company_id):
    """Choose the warehouse that actually holds this company's stock.

    Primary heuristic: the internal warehouse with the most stock_quant rows
    (this maps prod config 1 -> SB2B, where stock lives). Fall back to the
    company's first warehouse if it has no quants at all. Returns None only for
    a company with no warehouse (degenerate setup).
    """
    cr.execute(
        """
        SELECT sl.warehouse_id
        FROM stock_quant sq
        JOIN stock_location sl ON sl.id = sq.location_id
        WHERE sl.usage = 'internal'
          AND sq.company_id = %s
          AND sl.warehouse_id IS NOT NULL
        GROUP BY sl.warehouse_id
        ORDER BY COUNT(*) DESC, sl.warehouse_id
        LIMIT 1
        """,
        (company_id,),
    )
    row = cr.fetchone()
    if row:
        return row[0]

    cr.execute(
        "SELECT id FROM stock_warehouse WHERE company_id = %s ORDER BY id LIMIT 1",
        (company_id,),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _backfill_warehouse(cr):
    if not _column_exists(cr, 'cartona_config', 'warehouse_id'):
        cr.execute('ALTER TABLE cartona_config ADD COLUMN warehouse_id integer')
        _logger.info('Cartona 18.0.2.0.47: added cartona_config.warehouse_id column')

    cr.execute(
        "SELECT id, company_id FROM cartona_config WHERE warehouse_id IS NULL"
    )
    rows = cr.fetchall()
    backfilled = 0
    skipped = 0
    for config_id, company_id in rows:
        warehouse_id = _pick_warehouse(cr, company_id)
        if warehouse_id:
            cr.execute(
                "UPDATE cartona_config SET warehouse_id = %s WHERE id = %s",
                (warehouse_id, config_id),
            )
            backfilled += 1
            _logger.info(
                'Cartona 18.0.2.0.47: config %s (company %s) -> warehouse %s',
                config_id, company_id, warehouse_id,
            )
        else:
            skipped += 1
            _logger.warning(
                'Cartona 18.0.2.0.47: config %s (company %s) has no warehouse; '
                'leaving warehouse_id NULL (admin must set it before sync)',
                config_id, company_id,
            )
    _logger.info(
        'Cartona 18.0.2.0.47 warehouse backfill: backfilled=%s skipped=%s',
        backfilled, skipped,
    )


def _drop_company_uniq(cr):
    # The old per-company uniqueness is replaced by per-warehouse uniqueness.
    cr.execute(
        "ALTER TABLE cartona_config DROP CONSTRAINT IF EXISTS cartona_config_company_uniq"
    )
    cr.execute(
        """
        DELETE FROM ir_model_constraint
        WHERE name = 'cartona_config_company_uniq'
        """
    )
    _logger.info('Cartona 18.0.2.0.47: dropped company_uniq (if present)')


def migrate(cr, version):
    if not _table_exists(cr, 'cartona_config'):
        _logger.info(
            'Cartona 18.0.2.0.47: cartona_config table missing; nothing to migrate'
        )
        return

    _logger.info('Running cartona_odoo 18.0.2.0.47 pre-migration (per-warehouse config)')
    _backfill_warehouse(cr)
    _drop_company_uniq(cr)
    # NOT NULL on warehouse_id and the warehouse_uniq constraint are added by the
    # ORM from the field definition / _sql_constraints after this pre-migrate. Odoo
    # logs a warning (and continues) for any residual NULL warehouse_id, so a
    # warehouse-less company never blocks the upgrade.
    _logger.info('cartona_odoo 18.0.2.0.47 pre-migration complete')
