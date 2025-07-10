from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class MarketplaceWebhook(http.Controller):
    """Generic webhook controller for marketplace integrations"""

    @http.route('/marketplace_integration/webhook/orders', type='json', auth='none', 
                methods=['POST'], csrf=False, save_session=False)
    def receive_order_webhook(self, **kwargs):
        """Generic webhook endpoint to receive orders from any marketplace"""
        
        try:
            # Get request data
            if request.httprequest.content_type == 'application/json':
                data = json.loads(request.httprequest.data.decode('utf-8'))
            else:
                data = dict(request.httprequest.form)
                
            _logger.info(f"Received order webhook data: {data}")
            
            # Identify marketplace based on data structure or headers
            marketplace_config = self._identify_marketplace(data, request.httprequest.headers)
            
            if not marketplace_config:
                _logger.error("Could not identify marketplace for webhook")
                return self._error_response("Unknown marketplace", 400)
                
            # Process the order using the order processor
            order_processor = request.env['marketplace.order.processor'].sudo().with_context(
                marketplace_config_id=marketplace_config.id
            )
            
            success = order_processor.process_marketplace_order(data)
            
            if success:
                return self._success_response("Order processed successfully", order_processor.order)
            else:
                return self._error_response("Order processing failed", 500)
                
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON in webhook: {e}")
            return self._error_response("Invalid JSON format", 400)
            
        except Exception as e:
            _logger.error(f"Webhook processing error: {e}")
            return self._error_response(f"Processing error: {str(e)}", 500)

    @http.route('/marketplace_integration/webhook/status', type='http', auth='none',
                methods=['POST'], csrf=False, save_session=False)
    def receive_status_webhook(self, **kwargs):
        """Generic webhook endpoint to receive status updates from marketplaces"""
        
        try:
            # Get request data
            if request.httprequest.content_type == 'application/json':
                data = json.loads(request.httprequest.data.decode('utf-8'))
            else:
                data = dict(request.httprequest.form)
                
            _logger.info(f"Received status webhook data: {data}")
            
            # Identify marketplace
            marketplace_config = self._identify_marketplace(data, request.httprequest.headers)
            
            if not marketplace_config:
                return self._error_response("Unknown marketplace", 400)
                
            # Process status update
            success = self._process_status_update(data, marketplace_config)
            
            if success:
                return self._success_response("Status update processed")
            else:
                return self._error_response("Status update failed", 500)
                
        except Exception as e:
            _logger.error(f"Status webhook error: {e}")
            return self._error_response(f"Processing error: {str(e)}", 500)

    @http.route('/marketplace_integration/webhook/test', type='http', auth='none',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def test_webhook(self, **kwargs):
        """Test endpoint for webhook connectivity"""
        
        return self._success_response("Webhook endpoint is working")

    def _identify_marketplace(self, data, headers):
        """Identify which marketplace sent the webhook based on data structure or headers"""
        
        # Method 1: Check for marketplace identifier in data
        if 'marketplace_id' in data:
            marketplace_config = request.env['marketplace.config'].sudo().search([
                ('id', '=', data['marketplace_id']),
                ('active', '=', True)
            ], limit=1)
            if marketplace_config:
                return marketplace_config
                
        # Method 2: Check User-Agent header
        user_agent = headers.get('User-Agent', '').lower()
        if 'cartona' in user_agent:
            marketplace_config = request.env['marketplace.config'].sudo().search([
                ('name', 'ilike', 'cartona'),
                ('active', '=', True)
            ], limit=1)
            if marketplace_config:
                return marketplace_config
                
        # Method 3: Check for specific data patterns
        # Cartona pattern
        if 'order_id' in data and 'customer' in data and 'items' in data:
            marketplace_config = request.env['marketplace.config'].sudo().search([
                ('name', 'ilike', 'cartona'),
                ('active', '=', True)
            ], limit=1)
            if marketplace_config:
                return marketplace_config
                
        # Amazon pattern
        if 'AmazonOrderId' in data or 'amazon' in str(data).lower():
            marketplace_config = request.env['marketplace.config'].sudo().search([
                ('name', 'ilike', 'amazon'),
                ('active', '=', True)
            ], limit=1)
            if marketplace_config:
                return marketplace_config
                
        # Default: use first active marketplace if only one configured
        marketplaces = request.env['marketplace.config'].sudo().search([('active', '=', True)])
        if len(marketplaces) == 1:
            return marketplaces[0]
            
        return None

    def _process_status_update(self, data, marketplace_config):
        """Process status update from marketplace"""
        
        try:
            # Extract order ID and new status
            order_id = data.get('order_id') or data.get('id') or data.get('AmazonOrderId')
            new_status = data.get('status') or data.get('order_status')
            
            if not order_id or not new_status:
                _logger.error("Missing order_id or status in webhook data")
                return False
                
            # Find the order
            order = request.env['sale.order'].sudo().search([
                ('cartona_id', '=', str(order_id))
            ], limit=1)
            
            if not order:
                _logger.warning(f"Order not found for external ID: {order_id}")
                return False
                
            # Map marketplace status to Odoo status
            odoo_status = self._map_marketplace_status_to_odoo(new_status)
            
            if odoo_status:
                order.with_context(skip_marketplace_sync=True).write({
                    'state': odoo_status,
                    'marketplace_status': new_status,
                    'marketplace_sync_date': request.env['ir.fields'].Datetime.now()
                })
                
                _logger.info(f"Updated order {order.name} status to {odoo_status}")
                return True
            else:
                _logger.warning(f"Unknown marketplace status: {new_status}")
                return False
                
        except Exception as e:
            _logger.error(f"Error processing status update: {e}")
            return False

    def _map_marketplace_status_to_odoo(self, marketplace_status):
        """Map marketplace status to Odoo order status"""
        
        status_mapping = {
            # Common statuses
            'pending': 'draft',
            'confirmed': 'sale',
            'approved': 'sale',
            'processing': 'sale',
            'shipped': 'sale',
            'delivered': 'done',
            'completed': 'done',
            'cancelled': 'cancel',
            'canceled': 'cancel',
            
            # Cartona specific
            'synced': 'sale',
            
            # Amazon specific
            'Pending': 'draft',
            'Unshipped': 'sale',
            'PartiallyShipped': 'sale',
            'Shipped': 'sale',
            'Canceled': 'cancel',
        }
        
        return status_mapping.get(marketplace_status.lower(), None)

    def _success_response(self, message, order):
        return {
            'status': 'success',
            'message': message,
            'order_id': order.id,
            'order_name': order.name,
            'order_status': order.state
        }

    def _error_response(self, message, code=500):
        return {
            'status': 'error',
            'message': message,
            'code': code
        }

