from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Universal External Product ID - works with any marketplace
    cartona_id = fields.Char(
        string="External Product ID",
        help="Universal external product identifier for marketplace integration. "
             "Works with Cartona, Amazon ASIN, eBay Item ID, Shopify Product ID, etc.",
        index=True,  # For fast lookups
        copy=False   # Don't copy on duplicate
    )
    
    delivered_by = fields.Selection([
        ('delivered_by_supplier', 'Delivered by Supplier'),
        ('delivered_by_cartona', 'Delivered by Cartona')
    ], string='Delivered By', default='delivered_by_supplier',
       help="Determines who is responsible for order fulfillment and status updates.")
    
    # Marketplace Sync Status
    marketplace_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
        ('partial', 'Partially Synced'),  # Some marketplaces synced, others failed
    ], string="Sync Status", default='not_synced', help="Product synchronization status")
    
    marketplace_sync_date = fields.Datetime(string="Last Sync Date", readonly=True)
    marketplace_error_message = fields.Text(string="Sync Error", readonly=True)
    
    # Marketplace-specific fields
    marketplace_ids = fields.One2many(
        'product.marketplace.link', 'product_tmpl_id', 
        string="Cartona Marketplace Links",
        help="Links to this product in different Cartona marketplaces"
    )
    
    # Control fields
    marketplace_sync_enabled = fields.Boolean(
        string="Enable Cartona Marketplace Sync", 
        default=True,
        help="Enable automatic synchronization to Cartona marketplaces"
    )
    
    @api.constrains('cartona_id')
    def _check_cartona_id_unique(self):
        """Ensure cartona_id is unique when set"""
        for record in self:
            if record.cartona_id:
                existing = self.search([
                    ('cartona_id', '=', record.cartona_id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        _("External Product ID '%s' already exists on product '%s'. "
                          "Each product must have a unique external ID.") % 
                        (record.cartona_id, existing[0].name)
                    )

    def write(self, vals):
        """Override write to trigger marketplace sync on price/name changes"""

        # Check if we need to sync to marketplaces
        sync_fields = ['list_price']
        needs_sync = any(field in vals for field in sync_fields)
        
        result = super().write(vals)
        
        skip_sync = self.env.context.get('skip_marketplace_sync')
        
        if needs_sync and not skip_sync:
            self._trigger_marketplace_sync('product_update')
            
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to optionally sync new products"""
        records = super().create(vals_list)
        
        if not self.env.context.get('skip_marketplace_sync'):
            records._trigger_marketplace_sync('product_create')
            
        return records

    def _trigger_marketplace_sync(self, sync_type='product_update'):
        """Trigger marketplace synchronization using queue jobs"""
        if not self.env.context.get('skip_marketplace_sync'):
            for record in self:
                if record.marketplace_sync_enabled:
                    # Queue job for async processing
                    record.with_delay(
                        channel='marketplace',
                        description=f"Sync product {record.name} to marketplace"
                    )._sync_to_marketplaces(sync_type)

    def _sync_to_marketplaces(self, sync_type='product_update'):
        """Sync this product to all active marketplaces using bulk_update_products for correct payload"""
        self.ensure_one()
        # Get active marketplace configurations
        marketplaces = self.env['marketplace.config'].get_active_marketplaces()
        if not marketplaces:
            _logger.info("No active marketplaces configured for sync")
            return
        sync_results = []
        for marketplace in marketplaces:
            try:
                # Log the start of individual product sync
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=marketplace.id,
                    operation_type='product_sync',
                    status='info',
                    message=f"Starting {sync_type} for product: {self.name}",
                    record_model='product.template',
                    record_id=self.id,
                    record_name=self.name
                )
                # Get API client for this marketplace
                api_client = self.env['marketplace.api'].with_context(
                    marketplace_config_id=marketplace.id
                )
                # Always use bulk_update_products for correct endpoint/payload
                success = api_client.bulk_update_products([self])
                sync_results.append((marketplace.name, success))
                if success:
                    _logger.info(f"Successfully synced product {self.name} to {marketplace.name}")
                    # Log successful sync
                    self.env['marketplace.sync.log'].log_operation(
                        marketplace_config_id=marketplace.id,
                        operation_type='product_sync',
                        status='success',
                        message=f"Successfully completed {sync_type} for product: {self.name}",
                        record_model='product.template',
                        record_id=self.id,
                        record_name=self.name,
                        records_processed=1,
                        records_success=1
                    )
                else:
                    _logger.warning(f"Failed to sync product {self.name} to {marketplace.name}")
                    # Log failed sync
                    self.env['marketplace.sync.log'].log_operation(
                        marketplace_config_id=marketplace.id,
                        operation_type='product_sync',
                        status='error',
                        message=f"Failed {sync_type} for product: {self.name}",
                        record_model='product.template',
                        record_id=self.id,
                        record_name=self.name,
                        records_processed=1,
                        records_error=1,
                        error_details="API returned failure status"
                    )
            except Exception as e:
                error_msg = f"Error syncing product {self.name} to {marketplace.name}: {e}"
                _logger.error(error_msg)
                # Log exception
                self.env['marketplace.sync.log'].log_operation(
                    marketplace_config_id=marketplace.id,
                    operation_type='product_sync',
                    status='error',
                    message=f"Exception during {sync_type} for product: {self.name}",
                    record_model='product.template',
                    record_id=self.id,
                    record_name=self.name,
                    records_processed=1,
                    records_error=1,
                    error_details=error_msg
                )
                sync_results.append((marketplace.name, False))
        # Update sync status based on results
        self._update_sync_status(sync_results)

    def _update_sync_status(self, sync_results):
        """Update product sync status based on marketplace sync results"""
        self.ensure_one()
        
        if not sync_results:
            return
            
        successful_syncs = sum(1 for name, success in sync_results if success)
        total_syncs = len(sync_results)
        
        if successful_syncs == 0:
            status = 'error'
            error_msg = "Failed to sync to all marketplaces: " + ", ".join(
                name for name, success in sync_results if not success
            )
        elif successful_syncs == total_syncs:
            status = 'synced'
            error_msg = False
        else:
            status = 'partial'
            failed_marketplaces = [name for name, success in sync_results if not success]
            error_msg = f"Failed to sync to: {', '.join(failed_marketplaces)}"
            
        self.write({
            'marketplace_sync_status': status,
            'marketplace_sync_date': fields.Datetime.now(),
            'marketplace_error_message': error_msg
        })

    def action_manual_sync(self):
        """Manual sync action for products"""
        self.ensure_one()
        
        if not self.cartona_id:
            raise ValidationError(
                _("Cannot sync product without External Product ID. "
                  "Please set the External Product ID first.")
            )
            
        self._trigger_marketplace_sync('manual_sync')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sync Started"),
                'message': _("Manual sync started for product: %s") % self.name,
                'type': 'info',
            }
        }

    def action_reset_sync_status(self):
        """Reset sync status for products"""
        self.write({
            'marketplace_sync_status': 'not_synced',
            'marketplace_sync_date': False,
            'marketplace_error_message': False
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Status Reset"),
                'message': _("Sync status reset for %d product(s)") % len(self),
                'type': 'info',
            }
        }

    @api.model
    def find_by_cartona_id(self, cartona_id, create_if_missing=False):
        """Find product by external ID, optionally create if missing"""
        if not cartona_id:
            return self.env['product.template']
            
        product = self.search([('cartona_id', '=', cartona_id)], limit=1)
        
        if not product and create_if_missing:
            # Create placeholder product - will be updated by sync
            product = self.create({
                'name': f'Marketplace Product {cartona_id}',
                'cartona_id': cartona_id,
                'type': 'consu',  # Set product type to consumable
                'is_storable': True,  # Enable storable tracking
                'marketplace_sync_status': 'syncing'
            })
            _logger.info(f"Created placeholder product for external ID: {cartona_id}")
            
        return product


class ProductMarketplaceLink(models.Model):
    """Track product links across multiple marketplaces"""
    _name = 'product.marketplace.link'
    _description = 'Product Marketplace Links'
    _rec_name = 'marketplace_config_id'

    product_tmpl_id = fields.Many2one('product.template', required=True, ondelete='cascade')
    marketplace_config_id = fields.Many2one('marketplace.config', required=True, ondelete='cascade')
    external_id = fields.Char(string="External Product ID", required=True, index=True)
    last_sync_date = fields.Datetime(string="Last Sync Date")
    sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('error', 'Error'),
    ], default='pending')
    error_message = fields.Text(string="Error Message")

    _sql_constraints = [
        ('unique_product_marketplace', 
         'unique(product_tmpl_id, marketplace_config_id)', 
         'Product can only be linked once per marketplace'),
        ('unique_external_id_marketplace',
         'unique(external_id, marketplace_config_id)',
         'External ID must be unique per marketplace'),
    ]
