import logging

_logger = logging.getLogger(__name__)

TABLE_RENAMES = {
    'marketplace_config': 'cartona_config',
    'marketplace_api': 'cartona_api',
    'marketplace_order_processor': 'cartona_order_processor',
    'marketplace_sync_log': 'cartona_sync_log',
}

MODEL_RENAMES = {
    'marketplace.config': 'cartona.config',
    'marketplace.api': 'cartona.api',
    'marketplace.order.processor': 'cartona.order.processor',
    'marketplace.sync.log': 'cartona.sync.log',
    'marketplace.delivery.otp.wizard': 'cartona.delivery.otp.wizard',
}

FIELD_RENAMES = {
    'product_product': {
        'marketplace_sync_status': 'cartona_sync_status',
        'marketplace_sync_date': 'cartona_sync_date',
        'marketplace_error_message': 'cartona_sync_error',
    },
    'sale_order': {
        'marketplace_config_id': 'cartona_config_id',
        'marketplace_sync_status': 'cartona_sync_status',
        'marketplace_sync_date': 'cartona_sync_date',
        'marketplace_error_message': 'cartona_error_message',
        'is_marketplace_order': 'is_cartona_order',
        'marketplace_order_number': 'cartona_order_number',
        'marketplace_status': 'cartona_status',
        'marketplace_payment_method': 'cartona_payment_method',
        'marketplace_notes': 'cartona_notes',
        'marketplace_delivery_otp': 'cartona_delivery_otp',
    },
    'sale_order_line': {
        'marketplace_line_id': 'cartona_line_id',
        'marketplace_sku': 'cartona_sku',
        'marketplace_notes': 'cartona_line_notes',
    },
    'res_partner': {
        'marketplace_source': 'cartona_config_id',
        'is_marketplace_customer': 'is_cartona_customer',
        'marketplace_sync_date': 'cartona_sync_date',
    },
    'cartona_sync_log': {
        'marketplace_config_id': 'cartona_config_id',
    },
}

COLUMNS_TO_DROP = {
    'product_product': ['cartona_id', 'marketplace_stock_sync_enabled', 'last_stock_sync_date', 'stock_sync_error'],
    'product_template': [
        'cartona_id', 'delivered_by', 'marketplace_sync_status', 'marketplace_sync_date',
        'marketplace_error_message', 'marketplace_sync_enabled',
    ],
    'sale_order_line': ['marketplace_product_id'],
    'res_partner': [
        'marketplace_sync_status', 'marketplace_error_message',
        'partner_type_marketplace', 'last_customer_sync_date',
    ],
    'cartona_config': [
        'auto_sync_prices', 'auto_sync_stock', 'auto_pull_orders',
        'retry_attempts', 'auth_header',
    ],
    'stock_quant': [
        'marketplace_stock_sync_status', 'last_marketplace_sync', 'stock_sync_error',
    ],
    'stock_location': ['marketplace_sync_enabled', 'marketplace_location_code'],
}


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return cr.fetchone() is not None


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def _rename_table(cr, old, new):
    if _table_exists(cr, old) and not _table_exists(cr, new):
        cr.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')
        _logger.info('Renamed table %s -> %s', old, new)


def _rename_column(cr, table, old, new):
    if not _table_exists(cr, table):
        return
    if _column_exists(cr, table, old) and not _column_exists(cr, table, new):
        cr.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"')
        _logger.info('Renamed column %s.%s -> %s', table, old, new)


def _drop_column(cr, table, column):
    if not _table_exists(cr, table):
        return
    if _column_exists(cr, table, column):
        cr.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')
        _logger.info('Dropped column %s.%s', table, column)


def _add_column(cr, table, column, coltype='boolean', default='false'):
    if not _table_exists(cr, table):
        return
    if not _column_exists(cr, table, column):
        cr.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{column}" {coltype} DEFAULT {default}'
        )
        _logger.info('Added column %s.%s', table, column)


def _update_ir_model(cr):
    for old_model, new_model in MODEL_RENAMES.items():
        cr.execute(
            "UPDATE ir_model SET model = %s WHERE model = %s",
            (new_model, old_model),
        )


def _update_ir_model_fields(cr):
    for table, renames in FIELD_RENAMES.items():
        for old_field, new_field in renames.items():
            cr.execute(
                """
                UPDATE ir_model_fields
                SET name = %s
                WHERE model IN %s AND name = %s
                """,
                (
                    new_field,
                    tuple(MODEL_RENAMES.values()) + tuple(MODEL_RENAMES.keys()),
                    old_field,
                ),
            )
    for table in COLUMNS_TO_DROP:
        for column in COLUMNS_TO_DROP[table]:
            cr.execute(
                "DELETE FROM ir_model_fields WHERE name = %s",
                (column,),
            )


def migrate(cr, version):
    _logger.info('Running cartona_odoo 18.0.2.0.0 post-migration')

    for old_table, new_table in TABLE_RENAMES.items():
        _rename_table(cr, old_table, new_table)

    for table, renames in FIELD_RENAMES.items():
        for old_col, new_col in renames.items():
            _rename_column(cr, table, old_col, new_col)

    _add_column(cr, 'cartona_config', 'is_cartona_sync_enabled')

    for table, columns in COLUMNS_TO_DROP.items():
        for column in columns:
            _drop_column(cr, table, column)

    _update_ir_model(cr)
    _update_ir_model_fields(cr)

    _logger.info('cartona_odoo 18.0.2.0.0 post-migration complete')
