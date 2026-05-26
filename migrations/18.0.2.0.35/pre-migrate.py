import logging

_logger = logging.getLogger(__name__)

_CANCEL_MESSAGE = (
    'Cancelled during cartona_odoo upgrade: obsolete marketplace queue job'
)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE queue_job
        SET state = 'cancelled',
            date_cancelled = NOW() AT TIME ZONE 'UTC',
            exc_name = 'ObsoleteJobError',
            exc_message = %s,
            result = %s
        WHERE method_name LIKE '%%marketplace%%'
          AND state IN (
              'pending', 'enqueued', 'failed', 'started', 'wait_dependencies'
          )
        """,
        (_CANCEL_MESSAGE, _CANCEL_MESSAGE),
    )
    cancelled = cr.rowcount

    cr.execute(
        """
        UPDATE queue_job
        SET method_name = '_sync_to_cartona',
            kwargs = '{"sync_fields": "stock"}'::jsonb
        WHERE method_name = '_sync_stock_to_marketplaces'
          AND model_name = 'product.product'
        """
    )
    remapped_stock = cr.rowcount

    cr.execute(
        """
        UPDATE queue_job
        SET method_name = '_sync_status_to_cartona'
        WHERE method_name = '_sync_status_to_marketplace'
          AND model_name = 'sale.order'
        """
    )
    remapped_orders = cr.rowcount

    cr.execute(
        """
        UPDATE queue_job
        SET channel = 'cartona'
        WHERE channel = 'marketplace'
        """
    )
    channels_updated = cr.rowcount

    _logger.info(
        'Cartona 18.0.2.0.35 queue_job cleanup: cancelled=%s remapped_stock=%s '
        'remapped_orders=%s channel_updates=%s',
        cancelled,
        remapped_stock,
        remapped_orders,
        channels_updated,
    )
