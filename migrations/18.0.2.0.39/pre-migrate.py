import logging

_logger = logging.getLogger(__name__)

_MODULE = 'cartona_odoo'

_GROUP_MAP = (
    ('group_marketplace_user', 'group_cartona_user'),
    ('group_marketplace_manager', 'group_cartona_manager'),
)

_MARKETPLACE_CRON_XMLIDS = (
    'cron_pull_marketplace_orders',
    'cron_pull_marketplace_orders_ir_actions_server',
)

_STALE_ACL_XMLIDS = (
    'access_cartona_config_user',
    'access_cartona_config_manager',
    'access_cartona_api_user',
    'access_cartona_api_manager',
    'access_cartona_sync_log_user',
    'access_cartona_sync_log_manager',
    'access_cartona_sync_log_line_user',
    'access_cartona_sync_log_line_manager',
    'access_cartona_order_processor_user',
    'access_cartona_order_processor_manager',
    'access_cartona_product_sync_user',
    'access_cartona_product_sync_manager',
)

_OBSOLETE_PRODUCT_COLUMNS = (
    'cartona_sync_status',
    'cartona_sync_date',
    'cartona_sync_error',
)

_MODEL_TABLE = {
    'ir.cron': 'ir_cron',
    'ir.actions.server': 'ir_act_server',
    'res.groups': 'res_groups',
    'queue.job.channel': 'queue_job_channel',
    'ir.model.access': 'ir_model_access',
}


def _table_for_model(model):
    return _MODEL_TABLE.get(model, model.replace('.', '_'))


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


def _xmlid_row(cr, module, name):
    cr.execute(
        """
        SELECT res_id, model
        FROM ir_model_data
        WHERE module = %s AND name = %s
        LIMIT 1
        """,
        (module, name),
    )
    return cr.fetchone()


def _cartona_pull_cron_active(cr):
    row = _xmlid_row(cr, _MODULE, 'cron_pull_cartona_orders')
    if not row:
        _logger.warning(
            'Cartona 18.0.2.0.39: cron_pull_cartona_orders xmlid missing; '
            'skipping marketplace cron removal',
        )
        return False
    cron_id = row[0]
    cr.execute("SELECT active FROM ir_cron WHERE id = %s", (cron_id,))
    active_row = cr.fetchone()
    if not active_row or not active_row[0]:
        _logger.warning(
            'Cartona 18.0.2.0.39: cron_pull_cartona_orders (id=%s) inactive; '
            'skipping marketplace cron removal',
            cron_id,
        )
        return False
    return True


def _migrate_groups(cr):
    migrated_users = 0
    removed_old_memberships = 0
    removed_groups = 0

    for old_name, new_name in _GROUP_MAP:
        old_row = _xmlid_row(cr, _MODULE, old_name)
        new_row = _xmlid_row(cr, _MODULE, new_name)
        if not old_row:
            continue
        if not new_row:
            _logger.warning(
                'Cartona 18.0.2.0.39: target group %s missing; skipping %s',
                new_name,
                old_name,
            )
            continue

        old_gid, old_model = old_row
        new_gid, _new_model = new_row
        if old_model != 'res.groups':
            continue

        cr.execute(
            """
            INSERT INTO res_groups_users_rel (gid, uid)
            SELECT %s, uid
            FROM res_groups_users_rel
            WHERE gid = %s
            ON CONFLICT DO NOTHING
            """,
            (new_gid, old_gid),
        )
        migrated_users += cr.rowcount

        cr.execute(
            "DELETE FROM res_groups_users_rel WHERE gid = %s",
            (old_gid,),
        )
        removed_old_memberships += cr.rowcount

        cr.execute(
            """
            DELETE FROM res_groups_implied_rel
            WHERE gid = %s OR hid = %s
            """,
            (old_gid, old_gid),
        )
        cr.execute(
            "DELETE FROM rule_group_rel WHERE group_id = %s",
            (old_gid,),
        )
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (_MODULE, old_name),
        )
        cr.execute("DELETE FROM res_groups WHERE id = %s", (old_gid,))
        if cr.rowcount:
            removed_groups += 1

    _logger.info(
        'Cartona 18.0.2.0.39 group cleanup: migrated_users=%s '
        'removed_old_memberships=%s removed_groups=%s',
        migrated_users,
        removed_old_memberships,
        removed_groups,
    )


