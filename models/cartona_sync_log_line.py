from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class CartonaSyncLogLine(models.Model):
    _name = 'cartona.sync.log.line'
    _description = 'Cartona Sync Log Detail'
    _order = 'id'

    sync_log_id = fields.Many2one(
        'cartona.sync.log',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
    )
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ], required=True, readonly=True)
    entry_type = fields.Selection([
        ('order', 'Order'),
        ('order_line', 'Order Line'),
        ('product', 'Product'),
        ('system', 'System'),
    ], required=True, default='system', readonly=True)
    error_code = fields.Selection([
        ('missing_internal_product_id', 'Missing internal_product_id'),
        ('invalid_internal_product_id', 'Invalid internal_product_id'),
        ('variant_not_found', 'Odoo variant not found'),
        ('variant_not_available', 'Odoo variant not available'),
        ('missing_order_fields', 'Missing order fields'),
        ('invalid_order_details', 'Invalid order details'),
        ('no_valid_order_lines', 'No valid order lines'),
        ('customer_error', 'Customer error'),
        ('state_transition_error', 'State transition error'),
        ('unexpected_error', 'Unexpected error'),
        ('other', 'Other'),
    ], readonly=True)
    cartona_order_id = fields.Char(string='Cartona Order ID', readonly=True)
    cartona_order_number = fields.Char(
        string='Cartona Order #',
        readonly=True,
        help='Cartona order number from the API (receipt_id, or hashed_id when receipt_id is missing).',
    )
    cartona_line_id = fields.Char(
        string='Cartona Order Detail #',
        readonly=True,
        help='Cartona order detail id. Populated only for order line log entries.',
    )
    internal_product_id = fields.Char(readonly=True)
    record_model = fields.Char(readonly=True)
    record_id = fields.Integer(readonly=True)
    record_name = fields.Char(readonly=True)
    message = fields.Text(required=True, readonly=True)
    request_data = fields.Text(readonly=True)
    response_data = fields.Text(readonly=True)
    sync_log_create_date = fields.Datetime(
        related='sync_log_id.create_date',
        string='Log Date',
        readonly=True,
    )
    sync_log_operation = fields.Selection(
        related='sync_log_id.operation_type',
        string='Operation',
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.context.get('cartona_sync_log_internal'):
            raise AccessError(_('Sync log details cannot be created manually.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.context.get('cartona_sync_log_internal'):
            raise AccessError(_('Sync log details are read-only.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.context.get('cartona_sync_log_internal'):
            raise AccessError(_('Sync log details cannot be deleted manually.'))
        return super().unlink()

    def copy(self, default=None):
        raise AccessError(_('Sync log details cannot be duplicated.'))
