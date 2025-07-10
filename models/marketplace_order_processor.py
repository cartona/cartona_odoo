from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


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
            
            # Remove per-order info log here
            # self.env['marketplace.sync.log'].log_operation(
            #     marketplace_config_id=config.id,
            #     operation_type='order_pull',
            #     status='info',
            #     message=f"Starting order processing for order {order_data.get('order_id', 'unknown')}"
            # )
            
            # Extract and validate order data
            validated_order = self._validate_order_data(order_data)
            
            if not validated_order:
                _logger.error("Order validation failed")
                return False
                
            # Check if order already exists
            existing_order = self._find_existing_order(validated_order['order_id'])
            
            if existing_order:
                _logger.info(f"Order {validated_order['order_id']} already exists, updating with new data")
                success = self._update_existing_order(existing_order, validated_order, config)
                if success:
                    return {'success': True, 'is_new': False, 'order': existing_order, 'updated': True}
                else:
                    return {'success': False, 'error': 'Failed to update existing order'}
            
            # Create new order
            new_order = self._create_new_order(validated_order, config)
            
            if new_order:
                _logger.info(f"Successfully created order: {new_order.name}")
                return {'success': True, 'is_new': True, 'order': new_order, 'updated': False}
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

    def _map_cartona_status_to_odoo(self, cartona_status):
        """Map Cartona status to Odoo sale order state"""
        cartona_to_odoo_mapping = {
            'pending': 'draft',
            'approved': 'sale', 
            'delivered': 'done',
            'cancelled_by_supplier': 'cancel',
            'cancelled_by_retailer': 'cancel',
            'cancelled': 'cancel',
        }
        
        mapped_status = cartona_to_odoo_mapping.get(cartona_status, 'draft')
        _logger.info(f"Mapped Cartona status '{cartona_status}' to Odoo state '{mapped_status}'")
        return mapped_status

    def _create_new_order(self, order_data, config):
        """Create new sales order from marketplace data"""

        try:
            # Find or create customer
            customer = self._find_or_create_customer(order_data['customer_data'], config)
            
            if not customer:
                _logger.error("Failed to create/find customer")
                return None
            
            # Map the marketplace status to Odoo state
            marketplace_status = order_data.get('status', 'pending')
            mapped_odoo_state = self._map_cartona_status_to_odoo(marketplace_status)
                
            # Create order
            order_vals = {
                'partner_id': customer.id,
                'cartona_id': order_data['order_id'],
                'marketplace_config_id': config.id,
                'is_marketplace_order': True,
                'marketplace_order_number': order_data.get('marketplace_order_number'),
                'marketplace_status': marketplace_status,  # Store original Cartona status
                'marketplace_mapped_status': f"{marketplace_status} → {mapped_odoo_state}",  # Store mapping info
                'marketplace_notes': order_data.get('notes'),
                'delivered_by': order_data.get('delivered_by', 'delivered_by_supplier'),
                'marketplace_payment_method': order_data.get('payment_method', 'standard'),
                'state': mapped_odoo_state,  # Use mapped status instead of 'draft'
                'origin': f"Marketplace Order {order_data['order_id']}",
            }
            
            # Set sync status to indicate successful import
            order_vals['marketplace_sync_status'] = 'synced'
            order_vals['marketplace_sync_date'] = fields.Datetime.now()
            
            _logger.info(f"Creating order with Cartona status '{marketplace_status}' mapped to Odoo state '{mapped_odoo_state}'")
            
            order = self.env['sale.order'].create(order_vals)
            
            # Create order lines
            success = self._create_order_lines(order, order_data['order_lines'])
            
            if not success:
                _logger.error("Order line creation failed, deleting order")
                order.unlink()
                return None
                
            return order
            
        except Exception as e:
            _logger.error(f"Error creating order: {e}")
            return None

    def _update_existing_order(self, order, order_data, config):
        """Update existing order with marketplace data"""
        
        try:
            _logger.info(f"Starting comprehensive update for order {order.name}")
            
            # Update or verify customer information
            customer = self._find_or_create_customer(order_data['customer_data'], config)
            if customer and customer.id != order.partner_id.id:
                _logger.info(f"Updating customer for order {order.name} from {order.partner_id.name} to {customer.name}")
            
            # Get marketplace status and map to Odoo state
            marketplace_status = order_data.get('status')
            current_marketplace_status = order.marketplace_status
            
            # Prepare comprehensive update values
            update_vals = {
                'partner_id': customer.id if customer else order.partner_id.id,
                'marketplace_status': marketplace_status,
                'marketplace_sync_date': fields.Datetime.now(),
                'marketplace_sync_status': 'synced',
                'marketplace_order_number': order_data.get('marketplace_order_number'),
                'delivered_by': order_data.get('delivered_by', order.delivered_by),
                'marketplace_payment_method': order_data.get('payment_method', order.marketplace_payment_method),
            }
            
            # Update notes if provided
            if order_data.get('notes'):
                update_vals['marketplace_notes'] = order_data['notes']
                
            # If marketplace status changed, update Odoo state too
            if marketplace_status and marketplace_status != current_marketplace_status:
                mapped_odoo_state = self._map_cartona_status_to_odoo(marketplace_status)
                
                # Only update state if it's a valid transition
                if self._is_valid_state_transition(order.state, mapped_odoo_state):
                    if mapped_odoo_state == 'cancel':
                        # Use Odoo's proper cancellation method
                        try:
                            _logger.info(f"Attempting to cancel order {order.name} due to Cartona status '{marketplace_status}'")
                            
                            # Diagnose potential cancellation issues
                            issues = self._diagnose_cancellation_issues(order)
                            if issues:
                                _logger.warning(f"Potential cancellation issues for order {order.name}: {', '.join(issues)}")
                            
                            order.with_context(skip_marketplace_sync=True).action_cancel()
                            update_vals['marketplace_mapped_status'] = f"{marketplace_status} → {mapped_odoo_state}"
                            _logger.info(f"Successfully cancelled order {order.name}")
                        except Exception as cancel_error:
                            _logger.error(f"Failed to cancel order {order.name}: {cancel_error}")
                            
                            # Get diagnostic information for better error reporting
                            issues = self._diagnose_cancellation_issues(order)
                            diagnostic_info = f" Possible issues: {', '.join(issues)}" if issues else ""
                            
                            update_vals['marketplace_mapped_status'] = f"{marketplace_status} → {mapped_odoo_state} (cancel failed)"
                            update_vals['marketplace_error_message'] = f"Cancellation failed: {str(cancel_error)}.{diagnostic_info}"
                            update_vals['marketplace_sync_status'] = 'error'
                    else:
                        # Regular state update for non-cancellation states
                        update_vals['state'] = mapped_odoo_state
                        update_vals['marketplace_mapped_status'] = f"{marketplace_status} → {mapped_odoo_state}"
                        _logger.info(f"Updating order {order.name}: Cartona status '{marketplace_status}' mapped to Odoo state '{mapped_odoo_state}'")
                else:
                    _logger.warning(f"Skipping state update for order {order.name}: transition from '{order.state}' to '{mapped_odoo_state}' not allowed")
                    update_vals['marketplace_mapped_status'] = f"{marketplace_status} → {mapped_odoo_state} (blocked)"
            
            # Apply updates to order
            order.with_context(skip_marketplace_sync=True).write(update_vals)
            
            # Update order lines if provided
            if order_data.get('order_lines'):
                self._update_order_lines(order, order_data['order_lines'])
            
            _logger.info(f"Successfully updated existing order {order.name}")
            return True
            
        except Exception as e:
            _logger.error(f"Error updating existing order: {e}")
            return False

    def _is_valid_state_transition(self, current_state, new_state):
        """Check if state transition is valid to prevent invalid order state changes"""
        
        # Define valid state transitions
        valid_transitions = {
            'draft': ['sale', 'cancel'],
            'sent': ['sale', 'cancel'], 
            'sale': ['done', 'cancel'],
            'done': [],  # Final state - no transitions allowed
            'cancel': []  # Final state - no transitions allowed
        }
        
        # Allow transition if it's valid or if new state is the same as current
        return new_state == current_state or new_state in valid_transitions.get(current_state, [])

    def _diagnose_cancellation_issues(self, order):
        """Diagnose why an order might not be cancellable"""
        issues = []
        
        # Check if order has invoices
        if order.invoice_ids:
            posted_invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
            if posted_invoices:
                issues.append(f"Order has {len(posted_invoices)} posted invoice(s)")
        
        # Check if order has deliveries
        if order.picking_ids:
            done_pickings = order.picking_ids.filtered(lambda pick: pick.state == 'done')
            if done_pickings:
                issues.append(f"Order has {len(done_pickings)} completed delivery(ies)")
        
        # Check current state
        if order.state not in ['draft', 'sent', 'sale']:
            issues.append(f"Order is in state '{order.state}' which may not allow cancellation")
        
        # Check if order is already locked
        if hasattr(order, 'locked') and order.locked:
            issues.append("Order is locked")
        
        return issues

    def _update_order_lines(self, order, new_lines_data):
        """Update order lines for existing order"""
        
        try:
            # Get current marketplace line IDs
            existing_lines = {line.marketplace_line_id: line for line in order.order_line if line.marketplace_line_id}
            
            # Track which lines were updated/added
            updated_lines = set()
            
            for line_data in new_lines_data:
                marketplace_line_id = line_data.get('marketplace_line_id')
                
                if marketplace_line_id and marketplace_line_id in existing_lines:
                    # Update existing line
                    existing_line = existing_lines[marketplace_line_id]
                    self._update_order_line(existing_line, line_data)
                    updated_lines.add(marketplace_line_id)
                    _logger.info(f"Updated existing order line {marketplace_line_id} for order {order.name}")
                else:
                    # Add new line
                    self._create_single_order_line(order, line_data)
                    _logger.info(f"Added new order line for product {line_data.get('product_id')} to order {order.name}")
            
            # Optionally remove lines that are no longer in the marketplace order
            # (commented out to be conservative - you may want to enable this)
            # for line_id, line in existing_lines.items():
            #     if line_id not in updated_lines:
            #         _logger.info(f"Removing order line {line_id} from order {order.name} - no longer in marketplace")
            #         line.unlink()
                        
        except Exception as e:
            _logger.error(f"Error updating order lines for order {order.name}: {e}")

    def _update_order_line(self, order_line, line_data):
        """Update existing order line with new data"""
        
        try:
            # Find or create product
            product = self._find_or_create_product(line_data)
            
            if not product:
                _logger.warning(f"Could not find/create product for {line_data['product_id']}. Skipping line update.")
                return
            
            # Update line values
            line_vals = {
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': line_data['quantity'],
                'price_unit': line_data['unit_price'],
                'marketplace_product_id': line_data.get('product_id'),
                'marketplace_sku': line_data.get('sku'),
                'marketplace_notes': line_data.get('comment'),
            }
            
            order_line.write(line_vals)
            
        except Exception as e:
            _logger.error(f"Error updating order line {order_line.marketplace_line_id}: {e}")

    def _create_single_order_line(self, order, line_data):
        """Create a single order line"""
        
        try:
            # Find or create product
            product = self._find_or_create_product(line_data)
            
            if not product:
                _logger.warning(f"Could not find/create product for {line_data['product_id']}. Skipping line.")
                return None
            
            # Create order line
            line_vals = {
                'order_id': order.id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': line_data['quantity'],
                'price_unit': line_data['unit_price'],
                'marketplace_line_id': line_data.get('marketplace_line_id'),
                'marketplace_product_id': line_data.get('product_id'),
                'marketplace_sku': line_data.get('sku'),
                'marketplace_notes': line_data.get('comment'),
            }
            
            return self.env['sale.order.line'].create(line_vals)
            
        except Exception as e:
            _logger.error(f"Error creating order line for item {line_data.get('product_id', 'unknown')}: {e}")
            return None

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
                
                line = self.env['sale.order.line'].create(line_vals)
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

    def _log_error(self, config, message, order_data=None, error_details=None):
        """Log error for order processing"""
        
        self.env['marketplace.sync.log'].log_operation(
            marketplace_config_id=config.id,
            operation_type='order_pull',
            status='error',
            message=message,
            error_details=error_details,
            request_data=str(order_data) if order_data else None,
            records_processed=1,
            records_error=1
        )

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
