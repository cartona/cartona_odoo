import logging

_logger = logging.getLogger(__name__)

_OBSOLETE_PRODUCT_FIELDS = (
    'cartona_id',
    'cartona_sync_status',
    'cartona_sync_date',
    'cartona_sync_error',
)


def _legacy_columns_exist(cr):
    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_product'
          AND column_name = 'cartona_sync_status'
        LIMIT 1
    """)
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


def _cleanup_obsolete_product_views(cr):
    for model in ('product.product', 'product.template'):
        table = model.replace('.', '_')
        for field_name in _OBSOLETE_PRODUCT_FIELDS:
            if _column_exists(cr, table, field_name):
                continue
            cr.execute(
                "DELETE FROM ir_model_fields WHERE model = %s AND name = %s",
                (model, field_name),
            )

    cr.execute("""
        SELECT d.id, d.res_id
        FROM ir_model_data d
        JOIN ir_ui_view v ON v.id = d.res_id
        WHERE d.module = 'cartona_odoo'
          AND d.model = 'ir.ui.view'
          AND v.model = 'product.product'
    """)
    rows = cr.fetchall()
    removed = 0
    if rows:
        cr.execute(
            "DELETE FROM ir_model_data WHERE id = ANY(%s)",
            ([row[0] for row in rows],),
        )
        cr.execute(
            "DELETE FROM ir_ui_view WHERE id = ANY(%s)",
            ([row[1] for row in rows],),
        )
        removed = len(rows)

    _logger.info(
        'Cartona view cleanup: removed %s cartona_odoo product.product views',
        removed,
    )


def migrate(cr, version):
    _cleanup_obsolete_product_views(cr)

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
