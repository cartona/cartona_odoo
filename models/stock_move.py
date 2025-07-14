from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        """Override to trigger stock sync when moves are done"""
        _logger.debug(f"[StockMove._action_done] Starting with cancel_backorder={cancel_backorder}")
        
        result = super()._action_done(cancel_backorder)
        
        # Trigger stock sync for affected products
        if not self.env.context.get('skip_marketplace_sync'):
            _logger.debug(f"[StockMove._action_done] Marketplace sync not skipped, checking products")
            products_to_sync = self.mapped('product_id').filtered('marketplace_stock_sync_enabled')
            _logger.debug(f"[StockMove._action_done] Found {len(products_to_sync)} products to sync: {[p.name for p in products_to_sync]}")
            
            if products_to_sync:
                _logger.debug(f"[StockMove._action_done] Triggering stock sync for products")
                products_to_sync._trigger_stock_sync()
            else:
                _logger.debug(f"[StockMove._action_done] No products need stock sync")
        else:
            _logger.debug(f"[StockMove._action_done] Marketplace sync skipped due to context")
                
        _logger.debug(f"[StockMove._action_done] Completed successfully")
        return result

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    # Marketplace sync status for stock
    marketplace_stock_sync_status = fields.Selection([
        ('synced', 'Synced'),
        ('pending', 'Sync Pending'),
        ('error', 'Sync Error'),
    ], string="Stock Sync Status", default='synced')
    
    last_marketplace_sync = fields.Datetime(string="Last Stock Sync", readonly=True)
    stock_sync_error = fields.Text(string="Stock Sync Error", readonly=True)

    def write(self, vals):
        """Override write to trigger stock sync on quantity changes"""
        result = super().write(vals)
        
        # Check if quantity changed
        if 'quantity' in vals and not self.env.context.get('skip_marketplace_sync'):
            # Get unique products that need stock sync
            products_to_sync = self.mapped('product_id').filtered('marketplace_stock_sync_enabled')
            if products_to_sync:
                # Trigger stock sync for affected products
                products_to_sync._trigger_stock_sync()
                
        return result


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # Marketplace integration settings
    marketplace_sync_enabled = fields.Boolean(
        string="Include in Cartona Marketplace Sync",
        default=True,
        help="Include stock from this location in Cartona marketplace synchronization"
    )
    
    marketplace_location_code = fields.Char(
        string="Cartona Marketplace Location Code",
        help="External location code for Cartona marketplace integration"
    )


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_fill_move_quantity_with_demand(self):
        for picking in self:
            for move in picking.move_ids_without_package:
                move.quantity = move.product_uom_qty
