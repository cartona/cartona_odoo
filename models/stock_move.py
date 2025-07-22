from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        """Override to trigger stock sync when moves are done"""
        _logger.info(f"[CARTONA SYNC] StockMove._action_done called with cancel_backorder={cancel_backorder} for moves: {[m.display_name for m in self]}")
        result = super()._action_done(cancel_backorder)
        
        # Trigger stock sync for affected products
        if not self.env.context.get('skip_marketplace_sync'):
            _logger.info(f"[CARTONA SYNC] Marketplace sync not skipped, checking products")
            products_to_sync = self.mapped('product_id').filtered('marketplace_stock_sync_enabled')
            _logger.info(f"[CARTONA SYNC] Found {len(products_to_sync)} products to sync: {[p.name for p in products_to_sync]}")
            
            if products_to_sync:
                _logger.info(f"[CARTONA SYNC] Triggering stock sync for products")
                products_to_sync._trigger_stock_sync()
            else:
                _logger.info(f"[CARTONA SYNC] No products need stock sync")
        else:
            _logger.info(f"[CARTONA SYNC] Marketplace sync skipped due to context")
                
        _logger.info(f"[CARTONA SYNC] StockMove._action_done completed successfully")
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
        _logger.info(f"[CARTONA SYNC] stock.quant.write called for product(s) {[q.product_id.display_name for q in self]}, vals={vals}, context={self.env.context}")
        result = super().write(vals)
        if 'quantity' in vals and not self.env.context.get('skip_marketplace_sync'):
            products_to_sync = self.mapped('product_id').filtered('marketplace_stock_sync_enabled')
            if products_to_sync:
                _logger.info(f"[CARTONA SYNC] Will trigger stock sync for: {[p.display_name for p in products_to_sync]}")
                products_to_sync._trigger_stock_sync()
            else:
                _logger.info(f"[CARTONA SYNC] No products to sync or marketplace_stock_sync_enabled is False")
        else:
            if 'quantity' not in vals:
                _logger.info("[CARTONA SYNC] 'quantity' not in vals, not triggering sync")
            if self.env.context.get('skip_marketplace_sync'):
                _logger.info("[CARTONA SYNC] skip_marketplace_sync in context, not triggering sync")
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

    def button_validate(self):
        """Override button_validate to trigger Cartona sync when delivery is validated"""
        # Call the original button_validate method
        result = super().button_validate()
        
        # After validation, check if this is an outgoing delivery that became 'done'
        # and if it's related to a Cartona order
        if not self.env.context.get('skip_marketplace_sync'):
            for picking in self:
                if (picking.picking_type_code == 'outgoing' and 
                    picking.state == 'done' and 
                    picking.sale_id and 
                    picking.sale_id.cartona_id and 
                    picking.sale_id.marketplace_config_id):
                    
                    # Check if this order is delivered by supplier (business rule)
                    if picking.sale_id.delivered_by == 'delivered_by_supplier':
                        _logger.info(f"Delivery {picking.name} validated to 'done' - triggering Cartona sync for order {picking.sale_id.name}")
                        
                        # Trigger sync to update Cartona status to 'assigned_to_salesman'
                        picking.sale_id.with_delay(
                            channel='marketplace',
                            description=f"Sync delivery validation for order {picking.sale_id.name} to Cartona"
                        )._sync_delivery_validation_to_cartona()
                    else:
                        _logger.info(f"Delivery {picking.name} validated but order {picking.sale_id.name} is delivered_by_cartona - skipping sync")
        
        return result
