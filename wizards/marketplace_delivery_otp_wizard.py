from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MarketplaceDeliveryOtpWizard(models.TransientModel):
    _name = 'marketplace.delivery.otp.wizard'
    _description = 'Retailer OTP Confirmation for Cartona Delivery'

    picking_id = fields.Many2one('stock.picking', required=True)
    order_id = fields.Many2one('sale.order', related='picking_id.sale_id')
    marketplace_delivery_otp = fields.Char(string="Retailer OTP")

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id

        # Store OTP on the order so _sync_delivery_validation_to_cartona can include it
        order.marketplace_delivery_otp = self.marketplace_delivery_otp

        # Call Cartona FIRST — only proceed with picking validation if Cartona accepts.
        # This prevents marking a delivery as done in Odoo when Cartona rejects the OTP.
        order._sync_delivery_validation_to_cartona()

        if order.marketplace_sync_status != 'synced':
            # Cartona rejected (wrong OTP, API error, etc.) — clear OTP and abort
            order.marketplace_delivery_otp = False
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Delivery Blocked'),
                    'message': order.marketplace_error_message or _('Cartona rejected the delivery confirmation. Picking was NOT validated.'),
                    'type': 'danger',
                    'sticky': True,
                },
            }

        # Cartona accepted — now validate the picking in Odoo.
        # skip_marketplace_delivery_sync=True since Cartona is already updated.
        result = self.picking_id.with_context(
            skip_otp_check=True,
            skip_marketplace_delivery_sync=True,
        ).button_validate()

        if not result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Delivery Confirmed'),
                    'message': _('Order %s confirmed and synced to Cartona successfully.') % order.name,
                    'type': 'success',
                    'sticky': False,
                },
            }

        # button_validate returned a sub-action (e.g. backorder dialog) — hand it off
        return result
