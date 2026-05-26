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

    def _cartona_internal_product_id(self):
        self.ensure_one()
        return str(self.id)

    def _cartona_company(self):
        self.ensure_one()
        return self.company_id or self.env.company

    def _cartona_config(self):
        self.ensure_one()
        return self.env['cartona.config'].get_for_company(self._cartona_company())

    def _cartona_sync_record(self, config=None):
        self.ensure_one()
        if not config:
            config = self._cartona_config()
        if not config:
            return self.env['cartona.product.sync']
        return self.env['cartona.product.sync'].get_for_product_config(self, config)

    def write(self, vals):
        result = super().write(vals)
        if 'lst_price' in vals and not self.env.context.get('skip_cartona_sync'):
            self._trigger_cartona_sync('price')
        return result

    def _trigger_cartona_sync(self, sync_fields):
        if self.env.context.get('skip_cartona_sync'):
            return
        for record in self:
            config = record._cartona_config()
            if not config or not config.is_cartona_sync_enabled:
                continue
            record.with_context(
                cartona_config_id=config.id,
            ).with_delay(
                channel='cartona',
                description=f'Sync variant {record.display_name} to Cartona ({sync_fields})',
            )._sync_to_cartona(sync_fields)

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

    def _sync_to_cartona(self, sync_fields='both'):
        self.ensure_one()
        config_id = self.env.context.get('cartona_config_id')
        if config_id:
            config = self.env['cartona.config'].browse(config_id)
        else:
            config = self._cartona_config()
        if not config or not config.is_cartona_sync_enabled:
            return
        sync_rec = self.env['cartona.product.sync'].get_for_product_config(self, config)
        sync_rec.mark_syncing()
        api = self.env['cartona.api'].with_company(config.company_id).with_context(
            cartona_config_id=config.id,
        )
        start = time.time()
        result = api.bulk_update_products(self, sync_fields=sync_fields)
        duration = time.time() - start
        payload = api._build_variant_payload(self, sync_fields, company=config.company_id)
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

    def action_manual_cartona_sync(self):
        self.ensure_one()
        config = self._cartona_config()
        if not config or not config.is_cartona_sync_enabled:
            raise UserError(_('Enable Cartona sync on configuration first.'))
        self.with_context(
            cartona_config_id=config.id,
            cartona_log_action_type='manual',
        )._sync_to_cartona('both')
        sync_rec = self._cartona_sync_record(config)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _('Variant sync finished for %s') % self.display_name,
                'type': 'success' if sync_rec.sync_status == 'synced' else 'warning',
            },
        }
