from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class MarketplaceAPI(models.Model):
    _name = 'marketplace.api'
    _description = 'Generic Marketplace API Client'

    def _get_marketplace_config(self):
        """Get marketplace configuration from context"""
        config_id = self.env.context.get('marketplace_config_id')
        if not config_id:
            raise UserError(_("No marketplace configuration specified"))
            
        config = self.env['marketplace.config'].browse(config_id)
        if not config.exists():
            raise UserError(_("Invalid marketplace configuration"))
            
        return config

    def _make_api_request(self, endpoint, method='GET', data=None, params=None):
        """Make generic API request to marketplace"""
        config = self._get_marketplace_config()
        
        # Prepare URL
        url = f"{config.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Prepare headers
        headers = config.get_api_headers()
        
        # Prepare request parameters
        request_params = {
            'url': url,
            'headers': headers,
            'timeout': config.timeout,
        }
        
        if method.upper() in ['POST', 'PUT', 'PATCH']:
            request_params['json'] = data
        else:
            request_params['params'] = params or {}
        
        # Log the request body just before sending
        if method.upper() in ['POST', 'PUT', 'PATCH']:
            _logger.info(f"[Cartona API Outgoing Request] {method} {url} BODY: {data}")
        else:
            _logger.info(f"[Cartona API Outgoing Request] {method} {url} PARAMS: {params}")
        
        try:
            _logger.debug(f"Making {method} request to {url}")
            
            # Make the request
            response = requests.request(method, **request_params)
            
            # Log response for debugging
            _logger.debug(f"Response status: {response.status_code}")
            _logger.debug(f"Response body: {response.text[:500]}...")
            
            # Handle response
            if response.status_code == 200:
                try:
                    json_response = response.json()
                    # For 200 OK, return the raw JSON (could be dict or list)
                    # The calling method will normalize it
                    return json_response
                except json.JSONDecodeError:
                    return {'success': True, 'data': response.text}
            elif response.status_code == 201:
                # Successfully created
                try:
                    json_response = response.json()
                    return json_response
                except json.JSONDecodeError:
                    return {'success': True, 'created': True}
            elif response.status_code == 204:
                # No content (successful update/delete)
                return {'success': True}
            else:
                # Error response
                error_msg = f"API Error {response.status_code}: {response.text}"
                _logger.error(error_msg)
                try:
                    # Try to parse error response as JSON
                    error_json = response.json()
                    return {'success': False, 'error': error_msg, 'error_details': error_json}
                except json.JSONDecodeError:
                    return {'success': False, 'error': error_msg}
                
        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {config.timeout} seconds"
            _logger.error(error_msg)
            return {'success': False, 'error': error_msg}
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            _logger.error(error_msg)
            return {'success': False, 'error': error_msg}
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            _logger.error(error_msg)
            return {'success': False, 'error': error_msg}

    # ===== PRODUCT MANAGEMENT =====

    def get_supplier_products(self, page=3, per_page=100):
        """Get supplier products from marketplace"""
        params = {
            'page': page,
            'per_page': per_page
        }
        
        return self._make_api_request('supplier-product', method='GET', params=params)

    def create_product(self, product_record):
        """Create product in marketplace"""
        product_data = self._prepare_product_data(product_record)
        
        result = self._make_api_request('supplier-product', method='POST', data=product_data)
        
        # Ensure consistent return format
        if isinstance(result, list):
            return {'success': True, 'data': result}
        elif isinstance(result, dict):
            if 'success' not in result:
                result['success'] = True
            return result
        else:
            return {'success': False, 'error': 'Invalid response format'}

    def update_product(self, product_record):
        """Update product in marketplace"""
        if not product_record.cartona_id:
            _logger.warning(f"Cannot update product {product_record.name} without external ID")
            return {'success': False, 'error': 'Missing external ID'}
            
        product_data = self._prepare_product_data(product_record)
        endpoint = f'supplier-product/{product_record.cartona_id}'
        
        result = self._make_api_request(endpoint, method='PUT', data=product_data)
        
        # Ensure consistent return format
        if isinstance(result, list):
            return {'success': True, 'data': result}
        elif isinstance(result, dict):
            if 'success' not in result:
                result['success'] = True
            return result
        else:
            return {'success': False, 'error': 'Invalid response format'}

    def bulk_update_products(self, product_records):
        """Bulk update multiple products with only required fields for Cartona API"""
        products_data = []
        for product in product_records:
            products_data.append({
                'supplier_product_id': product.cartona_id,
                'selling_price': str(product.list_price)
            })
        if not products_data:
            return {'success': False, 'error': 'No products to update'}
        _logger.info(f"[Cartona API Request Body] /api/v1/supplier-product/bulk-update: {products_data}")
        result = self._make_api_request('supplier-product/bulk-update', method='POST', data=products_data)
        _logger.info(f"[Cartona API Response] /api/v1/supplier-product/bulk-update: {result}")
        # Use centralized response normalization
        return self._normalize_api_response(result)

    def update_product_stock(self, product_record):
        """Update product stock in marketplace"""
        if not product_record.cartona_id:
            return {'success': False, 'error': 'Missing external ID'}
        
        stock_data = [{
            'supplier_product_id': product_record.cartona_id,
            'available_stock_quantity': int(product_record.qty_available),
        }]
        result = self._make_api_request('supplier-product/bulk-update', method='POST', data=stock_data)
        # Use centralized response normalization
        return self._normalize_api_response(result)

    def bulk_update_stock(self, product_records):
        """Bulk update stock for multiple products"""
        stock_data = []
        for product in product_records:
            if product.cartona_id:
                stock_data.append({
                    'supplier_product_id': product.cartona_id,
                    'available_stock_quantity': int(product.qty_available),
                })
        if not stock_data:
            return {'success': False, 'error': 'No products with external IDs for stock update'}
        result = self._make_api_request('supplier-product/bulk-update', method='POST', data=stock_data)
        # Use centralized response normalization
        return self._normalize_api_response(result)

    def _prepare_product_data(self, product_record):
        """Prepare product data for API submission"""
        return {
            'id': product_record.cartona_id,
            'name': product_record.name,
            'description': product_record.description_sale or product_record.name,
            'price': float(product_record.list_price),
            'sku': product_record.default_code or product_record.barcode or str(product_record.id),
            'category': product_record.categ_id.name if product_record.categ_id else 'General',
            'quantity': int(product_record.qty_available) if hasattr(product_record, 'qty_available') else 0,
            'currency': product_record.currency_id.name if product_record.currency_id else 'USD',
            'barcode': product_record.barcode,
            'weight': float(product_record.weight) if product_record.weight else 0.0,
            'delivered_by': product_record.delivered_by,
            'dimensions': {
                'length': float(product_record.product_length) if hasattr(product_record, 'product_length') and product_record.product_length else 0.0,
                'width': float(product_record.product_width) if hasattr(product_record, 'product_width') and product_record.product_width else 0.0,
                'height': float(product_record.product_height) if hasattr(product_record, 'product_height') and product_record.product_height else 0.0,
            }
        }

    def _prepare_stock_data(self, product_record):
        """Prepare stock data for API submission"""
        return {
            'product_id': product_record.cartona_id,
            'sku': product_record.default_code or product_record.barcode or str(product_record.id),
            'quantity': int(product_record.qty_available),
            'available_quantity': int(product_record.virtual_available),
            'reserved_quantity': int(product_record.outgoing_qty) if hasattr(product_record, 'outgoing_qty') else 0,
            'incoming_quantity': int(product_record.incoming_qty) if hasattr(product_record, 'incoming_qty') else 0,
        }

    # ===== ORDER MANAGEMENT =====

    def pull_orders(self, from_date, to_date, page=1, per_page=100):
        """Pull orders from marketplace within a given date range"""
        params = {
            'page': page,
            'per_page': per_page,
            'from': from_date.isoformat() if isinstance(from_date, datetime) else from_date,
            'to': to_date.isoformat() if isinstance(to_date, datetime) else to_date,
        }

        _logger.info(f"Pulling orders from {params['from']} to {params['to']}")

        result = self._make_api_request('order/pull-orders', method='GET', params=params)

        # Use centralized response normalization
        return self._normalize_api_response(result)

    def update_order_status(self, order_record, new_status):
        """Update order status in Cartona marketplace using bulk endpoint (legacy)"""
        if not order_record.cartona_id:
            return {'success': False, 'error': 'Missing external order ID (cartona_id)'}
            
        # Use Cartona's bulk API format with array of orders
        status_data = [{
            'hashed_id': order_record.cartona_id,
            'status': new_status
        }]
        
        # Add optional fields if needed
        if new_status == 'delivered' and order_record.marketplace_payment_method in ['installment', 'wallet_top_up']:
            # For orders requiring OTP
            status_data[0]['retailer_otp'] = self._get_or_generate_otp(order_record)
        
        if new_status == 'cancelled_by_supplier':
            status_data[0]['cancellation_reason'] = self._get_cancellation_reason(order_record)
            
        _logger.info(f"Updating order status (bulk endpoint) for {order_record.cartona_id} to {new_status}")
        _logger.info(f"API Call: POST order/update-order-status")
        _logger.info(f"Request Body: {status_data}")
        
        result = self._make_api_request('order/update-order-status', method='POST', data=status_data)
        
        # Log the API response for debugging
        _logger.info(f"Cartona API response for bulk order {order_record.cartona_id}: {result}")
        
        # Ensure we return a dictionary format that the calling code expects
        return self._normalize_api_response(result)

    def update_single_order_status(self, order_record, new_status):
        """Update single order status using the individual endpoint"""
        if not order_record.cartona_id:
            return {'success': False, 'error': 'Missing external order ID (cartona_id)'}
            
        # Use single order endpoint with cartona_id in URL
        endpoint = f'order/update-order-status/{order_record.cartona_id}'
        
        # Body structure as specified by Cartona API
        status_data = {
            'status': new_status,
            'hashed_id': order_record.cartona_id
        }
        
        # Add optional fields if needed
        if new_status == 'delivered' and order_record.marketplace_payment_method in ['installment', 'wallet_top_up']:
            status_data['retailer_otp'] = self._get_or_generate_otp(order_record)
        
        if new_status == 'cancelled_by_supplier':
            status_data['cancellation_reason'] = self._get_cancellation_reason(order_record)
            
        _logger.info(f"Updating single order status for {order_record.cartona_id} to {new_status}")
        _logger.info(f"API Call: POST {endpoint}")
        _logger.info(f"Request Body: {status_data}")
        
        result = self._make_api_request(endpoint, method='POST', data=status_data)
        
        # Log the API response for debugging
        _logger.info(f"Cartona API response for single order {order_record.cartona_id}: {result}")
        
        # Normalize response format
        return self._normalize_api_response(result)

    def _get_or_generate_otp(self, order_record):
        """Get or generate OTP for delivery confirmation"""
        # Check if OTP is stored in order
        if hasattr(order_record, 'delivery_otp') and order_record.delivery_otp:
            return order_record.delivery_otp
        
        # For now, return None - OTP should be handled separately
        # In a real implementation, this would integrate with an OTP service
        return None

    def _get_cancellation_reason(self, order_record):
        """Get cancellation reason from order"""
        # Map common cancellation reasons
        reason_mapping = {
            'out_of_stock': 'out_of_stock',
            'cannot_deliver': 'cannot_deliver_the_order',
            'delayed': 'delayed_order',
            'supplier_request': 'supplier_asked_me_to_cancel',
            'expired_products': 'expired_products',
            'missing_items': 'missing_items'
        }
        
        # Get reason from order notes or use default
        if order_record.marketplace_notes and 'cancel' in order_record.marketplace_notes.lower():
            return 'supplier_asked_me_to_cancel'
        
        return 'supplier_asked_me_to_cancel'  # Default reason

    def bulk_update_order_status(self, order_records, status_updates):
        """Update multiple order statuses in a single API call"""
        if not order_records:
            return {'success': False, 'error': 'No orders provided for bulk update'}
            
        status_data = []
        for order, status in zip(order_records, status_updates):
            if not order.cartona_id:
                continue
                
            order_data = {
                'hashed_id': order.cartona_id,
                'status': status
            }
            
            # Add optional fields if needed
            if status == 'delivered' and order.marketplace_payment_method in ['installment', 'wallet_top_up']:
                otp = self._get_or_generate_otp(order)
                if otp:
                    order_data['retailer_otp'] = otp
            
            if status == 'cancelled_by_supplier':
                order_data['cancellation_reason'] = self._get_cancellation_reason(order)
                
            status_data.append(order_data)
        
        if not status_data:
            return {'success': False, 'error': 'No valid orders with cartona_id for bulk update'}
            
        _logger.info(f"Bulk updating {len(status_data)} order statuses")
        _logger.info(f"API Call: POST order/update-order-status")
        _logger.info(f"Request Body: {status_data}")
        
        result = self._make_api_request('order/update-order-status', method='POST', data=status_data)
        
        # Log the API response for debugging
        _logger.info(f"Cartona API response for bulk update: {result}")
        
        return self._normalize_api_response(result)

    def _normalize_api_response(self, response):
        """Normalize API response to consistent dictionary format"""
        if response is None:
            return {'success': False, 'error': 'No response received'}
        
        # If response is already a dictionary with success field, return as-is
        if isinstance(response, dict):
            if 'success' in response:
                return response
            # If it's a dict but no success field, consider it successful
            return {'success': True, 'data': response}
        
        # If response is a list (typical for Cartona bulk operations)
        if isinstance(response, list):
            if len(response) == 0:
                return {'success': True, 'data': response, 'message': 'Empty response list'}
            
            # Check if any items in the list indicate an error
            # For Cartona, a successful response is typically an empty list or list of success items
            return {'success': True, 'data': response, 'message': f'Processed {len(response)} items'}
        
        # For any other type, wrap it in a success response
        return {'success': True, 'data': response}

    def update_order_details(self, order_record, updates):
        """Update order details (quantities, items, etc.)"""
        if not order_record.cartona_id:
            return {'success': False, 'error': 'Missing external order ID'}
            
        order_data = {
            'order_id': order_record.cartona_id,
            'updates': updates,
            'updated_at': fields.Datetime.now().isoformat()
        }
        
        return self._make_api_request('order/update-order-details', method='POST', data=[order_data])

    # ===== SYNCHRONIZATION METHODS =====

    def sync_all_products(self):
        """Sync all products to marketplace"""
        config = self._get_marketplace_config()
        
        # Log the start of product sync
        self.env['marketplace.sync.log'].log_operation(
            marketplace_config_id=config.id,
            operation_type='product_sync',
            status='info',
            message="Starting product synchronization",
        )
        
        # Get all products that should be synced
        products = self.env['product.template'].search([
            ('marketplace_sync_enabled', '=', True)
        ])
        
        if not products:
            # Log no products to sync
            warning_msg = _("No products are currently enabled for synchronization. Please ensure that the products you want to sync are marked as 'Active' and have the 'Enable Cartona Marketplace Sync' checkbox ticked.")
            _logger.warning(warning_msg)
            self.env['marketplace.sync.log'].log_operation(
                marketplace_config_id=config.id,
                operation_type='product_sync',
                status='warning',
                message=warning_msg,
                records_processed=0
            )
            return {'success': True, 'message': warning_msg}
            
        # Process in batches
        batch_size = config.batch_size
        total_products = len(products)
        success_count = 0
        error_count = 0
        
        _logger.info(f"Starting sync of {total_products} products to {config.name}")
        
        for i in range(0, total_products, batch_size):
            batch = products[i:i + batch_size]
            
            try:
                result = self.bulk_update_products(batch)
                
                if result.get('success'):
                    success_count += len(batch)
                    # Update sync status for successful products
                    batch.write({
                        'marketplace_sync_status': 'synced',
                        'marketplace_sync_date': fields.Datetime.now(),
                        'marketplace_error_message': False
                    })
                    
                    # Log successful batch
                    self.env['marketplace.sync.log'].log_operation(
                        marketplace_config_id=config.id,
                        operation_type='product_sync',
                        status='success',
                        message=f"Successfully synced batch of {len(batch)} products",
                        records_processed=len(batch),
                        records_success=len(batch)
                    )
                else:
                    error_count += len(batch)
                    error_msg = result.get('error', 'Unknown error')
                    
                    # Update sync status for failed products
                    batch.write({
                        'marketplace_sync_status': 'error',
                        'marketplace_error_message': error_msg
                    })
                    
                    # Log failed batch
                    self.env['marketplace.sync.log'].log_operation(
                        marketplace_config_id=config.id,
                        operation_type='product_sync',
                        status='error',
                        message=f"Failed to sync batch of {len(batch)} products: {error_msg}",
                        records_processed=len(batch),
                        records_error=len(batch),
                        error_details=error_msg
                    )
                    
            except Exception as e:
                error_count += len(batch)
                error_msg = f"Batch sync error: {str(e)}"
                _logger.error(error_msg)
                
                batch.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': error_msg
                })
                
                # Log batch exception
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=config.id,
                    operation_type='product_sync',
                    status='error',
                    message=f"Exception during batch sync of {len(batch)} products",
                    records_processed=len(batch),
                    records_error=len(batch),
                    error_details=error_msg
                )
        
        # Log final summary
        status = 'success' if error_count == 0 else ('warning' if success_count > 0 else 'error')
        summary_msg = f"Product sync completed: {success_count} successful, {error_count} failed out of {total_products} total"
        
        self.env['marketplace.sync.log'].log_operation(
            marketplace_config_id=config.id,
            operation_type='product_sync',
            status=status,
            message=summary_msg,
            records_processed=total_products,
            records_success=success_count,
            records_error=error_count
        )
        
        # Update marketplace statistics with actual totals, not incremental
        # The manual_sync_products method will handle the stats update
        
        return {
            'success': True,
            'total_products': total_products,
            'success_count': success_count,
            'error_count': error_count
        }

    def pull_and_process_orders(self, since_date=None):
        """Pull and process orders from marketplace"""
        config = self._get_marketplace_config()
        
        # Default to last 24 hours if no date specified
        to_date = datetime.now()
        if not since_date:
            from_date = to_date - timedelta(hours=24)
        else:
            from_date = since_date
            
        # Get orders from marketplace
        result = self.pull_orders(from_date=from_date, to_date=to_date)
        
        if not result.get('success'):
            _logger.error(f"Order pull failed: {result}")
            return {
                'success': False,
                'message': 'Failed to pull orders from marketplace',
                'orders_pulled': 0,
                'orders_new': 0,
                'orders_total': 0,
                'errors': [result.get('message', 'Unknown error')]
            }
        
        orders_data = result.get('data', [])
        
        if not orders_data:
            _logger.info("No orders found in date range")
            return {
                'success': True,
                'message': 'No orders found in specified date range',
                'orders_pulled': 0,
                'orders_new': 0,
                'orders_total': 0,
                'errors': []
            }
        
        # Process each order
        processor = self.env['marketplace.order.processor']
        orders_processed = 0
        orders_new = 0
        orders_updated = 0
        errors = []
        
        for i, order_data in enumerate(orders_data, 1):
            try:
                result = processor.process_marketplace_order(order_data)
                if result:
                    orders_processed += 1
                    if result.get('is_new'):
                        orders_new += 1
                    elif result.get('updated'):
                        orders_updated += 1
                else:
                    errors.append(f"Failed to process order {i}: {order_data.get('order_id', 'unknown')}")
                    
            except Exception as e:
                _logger.error(f"Failed to process order {i}: {order_data.get('order_id', 'unknown')}")
                errors.append(f"Error processing order {i}: {str(e)}")
        
        # Log success if any orders processed
        if orders_processed > 0:
            self.env['marketplace.sync.log'].log_operation(
                marketplace_config_id=config.id,
                operation_type='order_pull',
                status='success',
                message=f"Successfully processed {orders_processed} orders ({orders_new} new, {orders_updated} updated)",
                records_processed=orders_processed,
                records_success=orders_new + orders_updated,
                records_error=len(errors)
            )
        elif errors:
            self.env['marketplace.sync.log'].log_operation(
                marketplace_config_id=config.id,
                operation_type='order_pull',
                status='error',
                message=f"Order pull completed with errors: {len(errors)} failed.",
                records_processed=orders_processed,
                records_error=len(errors)
            )
        
        return {
            'success': True,
            'message': f'Processed {orders_processed} orders successfully ({orders_new} new, {orders_updated} updated)',
            'orders_pulled': len(orders_data),
            'orders_new': orders_new,
            'orders_updated': orders_updated,
            'orders_total': orders_processed,
            'errors': errors
        }

    @api.model
    def test_all_marketplace_connections(self):
        """Test connections to all active marketplaces"""
        marketplaces = self.env['marketplace.config'].get_active_marketplaces()
        results = []
        
        for marketplace in marketplaces:
            try:
                marketplace.test_connection()
                results.append({
                    'marketplace': marketplace.name,
                    'status': 'success',
                    'message': 'Connection successful'
                })
            except Exception as e:
                results.append({
                    'marketplace': marketplace.name,
                    'status': 'error',
                    'message': str(e)
                })
                
        return results
