from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Universal External Product Variant ID
    cartona_id = fields.Char(
        string="External Variant ID",
        help="External product variant identifier for marketplace integration. "
             "Used for specific product variants (size, color, etc.)",
        index=True,
        copy=False
    )
    
    # Variant-specific sync status
    marketplace_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
        ('partial', 'Partially Synced'),
    ], string="Variant Sync Status", default='not_synced')
    
    marketplace_sync_date = fields.Datetime(string="Last Variant Sync", readonly=True)
    marketplace_error_message = fields.Text(string="Variant Sync Error", readonly=True)
    
    # Stock sync specific to variants
    marketplace_stock_sync_enabled = fields.Boolean(
        string="Enable Cartona Stock Sync",
        default=True,
        help="Enable automatic stock synchronization for this variant to Cartona marketplace"
    )
    
    last_stock_sync_date = fields.Datetime(string="Last Stock Sync", readonly=True)
    stock_sync_error = fields.Text(string="Stock Sync Error", readonly=True)

    @api.constrains('cartona_id')
    def _check_cartona_id_unique(self):
        """Ensure cartona_id is unique when set for variants"""
        for record in self:
            if record.cartona_id:
                existing = self.search([
                    ('cartona_id', '=', record.cartona_id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        _("External Variant ID '%s' already exists on product variant '%s'. "
                          "Each variant must have a unique external ID.") % 
                        (record.cartona_id, existing[0].display_name)
                    )

    def write(self, vals):
        """Override write to trigger stock sync on inventory changes"""
        result = super().write(vals)
        
        # Check if we need to sync stock to marketplaces
        stock_fields = ['qty_available', 'virtual_available']
        if any(field in vals for field in stock_fields):
            if not self.env.context.get('skip_marketplace_sync'):
                self._trigger_stock_sync()
                
        return result

    def _trigger_stock_sync(self):
        """Trigger stock synchronization for this variant"""
        for record in self:
            if record.marketplace_stock_sync_enabled and record.cartona_id:
                # Queue job for async stock sync
                record.with_delay(
                    channel='marketplace',
                    description=f"Sync stock for variant {record.display_name}"
                )._sync_stock_to_marketplaces()

    def _sync_stock_to_marketplaces(self):
        """Sync stock for this variant to all active marketplaces"""
        self.ensure_one()
        
        # Get active marketplace configurations
        marketplaces = self.env['marketplace.config'].get_active_marketplaces()
        
        if not marketplaces:
            return
            
        for marketplace in marketplaces:
            try:
                # Log the start of stock sync
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=marketplace.id,
                    operation_type='stock_sync',
                    status='info',
                    message=f"Starting stock sync for variant: {self.display_name}",
                    record_model='product.product',
                    record_id=self.id,
                    record_name=self.display_name
                )
                
                # Get API client for this marketplace
                api_client = self.env['marketplace.api'].with_context(
                    marketplace_config_id=marketplace.id
                )
                
                # Sync stock to this marketplace
                success = api_client.update_product_stock(self)
                
                if success:
                    self.write({
                        'last_stock_sync_date': fields.Datetime.now(),
                        'stock_sync_error': False
                    })
                    _logger.info(f"Successfully synced stock for {self.display_name} to {marketplace.name}")
                    
                    # Log successful stock sync
                    self.env['marketplace.sync.log'].log_operation(
                        marketplace_config_id=marketplace.id,
                        operation_type='stock_sync',
                        status='success',
                        message=f"Successfully synced stock for variant: {self.display_name}",
                        record_model='product.product',
                        record_id=self.id,
                        record_name=self.display_name,
                        records_processed=1,
                        records_success=1
                    )
                else:
                    _logger.warning(f"Failed to sync stock for {self.display_name} to {marketplace.name}")
                    
                    # Log failed stock sync
                    self.env['marketplace.sync.log'].log_operation(
                        marketplace_config_id=marketplace.id,
                        operation_type='stock_sync',
                        status='error',
                        message=f"Failed to sync stock for variant: {self.display_name}",
                        record_model='product.product',
                        record_id=self.id,
                        record_name=self.display_name,
                        records_processed=1,
                        records_error=1,
                        error_details="API returned failure status"
                    )
                    
            except Exception as e:
                error_msg = f"Stock sync error for {marketplace.name}: {str(e)}"
                self.write({'stock_sync_error': error_msg})
                _logger.error(f"Error syncing stock for {self.display_name} to {marketplace.name}: {e}")
                
                # Log stock sync exception
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=marketplace.id,
                    operation_type='stock_sync',
                    status='error',
                    message=f"Exception during stock sync for variant: {self.display_name}",
                    record_model='product.product',
                    record_id=self.id,
                    record_name=self.display_name,
                    records_processed=1,
                    records_error=1,
                    error_details=error_msg
                )

    def action_manual_stock_sync(self):
        """Manual stock sync action for variants"""
        self.ensure_one()
        
        if not self.cartona_id:
            raise ValidationError(
                _("Cannot sync stock without External Variant ID. "
                  "Please set the External Variant ID first.")
            )
            
        self._trigger_stock_sync()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Stock Sync Started"),
                'message': _("Manual stock sync started for variant: %s") % self.display_name,
                'type': 'info',
            }
        }

    def action_manual_sync(self):
        """Manual sync action for product variants"""
        self.ensure_one()
        
        if not self.cartona_id:
            raise ValidationError(
                _("Cannot sync product variant without External Variant ID. "
                  "Please set the External Variant ID first.")
            )
            
        # Trigger both product and stock sync for the variant
        self._trigger_marketplace_sync()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sync Started"),
                'message': _("Manual sync started for variant: %s") % self.display_name,
                'type': 'info',
            }
        }

    def _trigger_marketplace_sync(self):
        """Trigger marketplace sync for this variant"""
        self.ensure_one()
        
        # Update sync status
        self.write({'marketplace_sync_status': 'syncing'})
        
        # Get active marketplace configurations
        marketplaces = self.env['marketplace.config'].get_active_marketplaces()
        
        if not marketplaces:
            self.write({
                'marketplace_sync_status': 'error',
                'marketplace_error_message': 'No active marketplace configurations found'
            })
            return
            
        for marketplace in marketplaces:
            try:
                # Get API client for this marketplace
                api_client = self.env['marketplace.api'].with_context(
                    marketplace_config_id=marketplace.id
                )
                
                # Sync product data first
                success = api_client.update_product(self.product_tmpl_id)
                
                if success:
                    # Then sync stock for this specific variant
                    api_client.update_product_stock(self)
                    
                    self.write({
                        'marketplace_sync_status': 'synced',
                        'marketplace_sync_date': fields.Datetime.now(),
                        'marketplace_error_message': False
                    })
                    _logger.info(f"Successfully synced variant {self.display_name} to {marketplace.name}")
                else:
                    self.write({
                        'marketplace_sync_status': 'error',
                        'marketplace_error_message': f'Failed to sync to {marketplace.name}'
                    })
                    _logger.warning(f"Failed to sync variant {self.display_name} to {marketplace.name}")
                    
            except Exception as e:
                error_msg = f"Sync error for {marketplace.name}: {str(e)}"
                self.write({
                    'marketplace_sync_status': 'error',
                    'marketplace_error_message': error_msg
                })
                _logger.error(f"Error syncing variant {self.display_name} to {marketplace.name}: {e}")

    @api.model
    def find_by_cartona_id(self, cartona_id, create_if_missing=False):
        """Find product variant by external ID"""
        if not cartona_id:
            return self.env['product.product']
            
        variant = self.search([('cartona_id', '=', cartona_id)], limit=1)
        
        if not variant and create_if_missing:
            # Try to find template first
            template = self.env['product.template'].find_by_cartona_id(
                cartona_id, create_if_missing=True
            )
            
            # If template exists, create variant
            if template:
                variant = self.create({
                    'product_tmpl_id': template.id,
                    'cartona_id': cartona_id,
                    'marketplace_sync_status': 'syncing'
                })
                _logger.info(f"Created variant for external ID: {cartona_id}")
            
        return variant

    def get_stock_info(self):
        """Get stock information for marketplace sync"""
        self.ensure_one()
        
        return {
            'product_id': self.cartona_id,
            'sku': self.default_code or self.barcode or str(self.id),
            'qty_available': self.qty_available,
            'virtual_available': self.virtual_available,
            'incoming_qty': self.incoming_qty,
            'outgoing_qty': self.outgoing_qty,
            'location_ids': self._get_stock_locations()
        }

    def _get_stock_locations(self):
        """Get stock locations for this product"""
        locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', 'in', [self.env.company.id, False])
        ])
        
        location_stock = []
        for location in locations:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', self.id),
                ('location_id', '=', location.id),
                ('quantity', '>', 0)
            ])
            
            if quants:
                total_qty = sum(quants.mapped('quantity'))
                location_stock.append({
                    'location_id': location.id,
                    'location_name': location.name,
                    'quantity': total_qty
                })
                
        return location_stock

    def action_reset_sync_status(self):
        """Reset sync status for product variants"""
        self.write({
            'marketplace_sync_status': 'not_synced',
            'marketplace_sync_date': False,
            'marketplace_error_message': False,
            'last_stock_sync_date': False,
            'stock_sync_error': False
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Status Reset"),
                'message': _("Sync status reset for %d variant(s)") % len(self),
                'type': 'info',
            }
        }
