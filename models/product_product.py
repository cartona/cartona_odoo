from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import time

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    cartona_sync_ids = fields.One2many(
        'cartona.product.sync',
        'product_id',
        string='Cartona Sync Status',
    )
    cartona_is_unlimited_stock = fields.Boolean(
        string='Unlimited Stock',
        default=False,
        help=(
            'When enabled, Cartona receives is_unlimited_stock=true instead of the '
            'actual warehouse stock quantity.'
        ),
    )

    def _cartona_internal_product_id(self):
        self.ensure_one()
        return str(self.id)

    def _cartona_company(self):
        self.ensure_one()
        return self.company_id or self.env.company

    def _cartona_enabled_configs(self):
        """All enabled configs for the variant's company (price/product fan-out)."""
        self.ensure_one()
        return self.env['cartona.config'].enabled_configs_for_company(
            self._cartona_company(),
        )

    def _cartona_sync_record(self, config):
        self.ensure_one()
        if not config:
            return self.env['cartona.product.sync']
        return self.env['cartona.product.sync'].get_for_product_config(self, config)

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_cartona_sync'):
            if 'lst_price' in vals:
                self._trigger_cartona_sync('price')
            if 'cartona_is_unlimited_stock' in vals:
                # Fan out to all company configs — this flag is variant-level, not warehouse-specific
                self._trigger_cartona_sync('stock')
        return result

    def _queue_cartona_sync(self, record, config, sync_fields):
        # config_id is passed as an explicit job argument rather than via with_context()
        # because queue_job only preserves an allow-listed subset of context keys
        # (tz, lang, allowed_company_ids, force_company, active_test) when it serializes
        # a job for storage - cartona_config_id would otherwise be silently dropped and
        # _sync_to_cartona would fall back to the wrong config once the job actually runs.
        record.with_delay(
            channel='cartona',
            description=(
                f'Sync variant {record.display_name} to Cartona '
                f'[{config.warehouse_id.name}] ({sync_fields})'
            ),
        )._sync_to_cartona(sync_fields, config_id=config.id)

    def _trigger_cartona_sync(self, sync_fields, warehouse=None):
        """Route sync jobs by intent.

        - stock: only the config of the affected ``warehouse``.
        - price/product: fan out to every enabled config of the variant's company.
        """
        if self.env.context.get('skip_cartona_sync'):
            return
        config_model = self.env['cartona.config']
        for record in self:
            if sync_fields == 'stock' and warehouse:
                config = config_model.get_for_warehouse(warehouse)
                configs = config if (config and config.is_cartona_sync_enabled) else config_model.browse()
            else:
                configs = record._cartona_enabled_configs()
            for config in configs:
                self._queue_cartona_sync(record, config, sync_fields)

    def _cartona_sync_operation_type(self, sync_fields):
        return 'stock_sync' if sync_fields == 'stock' else 'product_sync'

    def _cartona_sync_log_line_vals(self, variant, sync_fields, payload, result):
        success = result.get('success')
        return {
            'status': 'success' if success else 'error',
            'entry_type': 'product',
            'internal_product_id': str(variant.id),
            'record_model': 'product.product',
            'record_id': variant.id,
            'record_name': variant.display_name,
            'message': _(
                '%(result)s variant %(variant)s (%(fields)s)'
            ) % {
                'result': 'Synced' if success else 'Failed to sync',
                'variant': variant.display_name,
                'fields': sync_fields,
            },
            'request_data': json.dumps({
                'endpoint': 'supplier-product/bulk-update',
                'method': 'POST',
                'sync_fields': sync_fields,
                'payload': payload,
            }, indent=2, ensure_ascii=False, default=str),
            'response_data': result.get('response_data'),
        }

    def _sync_to_cartona(self, sync_fields='both', config_id=None):
        self.ensure_one()
        # Prefer the explicit argument (see _queue_cartona_sync); fall back to context
        # only for direct synchronous calls (e.g. action_manual_cartona_sync) and any
        # already-queued legacy jobs still in the backlog when this deploys.
        config_id = config_id or self.env.context.get('cartona_config_id')
        if config_id:
            config = self.env['cartona.config'].browse(config_id)
        else:
            config = self._cartona_enabled_configs()[:1]
        if not config or not config.is_cartona_sync_enabled:
            return
        warehouse = config.warehouse_id
        sync_rec = self.env['cartona.product.sync'].get_for_product_config(self, config)
        sync_rec.mark_syncing()
        api = self.env['cartona.api'].with_company(config.company_id).with_context(
            cartona_config_id=config.id,
            cartona_warehouse_id=warehouse.id,
        )
        start = time.time()
        result = api.bulk_update_products(self, sync_fields=sync_fields)
        duration = time.time() - start
        payload = api._build_variant_payload(
            self, sync_fields, company=config.company_id, warehouse=warehouse,
        )
        log = self.env['cartona.sync.log']
        log_kwargs = {
            'request_data': result.get('request_data'),
            'response_data': result.get('response_data'),
            'duration': duration,
            'action_type': self.env.context.get('cartona_log_action_type', 'automated'),
            'line_vals_list': [self._cartona_sync_log_line_vals(self, sync_fields, payload, result)],
        }
        if result.get('success'):
            sync_rec.mark_success()
            log.log_product_sync(
                config.id, self, 'success',
                _('Synced variant to Cartona (%(fields)s)') % {'fields': sync_fields},
                operation_type=self._cartona_sync_operation_type(sync_fields),
                records_processed=1,
                records_success=1,
                **log_kwargs,
            )
        else:
            error_msg = result.get('error', 'Unknown error')
            sync_rec.mark_error(error_msg)
            log.log_product_sync(
                config.id, self, 'error',
                _('Failed to sync variant to Cartona (%(fields)s)') % {'fields': sync_fields},
                operation_type=self._cartona_sync_operation_type(sync_fields),
                records_processed=1,
                records_error=1,
                error_details=error_msg,
                **log_kwargs,
            )

    def _sync_stock_to_marketplaces(self):
        """Legacy queue_job method from pre-cartona rename."""
        for record in self:
            record._sync_to_cartona('stock')

    def action_manual_cartona_sync(self):
        self.ensure_one()
        configs = self._cartona_enabled_configs()
        if not configs:
            raise UserError(_('Enable Cartona sync on a configuration first.'))
        synced = 0
        for config in configs:
            self.with_context(
                cartona_log_action_type='manual',
            )._sync_to_cartona('both', config_id=config.id)
            if self._cartona_sync_record(config).sync_status == 'synced':
                synced += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _(
                    'Variant %(variant)s synced to %(synced)s of %(total)s warehouse config(s).'
                ) % {
                    'variant': self.display_name,
                    'synced': synced,
                    'total': len(configs),
                },
                'type': 'success' if synced == len(configs) else 'warning',
            },
        }
