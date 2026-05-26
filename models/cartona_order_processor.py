from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

_CANCEL_STATUSES = frozenset(['cancelled', 'cancelled_by_retailer', 'cancelled_by_supplier'])


class CartonaOrderProcessor(models.Model):
    _name = 'cartona.order.processor'
    _description = 'Cartona Order Processor'

    def _get_cartona_config(self):
        config_id = self.env.context.get('cartona_config_id')
        if not config_id:
            raise UserError(_('No Cartona configuration specified'))
        config = self.env['cartona.config'].browse(config_id)
        if not config.exists():
            raise UserError(_('Invalid Cartona configuration'))
        return config

    def _order_identifiers(self, order_data):
        if isinstance(order_data, list):
            order_data = order_data[0] if order_data else {}
        if not isinstance(order_data, dict):
            return {}
        order_id = order_data.get('hashed_id')
        order_number = order_data.get('receipt_id') or order_id
        return {
            'cartona_order_id': order_id,
            'cartona_order_number': order_number,
        }

    def _line_identifiers(self, item_data):
        line_id = item_data.get('id') or item_data.get('cartona_line_id')
        internal_product_id = item_data.get('internal_product_id')
        return {
            'cartona_line_id': str(line_id) if line_id is not None else False,
            'internal_product_id': str(internal_product_id) if internal_product_id is not None else False,
        }

    def _make_issue(self, status, entry_type, message, order_data=None, item_data=None,
                    error_code=None, record=None):
        issue = {
            'status': status,
            'entry_type': entry_type,
            'message': message,
        }
        if error_code:
            issue['error_code'] = error_code
        if order_data is not None:
            issue.update(self._order_identifiers(order_data))
        if item_data is not None:
            issue.update(self._line_identifiers(item_data))
        if record:
            issue.update({
                'record_model': record._name,
                'record_id': record.id,
                'record_name': record.display_name,
            })
        return issue

    def _make_result(self, success, order_data=None, issues=None, **kwargs):
        result = {
            'success': success,
            'is_new': kwargs.get('is_new', False),
            'updated': kwargs.get('updated', False),
            'order': kwargs.get('order'),
            'issues': issues or [],
        }
        if order_data is not None:
            result.update(self._order_identifiers(order_data))
        return result

    def _can_ack_order(self, order, issues):
        if not order or not order.cartona_id:
            return False
        if order.cartona_sync_status == 'error':
            return False
        if any(issue.get('status') == 'error' for issue in (issues or [])):
            return False
        return True

    def _ack_order_synced_to_cartona(self, order):
        if not order or not order.cartona_id:
            return
        config_id = order.cartona_config_id.id or self.env.context.get('cartona_config_id')
        if not config_id:
            return
        try:
            self.env['cartona.api'].with_context(
                cartona_config_id=config_id,
            ).ack_order_synced(order)
        except Exception as err:
            _logger.debug(
                'Could not send Cartona synced ack for order %s: %s',
                order.name, err,
            )

    def process_cartona_order(self, order_data):
        issues = []
        try:
            config = self._get_cartona_config()
            validated_order, validation_issues = self._validate_order_data(order_data)
            issues.extend(validation_issues)
            if not validated_order:
                return self._make_result(False, order_data=order_data, issues=issues)

            existing_order = self._find_existing_order(validated_order['order_id'], config)
            if existing_order:
                cartona_status = validated_order.get('status', 'pending')
                new_odoo_state = self._map_cartona_state_to_odoo(cartona_status, config)
                if (existing_order.state != new_odoo_state
                        or existing_order.cartona_status != cartona_status):
                    success = self._update_existing_order(
                        existing_order, validated_order, config, issues,
                    )
                    if success:
                        issues.append(self._make_issue(
                            'success', 'order',
                            _('Order %(number)s updated (%(name)s)') % {
                                'number': validated_order.get('cartona_order_number'),
                                'name': existing_order.name,
                            },
                            order_data=order_data,
                            record=existing_order,
                        ))
                        return self._ack_and_return(self._make_result(
                            True, order_data=order_data, issues=issues,
                            is_new=False, updated=True, order=existing_order,
                        ))
                    return self._make_result(
                        False, order_data=order_data, issues=issues, order=existing_order,
                    )

                issues.append(self._make_issue(
                    'info', 'order',
                    _('Order %(number)s already up to date (%(name)s)') % {
                        'number': validated_order.get('cartona_order_number'),
                        'name': existing_order.name,
                    },
                    order_data=order_data,
                    record=existing_order,
                ))
                return self._ack_and_return(self._make_result(
                    True, order_data=order_data, issues=issues,
                    is_new=False, updated=False, order=existing_order,
                ))

            new_order = self._create_new_order(validated_order, config, order_data, issues)
            if new_order:
                issues.append(self._make_issue(
                    'success', 'order',
                    _('Order %(number)s imported as %(name)s') % {
                        'number': validated_order.get('cartona_order_number'),
                        'name': new_order.name,
                    },
                    order_data=order_data,
                    record=new_order,
                ))
                return self._ack_and_return(self._make_result(
                    True, order_data=order_data, issues=issues,
                    is_new=True, order=new_order,
                ))
            return self._make_result(False, order_data=order_data, issues=issues)
        except Exception as err:
            _logger.error('Error processing order: %s', err)
            issues.append(self._make_issue(
                'error', 'order',
                _('Unexpected error processing order: %s') % err,
                order_data=order_data,
                error_code='unexpected_error',
            ))
            return self._make_result(False, order_data=order_data, issues=issues)

    def _ack_and_return(self, result):
        order = result.get('order')
        issues = result.get('issues') or []
        if result.get('success') and self._can_ack_order(order, issues):
            self._ack_order_synced_to_cartona(order)
        return result

    def _validate_order_data(self, order_data):
        issues = []
        if isinstance(order_data, list):
            if not order_data:
                issues.append(self._make_issue(
                    'error', 'order',
                    _('Empty order payload received from Cartona'),
                    error_code='invalid_order_details',
                ))
                return None, issues
            order_data = order_data[0]
        if not isinstance(order_data, dict):
            issues.append(self._make_issue(
                'error', 'order',
                _('Invalid order payload type from Cartona'),
                error_code='invalid_order_details',
            ))
            return None, issues

        order_ref = self._order_identifiers(order_data)
        order_label = order_ref.get('cartona_order_number') or order_ref.get('cartona_order_id') or '?'

        required_fields = ['hashed_id', 'retailer', 'order_details']
        missing_fields = [f for f in required_fields if f not in order_data]
        if missing_fields:
            issues.append(self._make_issue(
                'error', 'order',
                _('Order %(order)s failed validation: missing fields %(fields)s') % {
                    'order': order_label,
                    'fields': ', '.join(missing_fields),
                },
                order_data=order_data,
                error_code='missing_order_fields',
            ))
            return None, issues

        order_details = order_data.get('order_details', [])
        if not order_details or not isinstance(order_details, list):
            issues.append(self._make_issue(
                'error', 'order',
                _('Order %(order)s failed validation: invalid or missing order_details') % {
                    'order': order_label,
                },
                order_data=order_data,
                error_code='invalid_order_details',
            ))
            return None, issues

        retailer_data = order_data.get('retailer', {})
        retailer_name = (
            retailer_data.get('retailer_name')
            or retailer_data.get('name')
            or 'Cartona Customer'
        )
        retailer_code = (
            retailer_data.get('retailer_code')
            or retailer_data.get('id')
            or retailer_data.get('retailer_id')
            or str(hash(retailer_name))[:8]
        )

        delivered_by = order_data.get('delivered_by', 'delivered_by_supplier')
        if delivered_by not in ('delivered_by_supplier', 'delivered_by_cartona'):
            delivered_by = 'delivered_by_supplier'

        payment_method = 'standard'
        if order_data.get('installment_cost', 0) > 0:
            payment_method = 'installment'
        elif order_data.get('wallet_top_up', 0) > 0:
            payment_method = 'wallet_top_up'
        elif order_data.get('cartona_credit', 0) > 0:
            payment_method = 'cartona_credit'

        normalized_data = {
            'order_id': order_data['hashed_id'],
            'cartona_order_number': order_data.get('receipt_id', order_data['hashed_id']),
            'status': order_data.get('status', 'pending'),
            'total_amount': order_data.get('total_price', 0),
            'currency': 'EGP',
            'order_date': order_data.get('created_at', fields.Datetime.now()),
            'delivered_by': delivered_by,
            'payment_method': payment_method,
            'pickup_otp': order_data.get('pickup_otp'),
            'customer_data': {
                'retailer_name': retailer_name,
                'retailer_code': retailer_code,
                'retailer_number': retailer_data.get('retailer_number', ''),
                'retailer_email': retailer_data.get('retailer_email', ''),
                'retailer_address': retailer_data.get('retailer_address', ''),
                'phone': retailer_data.get('retailer_number', ''),
                'email': retailer_data.get('retailer_email', ''),
                'name': retailer_name,
                'external_id': f'retailer_{retailer_code}',
            },
            'order_lines': [],
        }

        for line_data in order_details:
            validated_line, line_issue = self._validate_order_item(line_data, order_data)
            if validated_line:
                normalized_data['order_lines'].append(validated_line)
            elif line_issue:
                issues.append(line_issue)

        if not normalized_data['order_lines']:
            if not issues:
                issues.append(self._make_issue(
                    'error', 'order',
                    _('Order %(order)s failed validation: no valid order lines') % {
                        'order': order_label,
                    },
                    order_data=order_data,
                    error_code='no_valid_order_lines',
                ))
            return None, issues
        return normalized_data, issues

    def _validate_order_item(self, item_data, order_data):
        order_ref = self._order_identifiers(order_data)
        order_label = order_ref.get('cartona_order_number') or order_ref.get('cartona_order_id') or '?'
        line_id = item_data.get('id')

        if not item_data.get('internal_product_id'):
            return None, self._make_issue(
                'error', 'order_line',
                _('Order %(order)s: order detail #%(line)s missing internal_product_id') % {
                    'order': order_label,
                    'line': line_id or '?',
                },
                order_data=order_data,
                item_data=item_data,
                error_code='missing_internal_product_id',
            )
        if 'amount' not in item_data:
            return None, self._make_issue(
                'error', 'order_line',
                _('Order %(order)s: order detail #%(line)s missing amount') % {
                    'order': order_label,
                    'line': line_id or '?',
                },
                order_data=order_data,
                item_data=item_data,
                error_code='other',
            )

        return {
            'internal_product_id': str(item_data['internal_product_id']),
            'quantity': float(item_data['amount']),
            'unit_price': float(item_data.get('selling_price', 0)),
            'total_price': float(item_data.get('selling_price', 0)) * float(item_data['amount']),
            'cartona_line_id': item_data.get('id'),
            'comment': item_data.get('comment'),
        }, None

    def _find_existing_order(self, order_id, config):
        return self.env['sale.order'].search([
            ('cartona_id', '=', order_id),
            ('cartona_config_id', '=', config.id),
        ], limit=1)

    def _map_cartona_state_to_odoo(self, cartona_status, config=None):
        if not config:
            config = self._get_cartona_config()
        state_mapping = config.get_state_mapping()
        return state_mapping.get(cartona_status, 'draft')

    def _create_new_order(self, order_data, config, raw_order_data, issues):
        order_label = order_data.get('cartona_order_number') or order_data.get('order_id')
        try:
            customer = self._find_or_create_customer(order_data['customer_data'], config)
            if not customer:
                issues.append(self._make_issue(
                    'error', 'order',
                    _('Order %(order)s failed: could not find or create customer') % {
                        'order': order_label,
                    },
                    order_data=raw_order_data,
                    error_code='customer_error',
                ))
                return None

            cartona_status = order_data.get('status', 'pending')
            order = self.env['sale.order'].with_context(skip_cartona_sync=True).create({
                'partner_id': customer.id,
                'company_id': config.company_id.id,
                'cartona_id': order_data['order_id'],
                'cartona_config_id': config.id,
                'is_cartona_order': True,
                'cartona_order_number': order_data.get('cartona_order_number'),
                'cartona_status': cartona_status,
                'cartona_notes': order_data.get('notes'),
                'delivered_by': order_data.get('delivered_by', 'delivered_by_supplier'),
                'cartona_payment_method': order_data.get('payment_method', 'standard'),
                'state': 'draft',
                'origin': f'Cartona Order {order_data["order_id"]}',
            })

            success = self._create_order_lines(
                order, order_data['order_lines'], raw_order_data, issues,
            )
            if not success:
                order.unlink()
                if not any(issue['entry_type'] == 'order_line' for issue in issues):
                    issues.append(self._make_issue(
                        'error', 'order',
                        _('Order %(order)s failed: could not create order lines') % {
                            'order': order_label,
                        },
                        order_data=raw_order_data,
                        error_code='no_valid_order_lines',
                    ))
                return None

            if not self._apply_cartona_state_action(order, cartona_status):
                issues.append(self._make_issue(
                    'error', 'order',
                    _('Order %(order)s failed to apply Cartona status %(status)s') % {
                        'order': order_label,
                        'status': cartona_status,
                    },
                    order_data=raw_order_data,
                    record=order,
                    error_code='state_transition_error',
                ))
                return None
            return order
        except Exception as err:
            _logger.error('Error creating order: %s', err)
            issues.append(self._make_issue(
                'error', 'order',
                _('Order %(order)s failed: %s') % (order_label, err),
                order_data=raw_order_data,
                error_code='unexpected_error',
            ))
            return None

    def _apply_cartona_state_action(self, order, cartona_status):
        try:
            order_ctx = order.with_context(skip_cartona_sync=True)

            if cartona_status == 'approved':
                if order.state == 'draft':
                    order_ctx.action_confirm()

            elif cartona_status == 'assigned_to_salesman':
                if order.state == 'draft':
                    order_ctx.action_confirm()
                for picking in order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                    and p.state in ('confirmed', 'waiting')
                ):
                    try:
                        picking.action_assign()
                    except Exception as err:
                        _logger.warning('Could not assign delivery %s: %s', picking.name, err)

            elif cartona_status == 'delivered':
                if order.state == 'draft':
                    order_ctx.action_confirm()
                for picking in order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                ):
                    if picking.state in ('confirmed', 'waiting'):
                        picking.action_assign()
                    if picking.state == 'assigned':
                        self._complete_delivery(picking)

            elif cartona_status in _CANCEL_STATUSES:
                if order.state not in ('cancel', 'done'):
                    done_pickings = order.picking_ids.filtered(
                        lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
                    )
                    if done_pickings:
                        order.with_context(skip_cartona_sync=True).write({
                            'cartona_sync_status': 'error',
                            'cartona_error_message': _(
                                "Cartona sent '%s' but the order has a validated delivery (%s). "
                                "Manual cancellation / return required."
                            ) % (cartona_status, ', '.join(done_pickings.mapped('name'))),
                        })
                        return False
                    order.picking_ids.filtered(
                        lambda p: p.state not in ('done', 'cancel')
                    ).action_cancel()
                    order_ctx._action_cancel()

            elif cartona_status == 'return':
                _logger.info('Order %s marked as return — manual handling required', order.name)

            return True
        except Exception as err:
            _logger.error(
                "Error applying Cartona status '%s' to order %s: %s",
                cartona_status, order.name, err,
            )
            order.with_context(skip_cartona_sync=True).write({
                'cartona_sync_status': 'error',
                'cartona_error_message': 'State transition error: %s' % err,
            })
            return False

    def _complete_delivery(self, picking):
        try:
            for move in picking.move_ids:
                if move.state in ('confirmed', 'waiting', 'assigned'):
                    move.quantity = move.product_uom_qty
            if picking.state == 'assigned':
                picking.with_context(skip_cartona_sync=True).button_validate()
        except Exception as err:
            _logger.error('Error completing delivery %s: %s', picking.name, err)

    def _update_existing_order(self, order, order_data, config, issues):
        order_label = order_data.get('cartona_order_number') or order_data.get('order_id')
        try:
            cartona_status = order_data.get('status', 'pending')
            current_status = order.cartona_status
            odoo_state_out_of_sync = (
                cartona_status in _CANCEL_STATUSES and order.state not in ('cancel', 'done')
            ) or (
                cartona_status == 'approved' and order.state == 'draft'
            )
            needs_transition = current_status != cartona_status or odoo_state_out_of_sync
            transition_ok = True
            if needs_transition:
                transition_ok = self._apply_cartona_state_action(order, cartona_status)

            if transition_ok:
                update_vals = {
                    'cartona_status': cartona_status,
                    'cartona_sync_date': fields.Datetime.now(),
                    'cartona_sync_status': 'synced',
                }
                if order_data.get('notes'):
                    update_vals['cartona_notes'] = order_data['notes']
                order.with_context(skip_cartona_sync=True).write(update_vals)
            else:
                issues.append(self._make_issue(
                    'error', 'order',
                    _('Order %(order)s failed to apply Cartona status %(status)s') % {
                        'order': order_label,
                        'status': cartona_status,
                    },
                    order_data={'hashed_id': order.cartona_id, 'receipt_id': order.cartona_order_number},
                    record=order,
                    error_code='state_transition_error',
                ))
            return transition_ok
        except Exception as err:
            _logger.error('Error updating existing order: %s', err)
            issues.append(self._make_issue(
                'error', 'order',
                _('Order %(order)s update failed: %s') % (order_label, err),
                order_data={'hashed_id': order.cartona_id, 'receipt_id': order.cartona_order_number},
                record=order,
                error_code='unexpected_error',
            ))
            return False

    def _create_order_lines(self, order, items_data, order_data, issues):
        lines_created = 0
        order_label = order.cartona_order_number or order.cartona_id
        for item_data in items_data:
            product, error_code, error_message = self._resolve_variant(
                item_data, config=order.cartona_config_id,
            )
            if not product:
                line_id = item_data.get('cartona_line_id') or '?'
                internal_product_id = item_data.get('internal_product_id')
                issues.append(self._make_issue(
                    'error', 'order_line',
                    _('Order %(order)s failed on order detail #%(line)s: %(detail)s') % {
                        'order': order_label,
                        'line': line_id,
                        'detail': error_message,
                    },
                    order_data={'hashed_id': order.cartona_id, 'receipt_id': order.cartona_order_number},
                    item_data=item_data,
                    error_code=error_code,
                ))
                _logger.error(
                    'Order line creation failed for %s: internal_product_id=%s (%s)',
                    order.name, internal_product_id, error_message,
                )
                return False

            self.env['sale.order.line'].with_context(skip_cartona_sync=True).create({
                'order_id': order.id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': item_data['quantity'],
                'price_unit': item_data['unit_price'],
                'cartona_line_id': item_data.get('cartona_line_id'),
                'cartona_line_notes': item_data.get('comment'),
            })
            lines_created += 1

        return lines_created > 0

    def _find_or_create_customer(self, customer_data, config):
        try:
            return self.env['res.partner'].with_company(
                config.company_id,
            ).find_or_create_cartona_customer(customer_data, config)
        except Exception as err:
            _logger.error('Error finding/creating customer: %s', err)
            return None

    def _resolve_variant(self, item_data, config=None):
        if not config:
            config = self._get_cartona_config()
        internal_product_id = item_data.get('internal_product_id')
        if not internal_product_id:
            return None, 'missing_internal_product_id', _(
                'missing internal_product_id on order line'
            )
        try:
            variant_id = int(internal_product_id)
        except (ValueError, TypeError):
            return None, 'invalid_internal_product_id', _(
                'internal_product_id "%(value)s" is not a valid Odoo variant id'
            ) % {'value': internal_product_id}

        variant = self.env['product.product'].browse(variant_id)
        if not variant.exists():
            return None, 'variant_not_found', _(
                'internal_product_id %(value)s does not match any Odoo variant'
            ) % {'value': internal_product_id}
        if not variant.active or not variant.sale_ok:
            return None, 'variant_not_available', _(
                'Odoo variant %(value)s exists but is inactive or not for sale'
            ) % {'value': internal_product_id}
        if variant.company_id and variant.company_id != config.company_id:
            return None, 'variant_not_available', _(
                'Odoo variant %(value)s belongs to another company'
            ) % {'value': internal_product_id}
        return variant, None, None
