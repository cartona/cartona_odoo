from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MarketplaceDeliveryOtpWizard(models.TransientModel):
    _name = 'marketplace.delivery.otp.wizard'
    _description = 'Retailer OTP Confirmation for Cartona Delivery'

    picking_id = fields.Many2one('stock.picking', required=True)
    order_id = fields.Many2one('sale.order', related='picking_id.sale_id')
    marketplace_delivery_otp = fields.Char(string="Retailer OTP", required=True)

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        order.marketplace_delivery_otp = self.marketplace_delivery_otp

        # skip_marketplace_delivery_sync suppresses only the delivery status enqueue
        # in button_validate — stock sync (StockMove._action_done, StockQuant.write)
        # still fires because those gate on skip_marketplace_sync, not this flag.
        result = self.picking_id.with_context(
            skip_otp_check=True,
            skip_marketplace_delivery_sync=True,
        ).button_validate()

        # If button_validate returned a sub-wizard (e.g. backorder dialog),
        # the picking is not done yet — hand off to that wizard and skip sync.
        if isinstance(result, dict) and result.get('res_model'):
            return result

        # Only sync if the picking actually became done
        if self.picking_id.state != 'done':
            return result

        # Synchronous call: admin sees success or Cartona error right away
        order._sync_delivery_validation_to_cartona()

        if order.marketplace_sync_status == 'synced':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Delivery Confirmed'),
                    'message': _('Order %s delivery synced to Cartona successfully.') % order.name,
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Cartona Sync Failed'),
                    'message': order.marketplace_error_message or _('Unknown error from Cartona API.'),
                    'type': 'danger',
                    'sticky': True,
                },
            }
