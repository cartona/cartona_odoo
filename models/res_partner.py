from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Universal External Partner ID (with retailer_ prefix for customers)
    cartona_id = fields.Char(
        string="External Partner ID",
        help="Universal external partner identifier for marketplace integration. "
             "Format: 'retailer_XXXXX' for customers, regular ID for suppliers. "
             "Works with Cartona, Amazon, eBay, Shopify customer IDs, etc.",
        index=True,
        copy=False
    )
    
    # Partner sync status
    marketplace_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
    ], string="Partner Sync Status", default='not_synced')
    
    marketplace_sync_date = fields.Datetime(string="Last Partner Sync", readonly=True)
    marketplace_error_message = fields.Text(string="Partner Sync Error", readonly=True)
    
    # Partner origin tracking
    marketplace_source = fields.Many2one(
        'marketplace.config', 
        string="Source Cartona Marketplace",
        help="The Cartona marketplace where this partner was first created"
    )
    
    # Customer-specific fields for marketplace integration
    is_marketplace_customer = fields.Boolean(
        string="Cartona Marketplace Customer",
        help="This partner was created from a marketplace order"
    )
    
    last_customer_sync_date = fields.Datetime(
        string="Last Customer Sync",
        help="Last time customer data was synchronized"
    )
    
    # Partner type classification
    partner_type_marketplace = fields.Selection([
        ('customer', 'Marketplace Customer'),
        ('supplier', 'Marketplace Supplier'),
        ('both', 'Customer & Supplier'),
    ], string="Marketplace Type", help="Partner role in marketplace integration")

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set marketplace type and sync status"""
        for vals in vals_list:
            # Auto-detect marketplace customer based on cartona_id format
            cartona_id = vals.get('cartona_id')
            if cartona_id and isinstance(cartona_id, str) and cartona_id.startswith('retailer_'):
                vals.update({
                    'is_marketplace_customer': True,
                    'partner_type_marketplace': 'customer',
                    'marketplace_sync_status': 'synced'  # Created from marketplace
                })
                
        return super().create(vals_list)

    def write(self, vals):
        """Override write to update sync status on important changes"""
        # Check if important customer data changed
        sync_fields = ['name', 'email', 'phone', 'street', 'city', 'zip', 'country_id']
        needs_sync = any(field in vals for field in sync_fields)
        
        result = super().write(vals)
        
        if needs_sync and not self.env.context.get('skip_marketplace_sync'):
            # Update sync status to indicate changes need to be pushed
            self.filtered('is_marketplace_customer').write({
                'marketplace_sync_status': 'syncing'
            })
            
        return result

    @api.model
    def find_or_create_marketplace_customer(self, customer_data, marketplace_config):
        """Find existing customer or create new one from marketplace data"""
        
        # Handle Cartona retailer structure
        if not customer_data:
            _logger.error("No customer data provided")
            return None
            
        _logger.info(f"Processing customer data: {customer_data}")
            
        # Try multiple field names for retailer name
        retailer_name = (customer_data.get('retailer_name') or 
                        customer_data.get('name') or 
                        customer_data.get('customer_name') or
                        customer_data.get('retailer_name'))
        
        # Try multiple field names for retailer number/phone
        retailer_number = (customer_data.get('retailer_number') or 
                          customer_data.get('phone') or 
                          customer_data.get('retailer_phone') or
                          customer_data.get('retailer_code'))
        
        # Try multiple field names for retailer code/ID
        retailer_code = (customer_data.get('retailer_code') or 
                        customer_data.get('external_id') or
                        customer_data.get('id') or
                        customer_data.get('retailer_id'))
        
        # Create a unique identifier - use any available data
        if retailer_code:
            external_id = f"retailer_{retailer_code}"
        elif retailer_name and retailer_number:
            external_id = f"retailer_{retailer_name}_{retailer_number}".replace('+', '').replace(' ', '_')
        elif retailer_name:
            external_id = f"retailer_{retailer_name}".replace(' ', '_')
        elif retailer_number:
            external_id = f"retailer_{retailer_number}".replace('+', '')
        else:
            # Last resort - create a generic customer
            _logger.warning("No retailer identifiers found, creating generic customer")
            external_id = f"retailer_unknown_{fields.Datetime.now().timestamp()}"
            retailer_name = "Cartona Customer"
            
        _logger.info(f"Generated external_id: {external_id}")
            
        # Try to find existing customer
        partner = self.search([
            '|', '|',
            ('cartona_id', '=', external_id),
            ('phone', '=', retailer_number),
            ('name', '=', retailer_name)
        ], limit=1)
        
        if partner:
            _logger.info(f"Found existing partner: {partner.name}")
            # Update existing customer data
            partner._update_from_marketplace_data(customer_data, marketplace_config)
            return partner
        
        # Create new customer
        partner_vals = self._prepare_customer_from_marketplace_data(
            customer_data, marketplace_config, external_id, retailer_name, retailer_number
        )
        
        partner = self.create(partner_vals)
        
        _logger.info(f"Created new marketplace customer {partner.name} with ID {external_id}")
        return partner

    def _prepare_customer_from_marketplace_data(self, customer_data, marketplace_config, external_id, retailer_name=None, retailer_number=None):
        """Prepare partner values from Cartona retailer data"""
        
        # Use provided parameters or extract from data
        name = retailer_name or customer_data.get('retailer_name') or customer_data.get('name') or 'Cartona Customer'
        phone = retailer_number or customer_data.get('retailer_number') or customer_data.get('phone')
        
        vals = {
            'name': name,
            'phone': phone,
            'mobile': customer_data.get('retailer_number2') or customer_data.get('mobile'),
            'email': customer_data.get('retailer_email') or customer_data.get('email'),
            'street': customer_data.get('retailer_address') or customer_data.get('street') or customer_data.get('address'),
            'comment': customer_data.get('address_notes') or customer_data.get('notes'),
            'is_company': False,
            'customer_rank': 1,  # Mark as customer
            'supplier_rank': 0,
            
            # Marketplace-specific fields
            'cartona_id': external_id,
            'is_marketplace_customer': True,
            'marketplace_source': marketplace_config.id,
            'partner_type_marketplace': 'customer',
            'marketplace_sync_status': 'synced',
            'marketplace_sync_date': fields.Datetime.now(),
            
            # Default country for Cartona (Egypt)
            'country_id': self._find_country_id('Egypt'),
        }
        
        # Remove None values
        cleaned_vals = {k: v for k, v in vals.items() if v is not None}
        _logger.info(f"Partner values to create: {cleaned_vals}")
        
        return cleaned_vals

    def _update_from_marketplace_data(self, customer_data, marketplace_config):
        """Update existing customer with fresh marketplace data"""
        self.ensure_one()
        
        address_data = customer_data.get('address', {}) or customer_data.get('shipping_address', {})
        
        update_vals = {
            'last_customer_sync_date': fields.Datetime.now(),
            'marketplace_sync_status': 'synced'
        }
        
        # Update basic info if provided
        if customer_data.get('name'):
            update_vals['name'] = customer_data['name']
        if customer_data.get('email'):
            update_vals['email'] = customer_data['email']
        if customer_data.get('phone'):
            update_vals['phone'] = customer_data['phone']
            
        # Update address if provided
        if address_data:
            if address_data.get('street'):
                update_vals['street'] = address_data['street']
            if address_data.get('city'):
                update_vals['city'] = address_data['city']
            if address_data.get('zip'):
                update_vals['zip'] = address_data['zip']
                
        self.write(update_vals)
        _logger.info(f"Updated marketplace customer {self.name}")

    def _find_state_id(self, state_name):
        """Find state ID by name"""
        if not state_name:
            return False
            
        state = self.env['res.country.state'].search([
            ('name', 'ilike', state_name)
        ], limit=1)
        
        return state.id if state else False

    def _find_country_id(self, country_name):
        """Find country ID by name or code"""
        if not country_name:
            return False
            
        # Try by code first (e.g., 'US', 'GB')
        country = self.env['res.country'].search([
            ('code', '=', country_name.upper())
        ], limit=1)
        
        if not country:
            # Try by name
            country = self.env['res.country'].search([
                ('name', 'ilike', country_name)
            ], limit=1)
            
        return country.id if country else False

    @api.model
    def find_by_cartona_id(self, cartona_id):
        """Find partner by external ID"""
        if not cartona_id:
            return self.env['res.partner']
            
        return self.search([('cartona_id', '=', cartona_id)], limit=1)

    def action_sync_to_marketplace(self):
        """Manual sync customer to marketplace"""
        self.ensure_one()
        
        if not self.cartona_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Not Available"),
                    'message': _("Customer sync requires External Partner ID"),
                    'type': 'warning',
                }
            }
        
        # Trigger sync (implementation would depend on marketplace requirements)
        self.write({'marketplace_sync_status': 'syncing'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sync Started"),
                'message': _("Customer sync started for: %s") % self.name,
                'type': 'info',
            }
        }
