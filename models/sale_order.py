from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cartona_id = fields.Char(
        string='External Order ID',
        help='Cartona order hashed_id',
        index=True,
        copy=False,
    )
    cartona_config_id = fields.Many2one(
        'cartona.config',
        string='Cartona Configuration',
    )
    cartona_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
    ], default='not_synced')
    cartona_sync_date = fields.Datetime(readonly=True)
    cartona_error_message = fields.Text(readonly=True)
    is_cartona_order = fields.Boolean(
        help='This order was imported from Cartona',
    )
    cartona_order_number = fields.Char(
        help='Original order number from Cartona',
    )
    cartona_status = fields.Char(
        help='Current status in Cartona',
    )
    cartona_payment_method = fields.Char()
    cartona_notes = fields.Text()
    delivered_by = fields.Selection([
        ('delivered_by_supplier', 'Delivered by Supplier'),
        ('delivered_by_cartona', 'Delivered by Cartona'),
    ], default='delivered_by_supplier')
    cartona_delivery_otp = fields.Char(copy=False)

    def _cartona_sync_active(self):
        self.ensure_one()
        return bool(
            self.cartona_config_id
            and self.cartona_config_id.is_cartona_sync_enabled
        )

    def write(self, vals):
        result = super().write(vals)
        if any(field in vals for field in ('state', 'delivery_status')):
            if not self.env.context.get('skip_cartona_sync'):
                orders_to_sync = self.filtered('is_cartona_order')._filter_orders_for_sync()
                orders_to_sync = orders_to_sync.filtered(lambda o: o._cartona_sync_active())
                if orders_to_sync:
                    orders_to_sync._trigger_status_sync()
        return result

    def _filter_orders_for_sync(self):
        allowed = self.env['sale.order']
        for order in self:
            if not order.cartona_id or not order.cartona_config_id:
                continue
            if order.delivered_by == 'delivered_by_cartona':
                if order.state == 'cancel':
                    allowed |= order
            elif order.delivered_by == 'delivered_by_supplier':
                allowed |= order
        return allowed

    def _trigger_status_sync(self):
        for order in self:
            if order.cartona_id and order.cartona_config_id:
                order.with_context(
                    cartona_config_id=order.cartona_config_id.id,
                ).with_delay(
                    channel='cartona',
                    description=f'Sync order status {order.name} to Cartona',
                )._sync_status_to_cartona()

    def _sync_status_to_marketplace(self):
        """Legacy queue_job method from pre-cartona rename."""
        return self._sync_status_to_cartona()

    def _sync_status_to_cartona(self):
        self.ensure_one()
        if not self._cartona_sync_active():
            return
        if not self.cartona_id or not self.cartona_config_id:
            return

        try:
            self.write({'cartona_sync_status': 'syncing'})
            api_client = self.env['cartona.api'].with_context(
                cartona_config_id=self.cartona_config_id.id,
            )
            cartona_status = self._map_odoo_status_to_cartona()
            if not cartona_status:
                self.write({
                    'cartona_sync_status': 'error',
                    'cartona_error_message': _('No status mapping for Odoo state: %s') % self.state,
                })
                return

            result = api_client.update_single_order_status(self, cartona_status)
            if not isinstance(result, dict):
                self.write({
                    'cartona_sync_status': 'error',
                    'cartona_error_message': _('Unexpected API response'),
                })
                return

            if result.get('success'):
                self.write({
                    'cartona_sync_status': 'synced',
                    'cartona_sync_date': fields.Datetime.now(),
                    'cartona_error_message': False,
                    'cartona_status': cartona_status,
                })
            else:
                self.write({
                    'cartona_sync_status': 'error',
                    'cartona_error_message': result.get('error', 'Unknown error'),
                })
        except Exception as err:
            self.write({
                'cartona_sync_status': 'error',
                'cartona_error_message': str(err),
            })

    def _map_odoo_status_to_cartona(self):
        return {
            'draft': 'pending',
            'sent': 'pending',
            'sale': 'approved',
            'cancel': 'cancelled_by_supplier',
        }.get(self.state)

    def action_manual_sync_to_cartona(self):
        self.ensure_one()
        if not self._cartona_sync_active():
            raise UserError(_('Enable Cartona sync on configuration first.'))
        if not self.cartona_id:
            raise UserError(_('Order sync requires External Order ID'))
        if self.delivered_by == 'delivered_by_cartona' and self.state != 'cancel':
            raise UserError(_('Orders delivered by Cartona can only sync cancellation status'))
        self._trigger_status_sync()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Started'),
                'message': _('Order sync started for: %s') % self.name,
                'type': 'info',
            },
        }

    def _sync_order_details_to_cartona(self):
        self.ensure_one()
        if not self._cartona_sync_active():
            return
        if not self.is_cartona_order or not self.cartona_id or not self.cartona_config_id:
            return

        try:
            self.write({'cartona_sync_status': 'syncing'})
            api_client = self.env['cartona.api'].with_context(
                cartona_config_id=self.cartona_config_id.id,
            )
            order_details = []
            for line in self.order_line:
                if line.cartona_line_id:
                    try:
                        line_id = int(line.cartona_line_id)
                    except (ValueError, TypeError):
                        continue
                    order_details.append({
                        'id': line_id,
                        'amount': line.product_uom_qty,
                        'price': line.price_unit,
                        'comment': line.cartona_line_notes or '',
                    })
                elif line.product_id:
                    order_details.append({
                        'internal_product_id': str(line.product_id.id),
                        'amount': line.product_uom_qty,
                        'price': line.price_unit,
                    })

            if not order_details:
                self.write({'cartona_sync_status': 'synced'})
                return

            result = api_client.update_order_details(self, order_details)
            if result.get('success'):
                self.write({
                    'cartona_sync_status': 'synced',
                    'cartona_sync_date': fields.Datetime.now(),
                    'cartona_error_message': False,
                })
                self.env['cartona.sync.log'].log_operation(
                    cartona_config_id=self.cartona_config_id.id,
                    operation_type='status_sync',
                    status='success',
                    message=f'Order details synced for order: {self.name}',
                    record_model='sale.order',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=len(order_details),
                    records_success=len(order_details),
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                self.write({
                    'cartona_sync_status': 'error',
                    'cartona_error_message': error_msg,
                })
                self.env['cartona.sync.log'].log_operation(
                    cartona_config_id=self.cartona_config_id.id,
                    operation_type='status_sync',
                    status='error',
                    message=f'Failed to sync order details for order: {self.name}',
                    record_model='sale.order',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=len(order_details),
                    records_error=1,
                    error_details=error_msg,
                )
        except Exception as err:
            self.write({
                'cartona_sync_status': 'error',
                'cartona_error_message': str(err),
            })
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=self.cartona_config_id.id,
                operation_type='status_sync',
                status='error',
                message=f'Exception syncing order details for order: {self.name}',
                record_model='sale.order',
                record_id=self.id,
                record_name=self.name,
                records_error=1,
                error_details=str(err),
            )

    def _sync_cancelled_line_to_cartona(self, line_id):
        self.ensure_one()
        if not self._cartona_sync_active():
            return
        if not self.cartona_id or not self.cartona_config_id:
            return
        api_client = self.env['cartona.api'].with_context(
            cartona_config_id=self.cartona_config_id.id,
        )
        api_client.update_order_details(self, [{'id': line_id, 'cancelled': True}])

    def _sync_delivery_validation_to_cartona(self):
        self.ensure_one()
        if not self._cartona_sync_active():
            return
        if not self.cartona_id or not self.cartona_config_id:
            return
        if self.delivered_by != 'delivered_by_supplier':
            return

        try:
            self.write({'cartona_sync_status': 'syncing'})
            api_client = self.env['cartona.api'].with_context(
                cartona_config_id=self.cartona_config_id.id,
            )
            result = api_client.update_single_order_status(self, 'delivered')
            if result.get('success'):
                self.write({
                    'cartona_sync_status': 'synced',
                    'cartona_status': 'delivered',
                    'cartona_sync_date': fields.Datetime.now(),
                    'cartona_error_message': False,
                })
                self.env['cartona.sync.log'].log_operation(
                    cartona_config_id=self.cartona_config_id.id,
                    operation_type='status_sync',
                    status='success',
                    message=f'Delivery validation synced for order: {self.name}',
                    record_model='sale.order',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=1,
                    records_success=1,
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                self.write({
                    'cartona_sync_status': 'error',
                    'cartona_error_message': error_msg,
                })
                self.env['cartona.sync.log'].log_operation(
                    cartona_config_id=self.cartona_config_id.id,
                    operation_type='status_sync',
                    status='error',
                    message=f'Failed delivery validation sync for order: {self.name}',
                    record_model='sale.order',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=1,
                    records_error=1,
                    error_details=error_msg,
                )
        except Exception as err:
            error_msg = str(err)
            self.write({
                'cartona_sync_status': 'error',
                'cartona_error_message': error_msg,
            })
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=self.cartona_config_id.id,
                operation_type='status_sync',
                status='error',
                message=f'Exception during delivery validation sync for order: {self.name}',
                record_model='sale.order',
                record_id=self.id,
                record_name=self.name,
                records_processed=1,
                records_error=1,
                error_details=error_msg,
            )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cartona_line_id = fields.Char(
        help='Cartona order_detail.id',
    )
    cartona_sku = fields.Char()
    cartona_line_notes = fields.Text()

    _DETAIL_SYNC_FIELDS = {'product_uom_qty', 'price_unit', 'product_id', 'cartona_line_notes'}

    def _enqueue_detail_sync(self):
        for order in self.mapped('order_id'):
            if (order.is_cartona_order
                    and order.cartona_id
                    and order.cartona_config_id
                    and order.cartona_config_id.is_cartona_sync_enabled):
                order.with_context(
                    cartona_config_id=order.cartona_config_id.id,
                ).with_delay(
                    channel='cartona',
                    description=f'Sync order details to Cartona [{order.name}]',
                )._sync_order_details_to_cartona()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('skip_cartona_sync'):
            lines._enqueue_detail_sync()
        return lines

    def write(self, vals):
        needs_sync = bool(self._DETAIL_SYNC_FIELDS & set(vals.keys()))
        result = super().write(vals)
        if needs_sync and not self.env.context.get('skip_cartona_sync'):
            self._enqueue_detail_sync()
        return result

    def unlink(self):
        to_cancel = []
        for line in self:
            if line.cartona_line_id and line.order_id.is_cartona_order:
                try:
                    to_cancel.append((line.order_id, int(line.cartona_line_id)))
                except (ValueError, TypeError):
                    pass
        result = super().unlink()
        if not self.env.context.get('skip_cartona_sync'):
            for order, line_id in to_cancel:
                if (order.cartona_id
                        and order.cartona_config_id
                        and order.cartona_config_id.is_cartona_sync_enabled):
                    order.with_context(
                        cartona_config_id=order.cartona_config_id.id,
                    ).with_delay(
                        channel='cartona',
                        description=f'Cancel line {line_id} on Cartona order [{order.name}]',
                    )._sync_cancelled_line_to_cartona(line_id)
        return result