def _remove_marketplace_cron(cr):
    removed_crons = 0
    removed_server_actions = 0

    for xmlid in _MARKETPLACE_CRON_XMLIDS:
        row = _xmlid_row(cr, _MODULE, xmlid)
        if not row:
            continue
        res_id, model = row
        table = _table_for_model(model)

        if model == 'ir.cron':
            cr.execute(
                "UPDATE ir_cron SET active = false WHERE id = %s",
                (res_id,),
            )

        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (_MODULE, xmlid),
        )
        if _table_exists(cr, table):
            cr.execute(f'DELETE FROM "{table}" WHERE id = %s', (res_id,))
            if model == 'ir.cron':
                removed_crons += cr.rowcount
            elif model == 'ir.actions.server':
                removed_server_actions += cr.rowcount

    _logger.info(
        'Cartona 18.0.2.0.39 cron cleanup: removed_crons=%s removed_server_actions=%s',
        removed_crons,
        removed_server_actions,
    )


def _cleanup_marketplace_channel(cr):
    if not _table_exists(cr, 'queue_job'):
        _logger.info('Cartona 18.0.2.0.39: queue_job table missing; skipping channel cleanup')
        return

    cr.execute(
        """
        SELECT COUNT(*)
        FROM queue_job
        WHERE channel = 'marketplace'
          AND state IN (
              'pending', 'enqueued', 'failed', 'started', 'wait_dependencies'
          )
        """
    )
    active_jobs = cr.fetchone()[0]
    if active_jobs:
        _logger.warning(
            'Cartona 18.0.2.0.39: %s active queue jobs on marketplace channel; '
            'skipping channel removal',
            active_jobs,
        )
        return

    channel_id = None
    row = _xmlid_row(cr, _MODULE, 'queue_job_channel_marketplace')
    if row:
        channel_id = row[0]
    elif _table_exists(cr, 'queue_job_channel'):
        cr.execute(
            """
            SELECT id FROM queue_job_channel
            WHERE complete_name = 'root.marketplace'
            LIMIT 1
            """
        )
        channel_row = cr.fetchone()
        if channel_row:
            channel_id = channel_row[0]

    if not channel_id:
        _logger.info('Cartona 18.0.2.0.39: marketplace queue channel not found')
        return

    removed_functions = 0
    if _table_exists(cr, 'queue_job_function'):
        cr.execute(
            "DELETE FROM queue_job_function WHERE channel_id = %s",
            (channel_id,),
        )
        removed_functions = cr.rowcount

    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = %s AND name = 'queue_job_channel_marketplace'
        """,
        (_MODULE,),
    )
    cr.execute("DELETE FROM queue_job_channel WHERE id = %s", (channel_id,))
    removed_channels = cr.rowcount

    _logger.info(
        'Cartona 18.0.2.0.39 channel cleanup: removed_functions=%s removed_channels=%s',
        removed_functions,
        removed_channels,
    )


def _drop_orphan_schema(cr):
    if _table_exists(cr, 'marketplace_delivery_otp_wizard'):
        cr.execute("DROP TABLE marketplace_delivery_otp_wizard")
        _logger.info('Cartona 18.0.2.0.39: dropped marketplace_delivery_otp_wizard')

    dropped_columns = 0
    for column in _OBSOLETE_PRODUCT_COLUMNS:
        cr.execute(
            "DELETE FROM ir_model_fields WHERE model = 'product.product' AND name = %s",
            (column,),
        )
        if _column_exists(cr, 'product_product', column):
            cr.execute(f'ALTER TABLE product_product DROP COLUMN "{column}"')
            dropped_columns += 1

    _logger.info(
        'Cartona 18.0.2.0.39 schema cleanup: dropped_product_columns=%s',
        dropped_columns,
    )


def _remove_stale_acl_rows(cr):
    removed_access = 0
    removed_metadata = 0

    for xmlid in _STALE_ACL_XMLIDS:
        row = _xmlid_row(cr, _MODULE, xmlid)
        if not row:
            continue
        access_id, model = row
        if model != 'ir.model.access':
            continue

        cr.execute("DELETE FROM ir_model_access WHERE id = %s", (access_id,))
        removed_access += cr.rowcount
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (_MODULE, xmlid),
        )
        removed_metadata += cr.rowcount

    _logger.info(
        'Cartona 18.0.2.0.39 ACL cleanup: removed_access=%s removed_metadata=%s',
        removed_access,
        removed_metadata,
    )


def migrate(cr, version):
    _logger.info('Running cartona_odoo 18.0.2.0.39 pre-migration (marketplace cleanup)')

    _migrate_groups(cr)

    if _cartona_pull_cron_active(cr):
        _remove_marketplace_cron(cr)
    else:
        _logger.warning(
            'Cartona 18.0.2.0.39: marketplace cron left in place (Cartona cron guard failed)',
        )

    _cleanup_marketplace_channel(cr)
    _drop_orphan_schema(cr)
    _remove_stale_acl_rows(cr)

    _logger.info('cartona_odoo 18.0.2.0.39 pre-migration complete')
