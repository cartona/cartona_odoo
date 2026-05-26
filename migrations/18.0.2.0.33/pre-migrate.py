import logging

_logger = logging.getLogger(__name__)

_OBSOLETE_PRODUCT_FIELDS = (
    'cartona_id',
    'cartona_sync_status',
    'cartona_sync_date',
    'cartona_sync_error',
)


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


def migrate(cr, version):
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
        'Cartona 18.0.2.0.33 view cleanup: removed %s cartona_odoo product.product views',
        removed,
    )
