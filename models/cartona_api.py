from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import threading
from datetime import datetime, timedelta

from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class CartonaAPI(models.Model):
    _name = 'cartona.api'
    _description = 'Cartona API Client'

    def _get_cartona_config(self):
        config_id = self.env.context.get('cartona_config_id')
        if not config_id:
            raise UserError(_('No Cartona configuration specified'))
        config = self.env['cartona.config'].browse(config_id)
        if not config.exists():
            raise UserError(_('Invalid Cartona configuration'))
        return config

    def _sync_active(self):
        config = self._get_cartona_config()
        return config.is_cartona_sync_enabled

    def _serialize_for_log(self, value):
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)

    def _api_log_fields(self, endpoint, method, request_body, response_status, response_body):
        return {
            'request_data': self._serialize_for_log({
                'endpoint': endpoint,
                'method': method.upper(),
                'payload': request_body,
            }),
            'response_data': self._serialize_for_log({
                'status_code': response_status,
                'body': response_body,
            }),
        }

    def _make_api_request(self, endpoint, method='GET', data=None, params=None):
        config = self._get_cartona_config()
        url = f"{config.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = config.get_api_headers()
        request_body = data if method.upper() in ('POST', 'PUT', 'PATCH') else (params or {})
        request_params = {
            'url': url,
            'headers': headers,
            'timeout': config.timeout,
        }
        if method.upper() in ('POST', 'PUT', 'PATCH'):
            request_params['json'] = data
        else:
            request_params['params'] = params or {}

        try:
            response = requests.request(method, **request_params)
            log_fields = self._api_log_fields(
                endpoint, method, request_body, response.status_code, response.text,
            )
            if response.status_code in (200, 201):
                try:
                    body = response.json()
                    log_fields = self._api_log_fields(
                        endpoint, method, request_body, response.status_code, body,
                    )
                    if isinstance(body, dict):
                        body.update(log_fields)
                        return body
                    return {'success': True, 'data': body, **log_fields}
                except json.JSONDecodeError:
                    return {'success': True, 'data': response.text, **log_fields}
            if response.status_code == 204:
                return {'success': True, **log_fields}
            error_msg = f'API Error {response.status_code}: {response.text}'
            _logger.error(error_msg)
            return {'success': False, 'error': error_msg, **log_fields}
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f'Timeout after {config.timeout}s',
                **self._api_log_fields(endpoint, method, request_body, None, 'Timeout'),
            }
        except requests.exceptions.ConnectionError as err:
            return {
                'success': False,
                'error': str(err),
                **self._api_log_fields(endpoint, method, request_body, None, str(err)),
            }
        except Exception as err:
            return {
                'success': False,
                'error': str(err),
                **self._api_log_fields(endpoint, method, request_body, None, str(err)),
            }

    def _normalize_api_response(self, response):
        if response is None:
            return {'success': False, 'error': 'No response'}
        if isinstance(response, dict):
            return response if 'success' in response else {'success': True, 'data': response}
        if isinstance(response, list):
            return {'success': True, 'data': response}
        return {'success': True, 'data': response}

    def _build_variant_payload(self, variant, sync_fields, company=None):
        if company:
            variant = variant.with_company(company)
        payload = {'internal_product_id': str(variant.id)}
        if sync_fields in ('price', 'both'):
            payload['selling_price'] = str(variant.lst_price)
        if sync_fields in ('stock', 'both'):
            payload['available_stock_quantity'] = int(variant.free_qty)
        return payload

    def bulk_update_products(self, variants, sync_fields='both'):
        if not variants:
            return {'success': False, 'error': 'No variants'}
        if not self._sync_active():
            return {'success': False, 'error': 'Cartona sync disabled'}

        config = self._get_cartona_config()
        company = config.company_id
        products_data = [
            self._build_variant_payload(v, sync_fields, company=company) for v in variants
        ]
        result = self._make_api_request(
            'supplier-product/bulk-update', method='POST', data=products_data,
        )
        normalized = self._normalize_api_response(result)
        for key in ('request_data', 'response_data'):
            if result.get(key):
                normalized[key] = result[key]
        normalized['sync_fields'] = sync_fields
        normalized['variant_ids'] = variants.ids
        return normalized

    def pull_orders(self, from_date, to_date, page=1, per_page=100):
        params = {
            'page': page,
            'per_page': per_page,
            'from': from_date.isoformat() if isinstance(from_date, datetime) else from_date,
            'to': to_date.isoformat() if isinstance(to_date, datetime) else to_date,
        }
        result = self._make_api_request('order/pull-orders', method='GET', params=params)
        return self._normalize_api_response(result)

    def update_single_order_status(self, order_record, new_status):
        if not order_record.cartona_id:
            return {'success': False, 'error': 'Missing cartona_id'}
        endpoint = f'order/update-order-status/{order_record.cartona_id}'
        status_data = {'status': new_status, 'hashed_id': order_record.cartona_id}
        if new_status == 'delivered' and order_record.cartona_payment_method in (
            'installment', 'wallet_top_up',
        ):
            status_data['retailer_otp'] = order_record.cartona_delivery_otp or None
        if new_status == 'cancelled_by_supplier':
            status_data['cancellation_reason'] = 'supplier_asked_me_to_cancel'
        result = self._make_api_request(endpoint, method='POST', data=status_data)
        return self._normalize_api_response(result)

    def ack_order_synced(self, order_record):
        """Notify Cartona that an inbound order was successfully processed (fire-and-forget)."""
        if not order_record.cartona_id:
            return
        if not self._sync_active():
            return

        config = self._get_cartona_config()
        cartona_id = order_record.cartona_id
        endpoint = f'order/update-order-status/{cartona_id}'
        url = f"{config.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = config.get_api_headers()
        payload = {'status': 'synced', 'hashed_id': cartona_id}
        timeout = config.timeout
        db_name = self.env.cr.dbname
        uid = self.env.uid
        context = dict(
            self.env.context,
            cartona_config_id=config.id,
            cartona_sync_log_internal=True,
        )
        action_type = self.env.context.get('cartona_log_action_type', 'automated')
        order_id = order_record.id
        order_name = order_record.display_name
        request_data = self._serialize_for_log({
            'endpoint': endpoint,
            'method': 'POST',
            'payload': payload,
        })

        def _post_ack():
            response_status = None
            response_body = None
            log_status = 'error'
            message = _('Inbound synced ack failed for order %s') % cartona_id
            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=timeout,
                )
                response_status = response.status_code
                try:
                    response_body = response.json()
                except json.JSONDecodeError:
                    response_body = response.text
                if response_status in (200, 201, 204):
                    log_status = 'success'
                    message = _('Inbound synced ack sent for order %s') % cartona_id
                else:
                    log_status = 'warning'
                    message = _(
                        'Inbound synced ack returned HTTP %(status)s for order %(order)s'
                    ) % {'status': response_status, 'order': cartona_id}
                    _logger.warning(
                        'Cartona synced ack HTTP %s for order %s: %s',
                        response_status, cartona_id, response_body,
                    )
            except Exception as err:
                response_body = str(err)
                message = _('Inbound synced ack failed for order %s: %s') % (cartona_id, err)
                _logger.warning(
                    'Cartona synced ack failed for order %s: %s',
                    cartona_id, err,
                )
            try:
                with Registry(db_name).cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    env['cartona.sync.log'].log_operation(
                        cartona_config_id=config.id,
                        operation_type='status_sync',
                        status=log_status,
                        message=message,
                        record_model='sale.order',
                        record_id=order_id,
                        record_name=order_name,
                        action_type=action_type,
                        request_data=request_data,
                        response_data=env['cartona.api']._serialize_for_log({
                            'status_code': response_status,
                            'body': response_body,
                        }),
                    )
                    cr.commit()
            except Exception as err:
                _logger.error(
                    'Failed to log Cartona synced ack for order %s: %s',
                    cartona_id, err,
                )

        threading.Thread(target=_post_ack, daemon=True).start()

    def update_order_details(self, order_record, order_details_list):
        if not order_record.cartona_id:
            return {'success': False, 'error': 'Missing cartona_id'}
        payload = [{
            'hashed_id': order_record.cartona_id,
            'order_details': order_details_list,
        }]
        result = self._make_api_request(
            'order/update-order-details', method='POST', data=payload,
        )
        return self._normalize_api_response(result)

    def pull_and_process_orders(self, since_date=None):
        import time
        start = time.time()
        config = self._get_cartona_config()
        action_type = self.env.context.get('cartona_log_action_type', 'automated')
        if not config.is_cartona_sync_enabled:
            return {'success': False, 'message': 'Cartona sync disabled', 'orders_pulled': 0}

        to_date = datetime.now()
        from_date = since_date or (to_date - timedelta(hours=24))
        result = self.pull_orders(from_date=from_date, to_date=to_date)
        if not result.get('success'):
            error_msg = result.get('error', 'Pull failed')
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=config.id,
                operation_type='order_pull',
                status='error',
                message=f'Order pull failed: {error_msg}',
                records_error=1,
                error_details=error_msg,
                duration=time.time() - start,
                action_type=action_type,
            )
            return {
                'success': False,
                'message': error_msg,
                'orders_pulled': 0,
            }

        orders_data = result.get('data', [])
        if not orders_data:
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=config.id,
                operation_type='order_pull',
                status='info',
                message='No orders found in date range',
                duration=time.time() - start,
                action_type=action_type,
            )
            return {
                'success': True,
                'message': 'No orders in date range',
                'orders_pulled': 0,
                'orders_new': 0,
                'orders_updated': 0,
            }

        processor = self.env['cartona.order.processor'].with_company(config.company_id)
        orders_processed = orders_new = orders_updated = orders_skipped = 0
        errors = []
        detail_lines = []
        for order_data in orders_data:
            try:
                proc_result = processor.with_context(
                    cartona_config_id=config.id,
                ).process_cartona_order(order_data)
                detail_lines.extend(proc_result.get('issues', []))
                if proc_result.get('success'):
                    orders_processed += 1
                    if proc_result.get('is_new'):
                        orders_new += 1
                    elif proc_result.get('updated'):
                        orders_updated += 1
                else:
                    orders_skipped += 1
            except Exception as err:
                errors.append(str(err))
                detail_lines.append({
                    'status': 'error',
                    'entry_type': 'system',
                    'message': str(err),
                    'error_code': 'unexpected_error',
                })
                _logger.error('Order processing error: %s', err)

        config._update_sync_stats()
        config._refresh_dashboard_issues_if_stale(force=True)
        config.write({'last_order_pull': fields.Datetime.now()})

        total_errors = len(errors) + orders_skipped
        if total_errors and not orders_processed:
            status = 'error'
        elif total_errors:
            status = 'warning'
        else:
            status = 'success'

        self.env['cartona.sync.log'].log_operation(
            cartona_config_id=config.id,
            operation_type='order_pull',
            status=status,
            message=(
                f'Pulled {len(orders_data)} orders: '
                f'{orders_processed} processed ({orders_new} new, {orders_updated} updated)'
                + (f', {orders_skipped} skipped' if orders_skipped else '')
                + (f', {len(errors)} errors' if errors else '')
            ),
            records_processed=len(orders_data),
            records_success=orders_new + orders_updated,
            records_error=total_errors,
            error_details='\n'.join(
                issue['message']
                for issue in detail_lines
                if issue.get('status') in ('error', 'warning')
            ) or None,
            duration=time.time() - start,
            action_type=action_type,
            line_vals_list=detail_lines,
        )
        return {
            'success': True,
            'message': f'Processed {orders_processed} orders',
            'orders_pulled': len(orders_data),
            'orders_new': orders_new,
            'orders_updated': orders_updated,
            'orders_skipped': orders_skipped,
            'errors': errors,
        }

    @api.model
    def cron_pull_orders(self):
        for config in self.env['cartona.config'].search([('is_cartona_sync_enabled', '=', True)]):
            try:
                self.with_company(config.company_id).with_context(
                    cartona_config_id=config.id,
                ).pull_and_process_orders()
            except Exception as err:
                _logger.error('Cron order pull failed for company %s: %s', config.company_id.name, err)

    @api.model
    def cron_retry_product_sync(self):
        for config in self.env['cartona.config'].search([('is_cartona_sync_enabled', '=', True)]):
            try:
                self.with_company(config.company_id).with_context(
                    cartona_config_id=config.id,
                ).retry_failed_variants()
            except Exception as err:
                _logger.error('Cron product retry failed for company %s: %s', config.company_id.name, err)

    def _collect_variants_for_retry(self, config, limit=100):
        sync_model = self.env['cartona.product.sync']
        sync_recs = sync_model.search([
            ('cartona_config_id', '=', config.id),
            ('sync_status', 'in', ['not_synced', 'error']),
        ], limit=limit)
        variants = sync_recs.mapped('product_id')
        remaining = max(0, limit - len(variants))
        if remaining:
            synced_product_ids = sync_model.search([
                ('cartona_config_id', '=', config.id),
            ]).mapped('product_id').ids
            extra_products = self.env['product.product'].with_company(config.company_id).search([
                ('sale_ok', '=', True),
                ('company_id', 'in', [False, config.company_id.id]),
                ('id', 'not in', synced_product_ids),
            ], limit=remaining)
            if extra_products:
                for product in extra_products:
                    sync_model.get_for_product_config(product, config)
                variants |= extra_products
        return variants, sync_model

    def _sync_variants_in_batches(
        self,
        config,
        variants,
        *,
        success_message,
        failure_message,
        summary_message,
    ):
        import time

        sync_model = self.env['cartona.product.sync']
        if not variants:
            return
        for product in variants:
            sync_model.get_for_product_config(product, config)
        success_count = error_count = 0
        last_error = None
        detail_lines = []
        batch_start = time.time()
        result = {}
        company = config.company_id
        variants = variants.with_company(company)
        for i in range(0, len(variants), config.batch_size):
            batch = variants[i:i + config.batch_size]
            batch_sync_recs = sync_model.search([
                ('cartona_config_id', '=', config.id),
                ('product_id', 'in', batch.ids),
            ])
            batch_sync_recs.mark_syncing()
            result = self.bulk_update_products(batch, sync_fields='both')
            batch_payloads = [
                self._build_variant_payload(variant, 'both', company=company)
                for variant in batch
            ]
            if result.get('success'):
                success_count += len(batch)
                batch_sync_recs.mark_success()
                for variant, payload in zip(batch, batch_payloads):
                    detail_lines.append({
                        'status': 'success',
                        'entry_type': 'product',
                        'internal_product_id': str(variant.id),
                        'record_model': 'product.product',
                        'record_id': variant.id,
                        'record_name': variant.display_name,
                        'message': success_message(variant),
                        'request_data': json.dumps({
                            'endpoint': 'supplier-product/bulk-update',
                            'method': 'POST',
                            'sync_fields': 'both',
                            'payload': payload,
                        }, indent=2, ensure_ascii=False, default=str),
                        'response_data': result.get('response_data'),
                    })
            else:
                error_count += len(batch)
                last_error = result.get('error', 'Unknown error')
                batch_sync_recs.mark_error(last_error)
                for variant, payload in zip(batch, batch_payloads):
                    detail_lines.append({
                        'status': 'error',
                        'entry_type': 'product',
                        'internal_product_id': str(variant.id),
                        'record_model': 'product.product',
                        'record_id': variant.id,
                        'record_name': variant.display_name,
                        'message': failure_message(variant),
                        'request_data': json.dumps({
                            'endpoint': 'supplier-product/bulk-update',
                            'method': 'POST',
                            'sync_fields': 'both',
                            'payload': payload,
                        }, indent=2, ensure_ascii=False, default=str),
                        'response_data': result.get('response_data'),
                    })
        self.env['cartona.sync.log'].log_operation(
            cartona_config_id=config.id,
            operation_type='product_sync',
            status='success' if not error_count else ('warning' if success_count else 'error'),
            message=summary_message.format(
                success=success_count,
                error=error_count,
                total=len(variants),
            ),
            records_processed=len(variants),
            records_success=success_count,
            records_error=error_count,
            error_details=last_error,
            request_data=result.get('request_data') if variants else None,
            response_data=result.get('response_data') if variants else None,
            duration=time.time() - batch_start,
            line_vals_list=detail_lines,
            action_type=self.env.context.get('cartona_log_action_type', 'automated'),
        )
        config._update_sync_stats()
        config._refresh_dashboard_issues_if_stale(force=True)

    def retry_failed_variants(self, limit=100):
        config = self._get_cartona_config()
        if not config.is_cartona_sync_enabled:
            return
        variants, _sync_model = self._collect_variants_for_retry(config, limit=limit)
        if not variants:
            return
        self._sync_variants_in_batches(
            config,
            variants,
            success_message=lambda variant: _(
                'Synced variant %s (retry batch)',
            ) % variant.display_name,
            failure_message=lambda variant: _(
                'Failed to sync variant %s (retry batch)',
            ) % variant.display_name,
            summary_message='Retry sync finished: {success} succeeded, {error} failed ({total} total)',
        )

    def sync_all_variants(self):
        config = self._get_cartona_config()
        if not config.is_cartona_sync_enabled:
            return
        company = config.company_id
        variants = self.env['product.product'].with_company(company).search([
            ('sale_ok', '=', True),
            ('company_id', 'in', [False, company.id]),
        ])
        if not variants:
            return
        self._sync_variants_in_batches(
            config,
            variants,
            success_message=lambda variant: _(
                'Synced variant %s (bulk manual)',
            ) % variant.display_name,
            failure_message=lambda variant: _(
                'Failed to sync variant %s (bulk manual)',
            ) % variant.display_name,
            summary_message=(
                'Bulk variant sync finished: {success} succeeded, '
                '{error} failed ({total} total)'
            ),
        )
