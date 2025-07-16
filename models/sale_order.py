from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Universal External Order ID
    cartona_id = fields.Char(
        string="External Order ID",
        help="External order identifier from marketplace (e.g., Cartona, Amazon, eBay)",
        index=True,
        copy=False
    )
    
    # Marketplace information
    marketplace_config_id = fields.Many2one(
        'marketplace.config',
        string="Source Marketplace",
        help="The marketplace where this order originated"
    )
    
    # Order sync status
    marketplace_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
    ], string="Order Sync Status", default='not_synced')
    
    marketplace_sync_date = fields.Datetime(string="Last Order Sync", readonly=True)
    marketplace_error_message = fields.Text(string="Order Sync Error", readonly=True)
    
    # Marketplace-specific fields
    is_marketplace_order = fields.Boolean(
        string="Marketplace Order",
        help="This order was imported from a marketplace"
    )
    
    marketplace_order_number = fields.Char(
        string="Marketplace Order Number",
        help="Original order number from the marketplace"
    )
    
    marketplace_status = fields.Char(
        string="Marketplace Status",
        help="Current status in the marketplace system"
    )
    
    marketplace_payment_method = fields.Char(
        string="Payment Method",
        help="Payment method used in marketplace"
    )
    
    marketplace_notes = fields.Text(
        string="Marketplace Notes",
        help="Additional notes from marketplace order"
    )
    
    # Delivery control field for business logic
    delivered_by = fields.Selection([
        ('delivered_by_supplier', 'Delivered by Supplier'),
        ('delivered_by_cartona', 'Delivered by Cartona')
    ], string='Delivered By', default='delivered_by_supplier',
        help="Controls who handles delivery and sync permissions")


    def write(self, vals):
        """
        Override write to sync status changes to marketplace.
        
        This method automatically triggers marketplace sync when order status changes,
        ensuring Odoo state changes are reflected in Cartona marketplace.
        
        Args:
            vals (dict): Values being written to the order
            
        Returns:
            bool: Result of parent write method
        """
        result = super().write(vals)
        
        # Check if order status changed and needs marketplace sync
        status_fields = ['state', 'delivery_status']
        if any(field in vals for field in status_fields):
            if not self.env.context.get('skip_marketplace_sync'):
                # Apply business logic filtering before sync
                orders_to_sync = self.filtered('is_marketplace_order')._filter_orders_for_sync()
                if orders_to_sync:
                    orders_to_sync._trigger_status_sync()
                
        return result

    def _filter_orders_for_sync(self):
        """
        Filter orders based on business rules for syncing.
        
        Business Rules:
        - Orders delivered by Cartona: Only sync cancellation status
        - Orders delivered by Supplier: Sync all status changes
        
        Returns:
            sale.order: Filtered recordset of orders allowed to sync
        """
        allowed_orders = self.env['sale.order']
        
        for order in self:
            if not order.cartona_id or not order.marketplace_config_id:
                continue
                
            # Apply business rules based on delivered_by field
            if order.delivered_by == 'delivered_by_cartona':
                # Can only sync cancellation status to Cartona
                if order.state == 'cancel':
                    allowed_orders |= order
                else:
                    _logger.info(f"Skipping sync for order {order.name}: delivered_by_cartona allows only cancel status")
            elif order.delivered_by == 'delivered_by_supplier':
                # Can sync any status change to Cartona
                allowed_orders |= order
            else:
                _logger.warning(f"Unknown delivered_by value for order {order.name}: {order.delivered_by}")
                
        return allowed_orders

    def _trigger_status_sync(self):
        """
        Trigger order status sync to marketplace using queue jobs.
        
        This method queues async jobs to sync order status changes back to Cartona,
        ensuring the marketplace is kept up-to-date with Odoo changes.
        """
        for order in self:
            if order.cartona_id and order.marketplace_config_id:
                # Queue job for async status sync
                order.with_delay(
                    channel='marketplace',
                    description=f"Sync order status {order.name} to {order.marketplace_config_id.name}"
                )._sync_status_to_marketplace()

    def _sync_status_to_marketplace(self):
        """
        Sync order status to marketplace via API.
        
        This method:
        1. Maps Odoo status to marketplace status
        2. Calls marketplace API to update status
        3. Updates sync status and error handling
        """
        self.ensure_one()
        
        if not self.cartona_id or not self.marketplace_config_id:
            return
            
        try:
            # Update sync status to 'syncing'
            self.write({
                'marketplace_sync_status': 'syncing',
            })
            
            # Get API client for this marketplace
            api_client = self.env['marketplace.api'].with_context(
                marketplace_config_id=self.marketplace_config_id.id
            )
            
            # Map Odoo status to marketplace status
            marketplace_status = self._map_odoo_status_to_marketplace()
            
            if not marketplace_status:
                error_msg = f"No marketplace status mapping found for Odoo state: {self.state}"
                self.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': error_msg
                })
                _logger.error(error_msg)
                return
            
            # Sync status to marketplace using single order endpoint
            result = api_client.update_single_order_status(self, marketplace_status)
            
            # Ensure result is a dictionary (extra safety check)
            if not isinstance(result, dict):
                error_msg = f"API returned unexpected response type: {type(result)}. Response: {result}"
                self.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': error_msg
                })
                _logger.error(f"Unexpected API response for order {self.name}: {error_msg}")
                return
            
            if result.get('success'):
                # Log additional info if available
                additional_info = f" - API Response: {result.get('message', 'No additional message')}"
                if result.get('data'):
                    additional_info += f" - Data: {len(result['data'])} items processed"
                
                self.write({
                    'marketplace_sync_status': 'synced',
                    'marketplace_sync_date': fields.Datetime.now(),
                    'marketplace_error_message': False,
                    'marketplace_status': marketplace_status
                })
                _logger.info(f"Successfully synced order {self.name} status to {self.marketplace_config_id.name} with status: {marketplace_status}{additional_info}")
            else:
                error_msg = result.get('error', 'Unknown error')
                error_details = result.get('error_details', '')
                full_error = f"{error_msg}"
                if error_details:
                    full_error += f" - Details: {error_details}"
                
                self.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': full_error
                })
                _logger.error(f"Failed to sync order {self.name} status: {full_error}")
                
        except Exception as e:
            error_msg = f"Status sync error: {str(e)}"
            self.write({
                'marketplace_sync_status': 'error',
                'marketplace_error_message': error_msg
            })
            _logger.error(f"Error syncing order {self.name} status: {e}")

    def _map_odoo_status_to_marketplace(self):
        """
        Map Odoo order status to Cartona marketplace status.
        
        Status Mapping:
        - draft/sent → pending (order created, pending approval)
        - sale → approved (sales order confirmed)
        - done → delivered (order completed/delivered)
        - cancel → cancelled_by_supplier (order cancelled)
        
        Returns:
            str: Mapped marketplace status or None
        """
        # Enhanced mapping based on Cartona API documentation
        status_mapping = {
            'draft': 'pending',           # Order created, pending approval
            'sent': 'pending',            # Quotation sent, still pending
            'sale': 'approved',           # Sales order confirmed
            'done': 'delivered',          # Order completed/delivered
            'cancel': 'cancelled_by_supplier',  # Order cancelled
        }
        
        return status_mapping.get(self.state)

    def _get_delivery_state(self):
        """
        Get the primary delivery state for enhanced status mapping.
        
        This method analyzes all outgoing deliveries and returns the most
        advanced state based on priority: done > assigned > confirmed > waiting > draft
        
        Returns:
            str: Primary delivery state
        """
        # Get outgoing deliveries (shipments)
        outgoing_pickings = self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state != 'cancel'
        )
        
        if not outgoing_pickings:
            return 'draft'
        
        # Priority order: done > assigned > confirmed > waiting > draft
        state_priority = ['done', 'assigned', 'confirmed', 'waiting', 'draft']
        for state in state_priority:
            if any(p.state == state for p in outgoing_pickings):
                return state
        
        return 'draft'

    def _map_combined_status_to_marketplace(self):
        """
        Enhanced mapping considering both order and delivery states.
        
        This provides more granular status mapping by considering:
        - Order state (draft, sale, done, cancel)
        - Delivery state (draft, confirmed, assigned, done)
        
        Returns:
            str: Enhanced marketplace status
        """
        order_state = self.state
        delivery_state = self._get_delivery_state()
        
        # Enhanced mapping logic
        if order_state == 'cancel':
            return 'cancelled_by_supplier'
        elif order_state == 'draft' or order_state == 'sent':
            return 'pending'
        elif order_state == 'sale':
            if delivery_state == 'done':
                return 'assigned_to_salesman'  # Shipped
            else:
                return 'approved'  # Confirmed but not shipped
        elif order_state == 'done':
            return 'delivered'  # Fully completed
        
        return 'pending'  # Fallback

    def action_manual_sync_to_marketplace(self):
        """Manual sync order to marketplace"""
        self.ensure_one()
        
        if not self.cartona_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Not Available"),
                    'message': _("Order sync requires External Order ID"),
                    'type': 'warning',
                }
            }
        
        # Check business rules before manual sync
        if self.delivered_by == 'delivered_by_cartona' and self.state != 'cancel':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Not Allowed"),
                    'message': _("Orders delivered by Cartona can only sync cancellation status"),
                    'type': 'warning',
                }
            }
        
        self._trigger_status_sync()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sync Started"),
                'message': _("Order sync started for: %s") % self.name,
                'type': 'info',
            }
        }

    def action_sync_enhanced_status(self):
        """Manual sync with enhanced status mapping"""
        self.ensure_one()
        
        if not self.cartona_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Not Available"),
                    'message': _("Order sync requires External Order ID"),
                    'type': 'warning',
                }
            }
        
        # Use enhanced mapping for manual sync
        try:
            api_client = self.env['marketplace.api'].with_context(
                marketplace_config_id=self.marketplace_config_id.id
            )
            
            marketplace_status = self._map_combined_status_to_marketplace()
            result = api_client.update_single_order_status(self, marketplace_status)
            
            if result.get('success'):
                message = f"Successfully synced order status: {marketplace_status}"
                notification_type = 'success'
            else:
                message = f"Sync failed: {result.get('error', 'Unknown error')}"
                notification_type = 'danger'
                
        except Exception as e:
            message = f"Sync error: {str(e)}"
            notification_type = 'danger'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sync Result"),
                'message': _(message),
                'type': notification_type,
            }
        }

    def action_test_status_sync(self):
        """Test method to demonstrate status sync functionality"""
        self.ensure_one()
        
        if not self.cartona_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Test Not Available"),
                    'message': _("Test requires External Order ID"),
                    'type': 'warning',
                }
            }
        
        # Get current status mappings
        current_status = self._map_odoo_status_to_marketplace()
        enhanced_status = self._map_combined_status_to_marketplace()
        delivery_state = self._get_delivery_state()
        
        # Check business rules
        can_sync = True
        if self.delivered_by == 'delivered_by_cartona' and self.state != 'cancel':
            can_sync = False
        
        # Create detailed test report
        test_results = {
            'order_name': self.name,
            'cartona_id': self.cartona_id,
            'current_state': self.state,
            'delivery_state': delivery_state,
            'delivered_by': self.delivered_by,
            'current_mapping': current_status,
            'enhanced_mapping': enhanced_status,
            'can_sync': can_sync,
            'sync_restriction_reason': 'Cartona delivery - only cancel allowed' if not can_sync else 'No restrictions'
        }
        
        # Log test results
        _logger.info(f"Order Status Sync Test Results: {test_results}")
        
        # Show API endpoint that would be used
        endpoint_info = f"order/update-order-status/{self.cartona_id}"
        request_body = {
            'status': enhanced_status,
            'hashed_id': self.cartona_id
        }
        
        message = f"""Order Status Sync Test:
        
Order: {self.name}
Cartona ID: {self.cartona_id}
Current State: {self.state}
Delivery State: {delivery_state}
Delivery Responsibility: {self.delivered_by}

Status Mappings:
- Current: {current_status}
- Enhanced: {enhanced_status}

API Call Details:
- Endpoint: POST {endpoint_info}
- Request Body: {request_body}

Business Rules:
- Can Sync: {can_sync}
- Restriction: {test_results['sync_restriction_reason']}
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Status Sync Test Results"),
                'message': message,
                'type': 'info',
            }
        }

    @api.model
    def find_by_cartona_id(self, cartona_id):
        """Find order by external ID"""
        if not cartona_id:
            return self.env['sale.order']
            
        return self.search([('cartona_id', '=', cartona_id)], limit=1)

    def _get_delivery_address_info(self):
        """Get delivery address for marketplace sync"""
        delivery_partner = self.partner_shipping_id or self.partner_id
        
        return {
            'name': delivery_partner.name,
            'street': delivery_partner.street,
            'street2': delivery_partner.street2,
            'city': delivery_partner.city,
            'zip': delivery_partner.zip,
            'state': delivery_partner.state_id.name if delivery_partner.state_id else '',
            'country': delivery_partner.country_id.name if delivery_partner.country_id else '',
            'phone': delivery_partner.phone,
            'email': delivery_partner.email,
        }

    def action_fill_move_quantity_with_demand(self):
        """
        Fill move quantities with demand for all deliveries.
        
        This is a utility method that automatically sets quantity_done = product_uom_qty
        for all assigned move lines in outgoing deliveries. Useful for bulk processing
        when you want to fulfill the entire demand.
        
        Returns:
            dict: Action result with notification
        """
        self.ensure_one()
        
        filled_moves = 0
        # Process all outgoing deliveries
        for picking in self.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing'):
            if picking.state == 'assigned':
                # Fill quantities for all moves in this delivery
                for move in picking.move_ids:
                    if move.state == 'assigned' and move.quantity_done < move.product_uom_qty:
                        move.quantity_done = move.product_uom_qty
                        filled_moves += 1
        
        # Return appropriate notification
        if filled_moves > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Quantities Filled"),
                    'message': _("Filled %d move lines with demand quantities") % filled_moves,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("No Changes"),
                    'message': _("No move lines needed quantity adjustment"),
                    'type': 'info',
                }
            }

    def _sync_delivery_validation_to_cartona(self):
        """
        Sync delivery validation to Cartona when delivery status becomes 'done'.
        
        This method is called when a delivery is validated and becomes 'done'.
        It updates the order status in Cartona to 'assigned_to_salesman' to indicate
        that the order has been shipped/delivered.
        """
        self.ensure_one()
        
        if not self.cartona_id or not self.marketplace_config_id:
            _logger.warning(f"Cannot sync delivery validation for order {self.name}: missing cartona_id or marketplace_config_id")
            return
        
        # Check business rules - only sync if delivered by supplier
        if self.delivered_by != 'delivered_by_supplier':
            _logger.info(f"Skipping delivery validation sync for order {self.name}: delivered_by_cartona orders don't sync delivery status")
            return
        
        try:
            # Update sync status to 'syncing'
            self.write({
                'marketplace_sync_status': 'syncing',
            })
            
            # Get API client for this marketplace
            api_client = self.env['marketplace.api'].with_context(
                marketplace_config_id=self.marketplace_config_id.id
            )
            
            # Use 'assigned_to_salesman' status for delivery validation
            # This indicates the order has been shipped/delivered by the supplier
            marketplace_status = 'assigned_to_salesman'
            
            _logger.info(f"Syncing delivery validation for order {self.name} to Cartona with status: {marketplace_status}")
            
            # Sync status to marketplace using single order endpoint
            result = api_client.update_single_order_status(self, marketplace_status)
            
            # Ensure result is a dictionary (extra safety check)
            if not isinstance(result, dict):
                error_msg = f"API returned unexpected response type: {type(result)}. Response: {result}"
                self.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': error_msg
                })
                _logger.error(f"Unexpected API response for delivery validation sync of order {self.name}: {error_msg}")
                return
            
            if result.get('success'):
                # Update order with successful sync
                self.write({
                    'marketplace_sync_status': 'synced',
                    'marketplace_status': marketplace_status,
                    'marketplace_sync_date': fields.Datetime.now(),
                    'marketplace_error_message': False
                })
                
                _logger.info(f"Successfully synced delivery validation for order {self.name} to Cartona")
                
                # Log successful sync
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=self.marketplace_config_id.id,
                    operation_type='status_sync',
                    status='success',
                    message=f"Successfully synced delivery validation for order: {self.name}",
                    record_model='sale.order',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=1,
                    records_success=1
                )
            else:
                # Handle API error
                error_msg = result.get('error', 'Unknown API error')
                self.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': error_msg
                })
                
                _logger.error(f"Failed to sync delivery validation for order {self.name} to Cartona: {error_msg}")
                
                # Log failed sync
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=self.marketplace_config_id.id,
                    operation_type='status_sync',
                    status='error',
                    message=f"Failed to sync delivery validation for order: {self.name}",
                    record_model='sale.order',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=1,
                    records_error=1,
                    error_details=error_msg
                )
                
        except Exception as e:
            error_msg = f"Exception during delivery validation sync: {str(e)}"
            self.write({
                'marketplace_sync_status': 'error',
                'marketplace_error_message': error_msg
            })
            
            _logger.error(f"Exception during delivery validation sync for order {self.name}: {e}")
            
            # Log exception
            self.env['marketplace.sync.log'].log_operation(
                marketplace_config_id=self.marketplace_config_id.id,
                operation_type='status_sync',
                status='error',
                message=f"Exception during delivery validation sync for order: {self.name}",
                record_model='sale.order',
                record_id=self.id,
                record_name=self.name,
                records_processed=1,
                records_error=1,
                error_details=error_msg
            )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Link to marketplace order line
    marketplace_line_id = fields.Char(
        string="Marketplace Line ID",
        help="External line identifier from marketplace"
    )
    
    # Line-specific marketplace data
    marketplace_product_id = fields.Char(
        string="Marketplace Product ID",
        help="Product ID as specified in marketplace order"
    )
    
    marketplace_sku = fields.Char(
        string="Marketplace SKU",
        help="Product SKU as specified in marketplace order"
    )
    
    marketplace_notes = fields.Text(
        string="Line Notes",
        help="Additional notes for this order line from marketplace"
    )
