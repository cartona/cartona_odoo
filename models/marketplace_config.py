from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)


class MarketplaceConfig(models.Model):
    _name = 'marketplace.config'
    _description = 'Marketplace Integration Configuration'
    _rec_name = 'name'
    _order = 'sequence, name'

    # Basic Configuration
    name = fields.Char(string="Marketplace Name", required=True, 
                      help="Display name for this marketplace (e.g., 'Cartona', 'Amazon', 'eBay')")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    
    # API Configuration
    api_base_url = fields.Char(string="API Base URL", required=True,
                              default="https://supplier-integrations.cartona.com/api/v1/",
                              help="Base URL for the marketplace API")
    auth_token = fields.Char(string="Authentication Token", required=True,
                            help="Bearer token provided by the marketplace")
    auth_header = fields.Char(string="Auth Header Name", default="AuthorizationToken",
                             help="Header name for authentication (default: AuthorizationToken)")
    
    # Sync Settings
    # auto_sync_products = fields.Boolean(string="Auto Sync Products", default=True,
    #                                    help="Automatically sync product changes to marketplace")
    auto_sync_stock = fields.Boolean(string="Auto Sync Stock", default=True,
                                    help="Automatically sync stock changes to marketplace")
    auto_sync_prices = fields.Boolean(string="Auto Sync Prices", default=True,
                                     help="Automatically sync price changes to marketplace")
    auto_pull_orders = fields.Boolean(string="Auto Pull Orders", default=True,
    help="Automatically pull orders from marketplace")
    
    # Advanced Settings
    batch_size = fields.Integer(string="Batch Size", default=100,
                               help="Number of records to process per batch")
    retry_attempts = fields.Integer(string="Retry Attempts", default=3,
                                   help="Number of retry attempts for failed operations")
    timeout = fields.Integer(string="Request Timeout (seconds)", default=30,
                            help="API request timeout in seconds")
    
    # Status Fields
    last_sync_date = fields.Datetime(string="Last Sync Date", readonly=True)
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], string="Connection Status", default='not_tested', readonly=True)
    error_message = fields.Text(string="Last Error", readonly=True)
    
    # Statistics
    total_products_synced = fields.Integer(string="Products Synced", readonly=True, default=0)
    total_orders_pulled = fields.Integer(string="Orders Pulled", readonly=True, default=0)
    last_order_pull = fields.Datetime(string="Last Order Pull", readonly=True)
    
    # Note: Removed state field to avoid conflicts with Odoo's internal state management
    
    @api.constrains('api_base_url')
    def _check_api_base_url(self):
        """Validate API base URL format"""
        for record in self:
            if record.api_base_url and not record.api_base_url.startswith(('http://', 'https://')):
                raise ValidationError(_("API Base URL must start with http:// or https://"))
            if record.api_base_url and not record.api_base_url.endswith('/'):
                record.api_base_url += '/'

    @api.constrains('batch_size')
    def _check_batch_size(self):
        """Validate batch size"""
        for record in self:
            if record.batch_size < 1 or record.batch_size > 1000:
                raise ValidationError(_("Batch size must be between 1 and 1000"))

    @api.constrains('active')
    def _check_single_active_config(self):
        """Ensure only one active marketplace configuration exists"""
        active_configs = self.search([('active', '=', True)])
        if len(active_configs) > 1:
            raise ValidationError(
                _("Only one marketplace configuration can be active at a time. "
                  "Please deactivate other configurations first.")
            )

    def test_connection(self):
        """Test connection to marketplace API"""
        self.ensure_one()
        
        # Store the current record ID for updates
        record_id = self.id
        
        try:
            # Reset connection status at the start of each test using SQL
            self.env.cr.execute(
                "UPDATE marketplace_config SET connection_status = %s, error_message = %s WHERE id = %s",
                ('not_tested', None, record_id)
            )
            self.env.cr.commit()
            
            # Prepare headers
            headers = {
                self.auth_header: self.auth_token,
                'Content-Type': 'application/json',
                'User-Agent': 'Odoo-Cartona-Integration/1.0'
            }
            
            # Test endpoint - try to get supplier products (common endpoint)
            test_url = f"{self.api_base_url}supplier-product"
            
            _logger.info(f"Testing connection to {self.name} at {test_url}")
            
            response = requests.get(
                test_url,
                headers=headers,
                timeout=self.timeout,
                params={'page': 1, 'per_page': 1}  # Minimal request
            )
            
            if response.status_code == 200:
                # Success: Update status using SQL to ensure persistence
                self.env.cr.execute(
                    "UPDATE marketplace_config SET connection_status = %s, error_message = %s, last_sync_date = %s WHERE id = %s",
                    ('connected', None, fields.Datetime.now(), record_id)
                )
                self.env.cr.commit()
                
                # Refresh the record to show updated status
                self._invalidate_cache(['connection_status', 'error_message', 'last_sync_date'])
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Connection Successful"),
                        'message': _("Successfully connected to %s marketplace API") % self.name,
                        'type': 'success',
                    }
                }
            else:
                # Handle specific HTTP error codes with user-friendly messages
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        if 'error' in error_data and 'invalid credentials' in error_data['error'].lower():
                            friendly_msg = _("Invalid credentials. Please check your authentication token.")
                        else:
                            friendly_msg = _("Bad request. Please verify your API settings and credentials.")
                    except:
                        friendly_msg = _("Invalid credentials or bad request. Please check your authentication token and API settings.")
                elif response.status_code == 401:
                    friendly_msg = _("Authentication failed. Your authentication token is invalid or expired.")
                elif response.status_code == 403:
                    friendly_msg = _("Access denied. Your account may not have permission to access this API.")
                elif response.status_code == 404:
                    friendly_msg = _("API endpoint not found. Please verify the API base URL is correct.")
                elif response.status_code == 429:
                    friendly_msg = _("Too many requests. Please wait a moment and try again.")
                elif response.status_code >= 500:
                    friendly_msg = _("Server error on marketplace side. Please try again later or contact marketplace support.")
                else:
                    friendly_msg = _("Connection failed with HTTP %s. Please check your configuration.") % response.status_code
                
                # Store technical details for debugging
                technical_error = f"HTTP {response.status_code}: {response.text}"
                
                # Update status to error using SQL to ensure persistence
                self.env.cr.execute(
                    "UPDATE marketplace_config SET connection_status = %s, error_message = %s WHERE id = %s",
                    ('error', technical_error, record_id)
                )
                self.env.cr.commit()
                
                # Refresh the record to show updated status
                self._invalidate_cache(['connection_status', 'error_message'])
                
                raise UserError(friendly_msg)
                
        except requests.exceptions.Timeout:
            error_msg = _("Connection timeout after %d seconds") % self.timeout
            # Update status to error using SQL to ensure persistence
            self.env.cr.execute(
                "UPDATE marketplace_config SET connection_status = %s, error_message = %s WHERE id = %s",
                ('error', error_msg, record_id)
            )
            self.env.cr.commit()
            
            # Refresh the record to show updated status
            self._invalidate_cache(['connection_status', 'error_message'])
            
            raise UserError(error_msg)
            
        except requests.exceptions.ConnectionError as e:
            error_msg = _("Cannot connect to marketplace API: %s") % str(e)
            # Update status to error using SQL to ensure persistence
            self.env.cr.execute(
                "UPDATE marketplace_config SET connection_status = %s, error_message = %s WHERE id = %s",
                ('error', error_msg, record_id)
            )
            self.env.cr.commit()
            
            # Refresh the record to show updated status
            self._invalidate_cache(['connection_status', 'error_message'])
            
            raise UserError(error_msg)
            
        except UserError:
            # Re-raise UserError without modification (status already updated above)
            raise
            
        except Exception as e:
            # Parse the error message to provide more user-friendly feedback
            error_str = str(e).lower()
            
            if 'invalid credentials' in error_str:
                friendly_msg = _("Invalid credentials. Please verify your authentication token is correct.")
            elif 'connection failed' in error_str and 'http 400' in error_str:
                friendly_msg = _("Authentication failed. Please check your credentials and try again.")
            elif 'connection refused' in error_str or 'name resolution failed' in error_str:
                friendly_msg = _("Cannot reach the marketplace API. Please check the API base URL and your internet connection.")
            elif 'ssl' in error_str or 'certificate' in error_str:
                friendly_msg = _("SSL certificate error. The marketplace API may have certificate issues.")
            elif 'timeout' in error_str:
                friendly_msg = _("Connection timeout. The marketplace API is taking too long to respond.")
            else:
                friendly_msg = _("Connection test failed. Please check your API configuration and try again.")
            
            # Store detailed error for debugging
            technical_error = f"Unexpected error: {str(e)}"
            
            # Update status to error using SQL to ensure persistence
            self.env.cr.execute(
                "UPDATE marketplace_config SET connection_status = %s, error_message = %s WHERE id = %s",
                ('error', technical_error, record_id)
            )
            self.env.cr.commit()
            
            # Refresh the record to show updated status
            self._invalidate_cache(['connection_status', 'error_message'])
            
            _logger.error(f"Connection test failed for {self.name}: {e}")
            raise UserError(friendly_msg)

    def get_api_headers(self):
        """Get headers for API requests"""
        self.ensure_one()
        return {
            self.auth_header: self.auth_token,
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo-Cartona-Integration/1.0'
        }

    def action_show_credential_help(self):
        """Show help dialog for obtaining API credentials"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('API Credentials Help'),
            'res_model': 'marketplace.config',
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',
            'context': {
                'default_name': self.name,
                'help_mode': True,
            },
            'flags': {'mode': 'readonly'},
        }

    def manual_sync_products(self):
        """Manual product synchronization"""
        self.ensure_one()

        _logger.info("--- Starting Manual Product Sync ---")

        # Use a new cursor for this operation to ensure transactional integrity
        with self.pool.cursor() as cr:
            # Re-instantiate self with the new cursor
            this = self.with_env(self.env(cr=cr))

            # Check for products to sync first
            products_to_sync = this.env['product.template'].search([
                ('marketplace_sync_enabled', '=', True),
                ('active', '=', True)
            ])

            if not products_to_sync:
                _logger.warning("No products found with 'Enable Cartona Marketplace Sync' checked.")
                raise UserError(_(
                    "No products are currently enabled for synchronization. "
                    "Please ensure that the products you want to sync are marked as 'Active' and have the 'Enable Cartona Marketplace Sync' checkbox ticked."
                ))
            
            # Get marketplace API client
            api_client = this.env['marketplace.api'].with_context(marketplace_config_id=this.id)
            
            try:
                # Get count before sync
                before_count = this.env['product.template'].search_count([
                    ('cartona_id', '!=', False)
                ])
                
                result = api_client.sync_all_products()
                
                # Get count after sync
                after_count = this.env['product.template'].search_count([
                    ('cartona_id', '!=', False)
                ])
                
                newly_synced = after_count - before_count
                
                # Update stats with actual totals
                this._update_sync_stats(products_count=after_count, is_increment=False)
                
                # Commit the transaction
                cr.commit()

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Product Sync Complete"),
                        'message': _("Synced %d products (%d new, %d total synced)") % (
                            result.get('success_count', 0),
                            newly_synced,
                            after_count
                        ),
                        'type': 'success',
                    }
                }
            except Exception as e:
                _logger.error(f"Manual product sync failed for {this.name}: {e}")
                cr.rollback()  # Rollback on error
                raise UserError(_("Sync failed: %s") % str(e))

    def manual_pull_orders(self):
        """Manual order pull from Cartona marketplace"""
        self.ensure_one()
        # Get marketplace API client  
        api_client = self.env['marketplace.api'].with_context(marketplace_config_id=self.id)
        try:
            # Get count before import
            before_count = self.env['sale.order'].search_count([
                ('cartona_id', '!=', False)
            ])
            result = api_client.pull_and_process_orders()
            # Get count after import
            after_count = self.env['sale.order'].search_count([
                ('cartona_id', '!=', False)
            ])
            newly_imported = after_count - before_count
            
            # Extract results from API response
            orders_new = result.get('orders_new', 0)
            orders_updated = result.get('orders_updated', 0)
            orders_total = result.get('orders_total', 0)
            
            # Update stats with actual totals
            self._update_sync_stats(orders_count=after_count, is_increment=False)
            
            # Create enhanced notification message
            if orders_new > 0 and orders_updated > 0:
                message = _("Pulled %d orders: %d new, %d updated (%d total in system)") % (
                    orders_total, orders_new, orders_updated, after_count
                )
            elif orders_new > 0:
                message = _("Pulled %d new orders (%d total in system)") % (
                    orders_new, after_count
                )
            elif orders_updated > 0:
                message = _("Updated %d existing orders (%d total in system)") % (
                    orders_updated, after_count
                )
            else:
                message = _("No new orders found (%d total in system)") % after_count
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Order Pull Complete"),
                    'message': message,
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Manual order pull failed for {self.name}: {e}")
            raise UserError(_("Order pull failed: %s") % str(e))

    @api.model
    def get_active_marketplaces(self):
        """Get all active marketplace configurations"""
        return self.search([('active', '=', True)])

    def _update_sync_stats(self, products_count=0, orders_count=0, is_increment=False):
        """Update synchronization statistics
        
        Args:
            products_count: Number of products synced (or total if is_increment=False)
            orders_count: Number of orders pulled (or total if is_increment=False)
            is_increment: If True, add to existing count; if False, set as total count
        """
        self.ensure_one()
        
        vals = {'last_sync_date': fields.Datetime.now()}
        
        if products_count > 0:
            if is_increment:
                vals['total_products_synced'] = self.total_products_synced + products_count
            else:
                # Set actual total count of products with cartona_id
                actual_synced_products = self.env['product.template'].search_count([
                    ('cartona_id', '!=', False)
                ])
                vals['total_products_synced'] = actual_synced_products
            
        if orders_count > 0:
            if is_increment:
                vals['total_orders_pulled'] = self.total_orders_pulled + orders_count
                vals['last_order_pull'] = fields.Datetime.now()
            else:
                actual_pulled_orders = self.env['sale.order'].search_count([
                    ('cartona_id', '!=', False)
                ])
                vals['total_orders_pulled'] = actual_pulled_orders
                vals['last_order_pull'] = fields.Datetime.now()
            
        self.write(vals)

    def recalculate_sync_stats(self):
        """Recalculate synchronization statistics based on actual data"""
        self.ensure_one()
        
        # Count actual synced products (products with cartona_id)
        actual_synced_products = self.env['product.template'].search_count([
            ('cartona_id', '!=', False)
        ])
        
        # Count actual pulled orders (orders with cartona_id)
        actual_pulled_orders = self.env['sale.order'].search_count([
            ('cartona_id', '!=', False)
        ])
        
        # Get last order pull date
        last_order = self.env['sale.order'].search([
            ('cartona_id', '!=', False)
        ], order='create_date desc', limit=1)
        
        vals = {
            'total_products_synced': actual_synced_products,
            'total_orders_pulled': actual_pulled_orders,
        }
        
        if last_order:
            vals['last_order_pull'] = last_order.create_date
            
        self.write(vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Statistics Refreshed"),
                'message': _("Dashboard updated: %d products synced, %d orders pulled") % (
                    actual_synced_products, actual_pulled_orders
                ),
                'type': 'info',
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure only one configuration exists"""
        existing_configs = self.search([])
        if existing_configs:
            raise ValidationError(
                _("Only one Cartona configuration is allowed. "
                  "Please edit the existing configuration instead of creating a new one.")
            )
        return super().create(vals_list)

    @api.model
    def get_or_create_config(self):
        """Get existing config or create a default one"""
        config = self.search([], limit=1)
        if not config:
            config = self.create({
                'name': 'Cartona Integration',
                'api_base_url': 'https://supplier-integrations.cartona.com/api/v1/',
                'auth_header': 'AuthorizationToken',
                'active': True,
            })
            # Initialize stats with actual counts
            config.recalculate_sync_stats()
        return config

    @api.model
    def default_get(self, fields_list):
        """Override default_get to ensure stats are up to date"""
        res = super().default_get(fields_list)
        
        # If we have an existing config, refresh its stats
        existing_config = self.search([], limit=1)
        if existing_config:
            existing_config.recalculate_sync_stats()
            
        return res

    def manual_pull_products(self):
        """Manual import of products from Cartona marketplace (single API call, no pagination)"""
        self.ensure_one()
        _logger.info("--- Starting Manual Product Pull from Cartona (single call) ---")

        imported = 0
        updated = 0
        errors = 0
        total = 0
        api_client = self.env['marketplace.api'].with_context(marketplace_config_id=self.id)
        Product = self.env['product.template']
        try:
            result = api_client.get_supplier_products()
            if not result or (isinstance(result, dict) and not result.get('success', True)):
                _logger.error(f"Failed to fetch products from Cartona: {result.get('error') if isinstance(result, dict) else result}")
                raise UserError(_("Failed to fetch products from Cartona: %s") % (result.get('error') if isinstance(result, dict) else result))
            products = result.get('data') if isinstance(result, dict) else result
            if not products:
                raise UserError(_("No products returned from Cartona API."))
            for prod in products:
                cartona_id = prod.get('id') or prod.get('cartona_id') or prod.get('supplier_product_id')
                internal_product_id = prod.get('internal_product_id')
                _logger.info(f"Internal Product ID: {internal_product_id}")
                if not cartona_id:
                    errors += 1
                    continue
                # Get stock quantity from Cartona API - ensure it's a valid number
                available_stock_quantity = prod.get('available_stock_quantity', 0)
                try:
                    available_stock_quantity = float(available_stock_quantity or 0)
                except (TypeError, ValueError):
                    _logger.warning(f"Invalid stock quantity in API response for product {cartona_id}: {available_stock_quantity}. Setting to 0.")
                    available_stock_quantity = 0.0
                
                vals = {
                    'cartona_id': cartona_id,
                    'name': prod.get('name') or prod.get('suppler_prodcut_name') or prod.get('product_name') or 'Cartona Product',
                    'list_price': prod.get('price') or prod.get('selling_price') or 0.0,
                    'active': prod.get('active', True),
                    'marketplace_sync_enabled': True,
                    'description_sale': prod.get('description') or prod.get('base_product_name') or '',
                    'type': 'consu',  # Set product type to consumable
                    'is_storable': True,  # Enable storable tracking
                }
                existing = Product.search([('cartona_id', '=', cartona_id)], limit=1)
                if existing:
                    # Check if there are multiple products with same cartona_id (duplicates)
                    duplicates = Product.search([('cartona_id', '=', cartona_id)])
                    if len(duplicates) > 1:
                        _logger.warning(f"Found {len(duplicates)} products with cartona_id {cartona_id}. Using first one and skipping update to avoid constraint error.")
                        # Just update stock for the first one found, skip the write operation
                        self._update_product_stock(existing, available_stock_quantity)
                        # Ensure cartona_id is set on all variants
                        for variant in existing.product_variant_ids:
                            variant.cartona_id = cartona_id
                        updated += 1
                    else:
                        # Safe to update - only one product with this cartona_id
                        _logger.info(f"Updating existing Product: {existing}")
                        _logger.info(f"Vals: {vals}")
                        try:
                            # Remove cartona_id from vals to avoid constraint trigger during update
                            update_vals = vals.copy()
                            del update_vals['cartona_id']  # Don't update cartona_id if it's the same
                            existing.write(update_vals)
                            # Ensure cartona_id is set on all variants
                            for variant in existing.product_variant_ids:
                                variant.cartona_id = cartona_id
                            # Update stock quantity for existing product
                            self._update_product_stock(existing, available_stock_quantity)
                            updated += 1
                        except Exception as e:
                            _logger.error(f"Error updating product {existing.name}: {e}")
                            errors += 1
                else:
                    # If internal_product_id is present and valid, set it as the Odoo product's id
                    if internal_product_id:
                        _logger.info(f"Internal Product ID: {internal_product_id}")
                        try:
                            vals['id'] = int(internal_product_id)
                            _logger.info(f"Vals after setting id: {vals}")
                        except Exception:
                            _logger.error(f"Error setting id: {e}")
                            pass  # Ignore if not a valid int
                    new_product = Product.create(vals)
                    # Set initial stock quantity for new product
                    self._update_product_stock(new_product, available_stock_quantity)
                    # Ensure cartona_id is set on all variants
                    for variant in new_product.product_variant_ids:
                        variant.cartona_id = cartona_id
                    imported += 1
                total += 1
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Product Import Complete"),
                    'message': _("Imported %d new, updated %d products from Cartona. (Total processed: %d, Errors: %d)") % (imported, updated, total, errors),
                    'type': 'success' if errors == 0 else 'warning',
                }
            }
        except Exception as e:
            _logger.error(f"Manual product pull failed for {self.name}: {e}")
            raise UserError(_("Product import failed: %s") % str(e))

    def check_duplicate_cartona_ids(self):
        """Check for and report duplicate cartona_id values in products"""
        self.ensure_one()
        
        # Find products with duplicate cartona_ids
        Product = self.env['product.template']
        
        # SQL query to find duplicates
        self.env.cr.execute("""
            SELECT cartona_id, COUNT(*) as count, array_agg(id) as product_ids
            FROM product_template 
            WHERE cartona_id IS NOT NULL AND cartona_id != ''
            GROUP BY cartona_id 
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        duplicates = self.env.cr.fetchall()
        
        if not duplicates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("No Duplicates Found"),
                    'message': _("No duplicate cartona_id values found in the database."),
                    'type': 'success',
                }
            }
        
        # Report the duplicates
        message_lines = [_("Found duplicate cartona_id values:")]
        total_duplicates = 0
        
        for cartona_id, count, product_ids in duplicates:
            products = Product.browse(product_ids)
            product_names = [p.name[:50] + ('...' if len(p.name) > 50 else '') for p in products]
            message_lines.append(f"• cartona_id '{cartona_id}': {count} products")
            for i, name in enumerate(product_names):
                message_lines.append(f"  - ID {product_ids[i]}: {name}")
            total_duplicates += count - 1  # count - 1 because one is the original
            
        message = "\n".join(message_lines)
        _logger.warning(f"Found {len(duplicates)} sets of duplicate cartona_ids affecting {total_duplicates} products")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Duplicate cartona_id Found"),
                'message': message,
                'type': 'warning',
                'sticky': True,
            }
        }

    def _update_product_stock(self, product, stock_quantity):
        """Update product stock quantity using stock.quant
        
        Args:
            product: product.template record
            stock_quantity: Available stock quantity from Cartona API
        """
        if not product:
            return
            
        # Ensure stock_quantity is a valid number
        try:
            stock_quantity = float(stock_quantity or 0)
        except (TypeError, ValueError):
            _logger.warning(f"Invalid stock quantity for product {product.name}: {stock_quantity}. Setting to 0.")
            stock_quantity = 0.0
            
        if stock_quantity < 0:
            return
            
        _logger.info(f"Setting stock quantity {stock_quantity} for product {product.name}")
        
        try:
            # Get the main stock location 
            main_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
            if not main_location:
                # Fallback to first internal location
                main_location = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    ('company_id', 'in', [self.env.company.id, False])
                ], limit=1)
                
            if not main_location:
                _logger.warning(f"No internal stock location found for product {product.name}")
                return
                
            # For product templates, we need to work with product.product (variants)
            product_variants = product.product_variant_ids
            if not product_variants:
                _logger.warning(f"No product variants found for {product.name}")
                return
                
            # Update stock for the first variant (most common case)
            # If there are multiple variants, this could be enhanced to handle them separately
            variant = product_variants[0]
            
            # Check if there's already a stock.quant record for this product+location
            existing_quant = self.env['stock.quant'].search([
                ('product_id', '=', variant.id),
                ('location_id', '=', main_location.id),
            ], limit=1)
            
            if existing_quant:
                # Update existing quant
                if existing_quant.quantity != stock_quantity:
                    _logger.info(f"Updating existing stock: {existing_quant.quantity} -> {stock_quantity}")
                    existing_quant.with_context(skip_marketplace_sync=True).write({
                        'quantity': stock_quantity
                    })
            else:
                # Create new quant if stock_quantity > 0
                if stock_quantity > 0:
                    _logger.info(f"Creating new stock quant with quantity {stock_quantity}")
                    self.env['stock.quant'].with_context(skip_marketplace_sync=True).create({
                        'product_id': variant.id,
                        'location_id': main_location.id,
                        'quantity': stock_quantity,
                        'reserved_quantity': 0,
                    })
                    
        except Exception as e:
            _logger.error(f"Error updating stock for product {product.name}: {e}")
            # Don't raise the error - continue with other products
