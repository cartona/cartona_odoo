from odoo import models, fields, _
import logging

_logger = logging.getLogger(__name__)


class CartonaDeliveryOtpWizard(models.TransientModel):
    _name = 'cartona.delivery.otp.wizard'
    _description = 'Retailer OTP Confirmation for Cartona Delivery'

    picking_id = fields.Many2one('stock.picking', required=True)
    order_id = fields.Many2one('sale.order', related='picking_id.sale_id')
    cartona_delivery_otp = fields.Char(string='Retailer OTP')

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        order.cartona_delivery_otp = self.cartona_delivery_otp
        order._sync_delivery_validation_to_cartona()

        if order.cartona_sync_status != 'synced':
            order.cartona_delivery_otp = False
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Delivery Blocked'),
                    'message': order.cartona_error_message or _(
                        'Cartona rejected the delivery confirmation. Picking was NOT validated.'
                    ),
                    'type': 'danger',
                    'sticky': True,
                },
            }

        result = self.picking_id.with_context(
            skip_otp_check=True,
            skip_cartona_delivery_sync=True,
        ).button_validate()

        if not result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Delivery Confirmed'),
                    'message': _('Order %s confirmed and synced to Cartona successfully.') % order.name,
                    'type': 'success',
                },
            }
        return result
