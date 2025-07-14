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
        """Create new sales order from marketplace data"""
        
        try:
            # Find or create customer
            customer = self._find_or_create_customer(order_data['customer_data'], config)
            
            if not customer:
                _logger.error("Failed to create/find customer")
                return None
                
            # Map marketplace status to Odoo state
            marketplace_status = order_data.get('status', 'pending')
            odoo_state = self._map_marketplace_state_to_odoo(marketplace_status, config)
                
            # Create order
            order_vals = {
                'partner_id': customer.id,
                'cartona_id': order_data['order_id'],
                'marketplace_config_id': config.id,
                'is_marketplace_order': True,
                'marketplace_order_number': order_data.get('marketplace_order_number'),
                'marketplace_status': marketplace_status,
                'marketplace_notes': order_data.get('notes'),
                'delivered_by': order_data.get('delivered_by', 'delivered_by_supplier'),
                'marketplace_payment_method': order_data.get('payment_method', 'standard'),
                'state': odoo_state,
                'origin': f"Marketplace Order {order_data['order_id']}",
            }
            
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
            # Map marketplace status to Odoo state
            marketplace_status = order_data.get('status', 'pending')
            odoo_state = self._map_marketplace_state_to_odoo(marketplace_status, config)
            
            # Update order status and marketplace info
            update_vals = {
                'marketplace_status': marketplace_status,
                'marketplace_sync_date': fields.Datetime.now(),
                'marketplace_sync_status': 'synced',
                'state': odoo_state,  # Update Odoo state based on marketplace status
            }
            
            # Update notes if provided
            if order_data.get('notes'):
                update_vals['marketplace_notes'] = order_data['notes']
                
            order.with_context(skip_marketplace_sync=True).write(update_vals)
            
            _logger.info(f"Updated existing order {order.name} - Status: {marketplace_status} -> {odoo_state}")
            return True
            
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
