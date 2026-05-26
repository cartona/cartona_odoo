from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        result = super()._action_done(cancel_backorder)
        if not self.env.context.get('skip_cartona_sync'):
            products = self.mapped('product_id')
            if products:
                products._trigger_cartona_sync('stock')
        return result


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def write(self, vals):
        result = super().write(vals)
        if 'quantity' in vals and not self.env.context.get('skip_cartona_sync'):
            products = self.mapped('product_id')
            if products:
                products._trigger_cartona_sync('stock')
        return result


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_fill_move_quantity_with_demand(self):
        for picking in self:
            for move in picking.move_ids_without_package:
                move.quantity = move.product_uom_qty

    def button_validate(self):
        if not self.env.context.get('skip_otp_check'):
            for picking in self:
                order = picking.sale_id
                if (picking.picking_type_code == 'outgoing'
                        and picking.state not in ('done', 'cancel')
                        and order
                        and order.is_cartona_order
                        and order.delivered_by == 'delivered_by_supplier'
                        and order.cartona_payment_method in ('installment', 'wallet_top_up')
                        and not order.cartona_delivery_otp):
                    wizard = self.env['cartona.delivery.otp.wizard'].create({
                        'picking_id': picking.id,
                    })
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'cartona.delivery.otp.wizard',
                        'res_id': wizard.id,
                        'view_mode': 'form',
                        'target': 'new',
                        'name': 'Enter Retailer OTP',
                    }

        result = super().button_validate()

        skip_sync = (
            self.env.context.get('skip_cartona_sync')
            or self.env.context.get('skip_cartona_delivery_sync')
        )
        if not skip_sync:
            for picking in self:
                order = picking.sale_id
                if (picking.picking_type_code == 'outgoing'
                        and picking.state == 'done'
                        and order
                        and order.cartona_id
                        and order.cartona_config_id
                        and order.cartona_config_id.is_cartona_sync_enabled
                        and order.delivered_by == 'delivered_by_supplier'):
                    order.with_context(
                        cartona_config_id=order.cartona_config_id.id,
                    ).with_delay(
                        channel='cartona',
                        description=f'Sync delivery validation for order {order.name}',
                    )._sync_delivery_validation_to_cartona()
        return result
