from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

# Cartona statuses that map to a cancelled Odoo sale order.
_CANCEL_STATUSES = frozenset(['cancelled', 'cancelled_by_retailer', 'cancelled_by_supplier'])


class MarketplaceOrderProcessor(models.Model):
    _name = 'marketplace.order.processor'
    _description = 'Marketplace Order Processor'

    def _get_marketplace_config(self):
        """Get marketplace configuration from context"""
        config_id = self.env.context.get('marketplace_config_id')
        if not config_id:
            raise UserError(_("No marketplace configuration specified"))
            
        config = self.env['marketplace.config'].browse(config_id)
        if not config.exists():
            raise UserError(_("Invalid marketplace configuration"))
            
        return config

    def process_marketplace_order(self, order_data):
        """Process a single order from marketplace"""

        try:
            config = self._get_marketplace_config()

            # Extract and validate order data
            validated_order = self._validate_order_data(order_data)
            
            if not validated_order:
                _logger.error("Order validation failed")
                return False
                
            # Check if order already exists
            existing_order = self._find_existing_order(validated_order['order_id'])
            
            if existing_order:
                # Check if state mapping would result in a different state
                marketplace_status = validated_order.get('status', 'pending')
                new_odoo_state = self._map_marketplace_state_to_odoo(marketplace_status, config)
                
                if existing_order.state != new_odoo_state or existing_order.marketplace_status != marketplace_status:
                    _logger.info(f"Order {validated_order['order_id']} exists but state differs. Current: {existing_order.state}, New: {new_odoo_state}. Updating...")
                    success = self._update_existing_order(existing_order, validated_order, config)
                    if success:
                        return {'success': True, 'is_new': False, 'order': existing_order, 'updated': True}
                    else:
                        return False
                else:
                    _logger.info(f"Order {validated_order['order_id']} already exists with same state, skipping")
                    return {'success': True, 'is_new': False, 'order': existing_order, 'updated': False}
            
            # Create new order
            new_order = self._create_new_order(validated_order, config)
            
            if new_order:
                _logger.info(f"Successfully created order: {new_order.name}")
                return {'success': True, 'is_new': True, 'order': new_order}
            else:
                _logger.error("Failed to create new order")
                return False
                
        except Exception as e:
            _logger.error(f"Error processing order: {e}")
            return False

    def _validate_order_data(self, order_data):
        """Validate and normalize order data from marketplace"""
        
        # Handle case where order_data might be a list
        if isinstance(order_data, list):
            if len(order_data) == 0:
                return None
            # Take the first item if it's a list
            order_data = order_data[0]
            
        if not isinstance(order_data, dict):
            return None
        
        # Update required fields to match Cartona order structure
        required_fields = ['hashed_id', 'retailer', 'order_details']
        
        missing_fields = []
        for field in required_fields:
            if field not in order_data:
                missing_fields.append(field)
                
        if missing_fields:
            _logger.error(f"Missing required fields: {missing_fields}")
            return None
        
        # Validate retailer data
        retailer_data = order_data.get('retailer', {})
        required_retailer_fields = ['retailer_name']  # Only require name as minimum
        
        missing_retailer_fields = []
        for field in required_retailer_fields:
            if field not in retailer_data or not retailer_data[field]:
                missing_retailer_fields.append(field)
                
        if missing_retailer_fields:
            _logger.warning(f"Missing retailer fields: {missing_retailer_fields}, will use fallback values")
        
        # Validate order_details
        order_details = order_data.get('order_details', [])
        if not order_details or not isinstance(order_details, list):
            _logger.error("Invalid or missing order_details")
            return None
        
        # Extract retailer information with fallbacks
        retailer_name = (retailer_data.get('retailer_name') or 
                        retailer_data.get('name') or 
                        'Cartona Customer')
        
        retailer_code = (retailer_data.get('retailer_code') or 
                        retailer_data.get('id') or 
                        retailer_data.get('retailer_id') or
                        str(hash(retailer_name))[:8])  # Generate code from name
        
        # Extract delivery responsibility from Cartona order
        delivered_by = order_data.get('delivered_by', 'delivered_by_supplier')
        # Ensure it's a valid value
        if delivered_by not in ['delivered_by_supplier', 'delivered_by_cartona']:
            delivered_by = 'delivered_by_supplier'  # Default to supplier
        
        # Extract payment method information
        payment_method = 'standard'
        if order_data.get('installment_cost', 0) > 0:
            payment_method = 'installment'
        elif order_data.get('wallet_top_up', 0) > 0:
            payment_method = 'wallet_top_up'
        elif order_data.get('cartona_credit', 0) > 0:
            payment_method = 'cartona_credit'
        
        # Normalize the order data structure
        normalized_data = {
            'order_id': order_data['hashed_id'],
            'marketplace_order_number': order_data.get('receipt_id', order_data['hashed_id']),
            'status': order_data.get('status', 'pending'),
            'total_amount': order_data.get('total_price', 0),
            'currency': 'EGP',  # Default for Cartona
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
                'external_id': f"retailer_{retailer_code}",
            },
            'order_lines': []
        }
        
        # Process order lines
        for line_data in order_details:
            validated_line = self._validate_order_item(line_data)
            if validated_line:
                normalized_data['order_lines'].append(validated_line)
        
        if not normalized_data['order_lines']:
            _logger.error("No valid order lines found")
            return None
            
        return normalized_data

    def _validate_order_item(self, item_data):
        """Validate individual order item for Cartona structure"""
        
        # Updated required fields to match Cartona order_details structure
        required_item_fields = ['supplier_product_id', 'amount']  # Cartona uses 'amount' instead of 'quantity'
        
        missing_fields = []
        for field in required_item_fields:
            if field not in item_data:
                missing_fields.append(field)
                
        if missing_fields:
            _logger.error(f"Missing required item fields: {missing_fields}")
            return None
        
        validated_item = {
            'product_id': str(item_data['supplier_product_id']),
            'sku': item_data.get('supplier_product_id'),
            'product_name': item_data.get('product_name', ''),
            'quantity': float(item_data['amount']),
            'unit_price': float(item_data.get('selling_price', 0)),
            'total_price': float(item_data.get('selling_price', 0)) * float(item_data['amount']),
            'marketplace_line_id': item_data.get('id'),
            'base_product_id': item_data.get('base_product_id'),
            'internal_product_id': item_data.get('internal_product_id'),
            'unit': item_data.get('unit'),
            'unit_count': item_data.get('unit_count', 1),
            'applied_supplier_discount': item_data.get('applied_supplier_discount', 0),
            'applied_cartona_discount': item_data.get('applied_cartona_discount', 0),
            'comment': item_data.get('comment')
        }
        
        return validated_item

    def _find_existing_order(self, order_id):
        """Find existing order by external ID"""
        return self.env['sale.order'].search([
            ('cartona_id', '=', order_id)
        ], limit=1)

    def _map_marketplace_state_to_odoo(self, marketplace_status, config=None):
        """Map marketplace status to Odoo order state using configuration"""
        if not config:
            config = self._get_marketplace_config()
        
        # Get state mapping from configuration
        state_mapping = config.get_state_mapping()
        
        # Get mapped state or default to 'draft'
        odoo_state = state_mapping.get(marketplace_status, 'draft')
        
        _logger.info(f"Mapped marketplace status '{marketplace_status}' to Odoo state '{odoo_state}' using {config.name} configuration")
        return odoo_state

    def _create_new_order(self, order_data, config):
        """
        Create new sales order from marketplace data with proper state transitions.
        
        This method creates orders in draft state first, then applies the correct
        Odoo actions based on the Cartona status to ensure all business logic
        (delivery creation, inventory allocation, etc.) is properly executed.
        
        Args:
            order_data (dict): Normalized order data from Cartona
            config (marketplace.config): Marketplace configuration record
            
        Returns:
            sale.order: Created order record or None if failed
        """
        
        try:
            # Find or create customer from Cartona retailer data
            customer = self._find_or_create_customer(order_data['customer_data'], config)
            
            if not customer:
                _logger.error("Failed to create/find customer")
                return None
                
            marketplace_status = order_data.get('status', 'pending')
                
            # Always create order in draft state first - this is crucial!
            # We'll apply proper state transitions afterward using Odoo actions
            order_vals = {
                'partner_id': customer.id,
                'cartona_id': order_data['order_id'],  # External ID for sync
                'marketplace_config_id': config.id,
                'is_marketplace_order': True,
                'marketplace_order_number': order_data.get('marketplace_order_number'),
                'marketplace_status': marketplace_status,  # Store original Cartona status
                'marketplace_notes': order_data.get('notes'),
                'delivered_by': order_data.get('delivered_by', 'delivered_by_supplier'),
                'marketplace_payment_method': order_data.get('payment_method', 'standard'),
                'state': 'draft',  # Always start in draft - proper transitions come next
                'origin': f"Marketplace Order {order_data['order_id']}",
            }
            
            order = self.env['sale.order'].create(order_vals)
            
            # Create order lines from Cartona order details
            success = self._create_order_lines(order, order_data['order_lines'])
            
            if not success:
                _logger.error("Order line creation failed, deleting order")
                order.unlink()
                return None
            
            # Apply the state transition that matches the incoming Cartona status.
            # If the transition fails the order is left in draft; the next pull will
            # find it via _find_existing_order and retry via _update_existing_order.
            self._apply_cartona_state_action(order, marketplace_status)

            return order
            
        except Exception as e:
            _logger.error(f"Error creating order: {e}")
            return None

    def _apply_cartona_state_action(self, order, cartona_status):
        """
        Drive the Odoo sale order to the state implied by the Cartona status.

        Uses proper Odoo action methods rather than writing ``state`` directly so
        that all downstream business logic (delivery creation, inventory allocation,
        accounting entries, etc.) fires correctly.

        ``skip_marketplace_sync=True`` is injected into the execution context for
        every write/action so that our own ``sale.order.write`` override does not
        schedule a redundant outbound sync call.

        Returns:
            bool: ``True`` when the transition succeeded (or the order was already
                  in the correct state).  ``False`` on any error — the caller must
                  NOT persist the new ``marketplace_status`` so the next pull can
                  retry automatically.
        """
        try:
            _logger.info("Applying Cartona status '%s' to order %s", cartona_status, order.name)

            order_ctx = order.with_context(skip_marketplace_sync=True)

            if cartona_status == 'approved':
                if order.state == 'draft':
                    order_ctx.action_confirm()
                    _logger.info("Order %s confirmed — deliveries created", order.name)

            elif cartona_status == 'assigned_to_salesman':
                if order.state == 'draft':
                    order_ctx.action_confirm()
                for picking in order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing' and p.state in ['confirmed', 'waiting']
                ):
                    try:
                        picking.action_assign()
                        _logger.info("Delivery %s assigned (ready) for order %s", picking.name, order.name)
                    except Exception as e:  # non-fatal — partial assignment is acceptable
                        _logger.warning("Could not assign delivery %s: %s", picking.name, e)

            elif cartona_status == 'delivered':
                if order.state == 'draft':
                    order_ctx.action_confirm()
                for picking in order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing'):
                    if picking.state in ['confirmed', 'waiting']:
                        picking.action_assign()
                    if picking.state == 'assigned':
                        self._complete_delivery(picking)

            elif cartona_status in _CANCEL_STATUSES:
                if order.state not in ['cancel', 'done']:
                    # Guard: if at least one outgoing delivery has already been
                    # validated (done), the order has physically left the warehouse
                    # and cannot be reversed from this background job.  Log a
                    # warning, leave the Odoo order as-is, and return True so the
                    # caller records the new marketplace_status without retrying.
                    done_pickings = order.picking_ids.filtered(
                        lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
                    )
                    if done_pickings:
                        _logger.warning(
                            "Order %s received '%s' from Cartona but has validated "
                            "delivery/deliveries (%s) — Odoo cancellation skipped. "
                            "Manual review required.",
                            order.name,
                            cartona_status,
                            ', '.join(done_pickings.mapped('name')),
                        )
                        # Mark the order so it surfaces in a manual review queue.
                        order.with_context(skip_marketplace_sync=True).write({
                            'marketplace_sync_status': 'error',
                            'marketplace_error_message': _(
                                "Cartona sent '%s' but the order has a validated delivery (%s). "
                                "Manual cancellation / return required."
                            ) % (cartona_status, ', '.join(done_pickings.mapped('name'))),
                        })
                        return True

                    # Cancel any pending stock pickings first; otherwise the SO
                    # cancellation would be blocked by reserved moves.
                    order.picking_ids.filtered(
                        lambda p: p.state not in ['done', 'cancel']
                    ).action_cancel()
                    # Call _action_cancel() directly to bypass the Odoo 18
                    # cancel-confirmation wizard that action_cancel() may return
                    # instead of performing the cancellation.
                    order_ctx._action_cancel()
                    if order.state != 'cancel':
                        raise UserError(_(
                            "Could not cancel order %s (state is still '%s'). "
                            "Manual intervention required."
                        ) % (order.name, order.state))
                    _logger.info("Order %s cancelled — all deliveries cancelled", order.name)

            elif cartona_status == 'return':
                _logger.info("Order %s marked as return — manual handling required", order.name)

            return True

        except Exception as e:
            _logger.error(
                "Error applying Cartona status '%s' to order %s: %s",
                cartona_status, order.name, e,
            )
            order.with_context(skip_marketplace_sync=True).write({
                'marketplace_sync_status': 'error',
                'marketplace_error_message': "State transition error: %s" % e,
            })
            return False

    def _complete_delivery(self, picking):
        """
        Complete delivery by auto-filling quantities and validating.
        
        This method automatically:
        1. Sets quantity_done = product_uom_qty for all moves
        2. Validates the picking (completes delivery)
        3. Updates inventory accordingly
        
        Args:
            picking (stock.picking): The delivery to complete
        """
        
        try:
            # Auto-fill all move quantities with their demand quantities
            # This is equivalent to manually entering quantities in the delivery
            for move in picking.move_ids:
                if move.state in ['confirmed', 'waiting', 'assigned']:
                    move.quantity_done = move.product_uom_qty
                    
            # Validate the picking - this completes the delivery
            # Updates inventory, creates accounting entries, etc.
            if picking.state == 'assigned':
                picking.button_validate()
                _logger.info(f"Delivery {picking.name} completed (done) - inventory updated")
                
        except Exception as e:
            _logger.error(f"Error completing delivery {picking.name}: {e}")

    def _update_existing_order(self, order, order_data, config):
        """
        Update existing order with new marketplace data and handle state changes.
        
        This method:
        1. Updates marketplace-specific fields
        2. Checks if the Cartona status changed
        3. Applies proper state transitions if status changed
        
        Args:
            order (sale.order): Existing order to update
            order_data (dict): New order data from Cartona
            config (marketplace.config): Marketplace configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        
        try:
            marketplace_status = order_data.get('status', 'pending')
            current_status = order.marketplace_status

            # Decide whether to (re-)apply the state transition. We do so when:
            #   a) The incoming marketplace_status differs from what is stored — the
            #      normal case for a status update.
            #   b) The Odoo order state does not reflect the stored marketplace_status
            #      (odoo_state_out_of_sync). This handles orders where a previous pull
            #      wrote the marketplace_status before the Odoo transition succeeded,
            #      permanently preventing a retry. We detect the two most critical
            #      mismatches: a cancellation that never landed, and a confirmation
            #      that never fired.
            odoo_state_out_of_sync = (
                marketplace_status in _CANCEL_STATUSES and order.state not in ['cancel', 'done']
            ) or (
                marketplace_status == 'approved' and order.state == 'draft'
            )

            needs_transition = current_status != marketplace_status or odoo_state_out_of_sync
            transition_ok = True
            if needs_transition:
                _logger.info(
                    "Applying transition for order %s: marketplace=%s, odoo=%s, stored=%s",
                    order.name, marketplace_status, order.state, current_status,
                )
                transition_ok = self._apply_cartona_state_action(order, marketplace_status)

            if transition_ok:
                update_vals = {
                    'marketplace_status': marketplace_status,
                    'marketplace_sync_date': fields.Datetime.now(),
                    'marketplace_sync_status': 'synced',
                }
                if order_data.get('notes'):
                    update_vals['marketplace_notes'] = order_data['notes']
                order.with_context(skip_marketplace_sync=True).write(update_vals)
                _logger.info("Updated existing order %s — status: %s", order.name, marketplace_status)
            else:
                _logger.warning(
                    "State transition failed for order %s (%s → %s). "
                    "marketplace_status not updated; next pull will retry.",
                    order.name, current_status, marketplace_status,
                )

            return transition_ok

        except Exception as e:
            _logger.error(f"Error updating existing order: {e}")
            return False

    def _create_order_lines(self, order, items_data):
        """Create order lines from marketplace items"""
        
        lines_created = 0
        
        for item_data in items_data:
            try:
                # Find or create product
                product = self._find_or_create_product(item_data)
                
                if not product:
                    _logger.warning(f"Could not find/create product for {item_data['product_id']}. Skipping line.")
                    continue
                
                # Create order line
                line_vals = {
                    'order_id': order.id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_uom_qty': item_data['quantity'],
                    'price_unit': item_data['unit_price'],
                    'marketplace_line_id': item_data.get('marketplace_line_id'),
                    'marketplace_product_id': item_data.get('product_id'),
                    'marketplace_sku': item_data.get('sku'),
                    'marketplace_notes': item_data.get('comment'),
                }
                
                line = self.env['sale.order.line'].with_context(
                    skip_marketplace_sync=True
                ).create(line_vals)
                lines_created += 1
                
            except Exception as e:
                _logger.error(f"Error creating order line for item {item_data.get('product_id', 'unknown')}: {e}")
                continue
        
        if lines_created == 0:
            _logger.warning(f"No order lines were created for order {order.name}. All items failed product lookup.")
            return False
            
        return True

    def _find_or_create_customer(self, customer_data, config):
        """Find or create customer from marketplace data"""
        
        try:
            return self.env['res.partner'].find_or_create_marketplace_customer(
                customer_data, config
            )
        except Exception as e:
            _logger.error(f"Error finding/creating customer: {e}")
            return None

    def _find_or_create_product(self, item_data):
        """Find or create product from marketplace item data"""
        
        try:
            # Try to find by external ID first
            product = self.env['product.template'].find_by_cartona_id(
                item_data['product_id']
            )
            
            if product:
                return product
                
            # Try to find by SKU
            if item_data.get('sku'):
                product = self.env['product.template'].search([
                    ('default_code', '=', item_data['sku'])
                ], limit=1)
                
                if product:
                    # Update with external ID
                    product.cartona_id = item_data['product_id']
                    return product
                    
            # Create placeholder product if enabled
            product_vals = {
                'name': item_data.get('product_name', f"Marketplace Product {item_data['product_id']}"),
                'cartona_id': item_data['product_id'],
                'default_code': item_data.get('sku'),
                'list_price': item_data.get('unit_price', 0),
                'type': 'consu',  # Set product type to consumable
                'is_storable': True,  # Enable storable tracking
                'marketplace_sync_status': 'syncing',
            }
            
            product = self.env['product.template'].create(product_vals)
            return product
            
        except Exception as e:
            _logger.error(f"Error finding/creating product: {e}")
            return None

    def _extract_shipping_address(self, retailer_data):
        """Extract shipping address from Cartona retailer data"""
        if not retailer_data:
            return None
            
        address_parts = []
        if retailer_data.get('retailer_address'):
            address_parts.append(retailer_data['retailer_address'])
        if retailer_data.get('address_notes'):
            address_parts.append(retailer_data['address_notes'])
            
        return ', '.join(address_parts) if address_parts else None
