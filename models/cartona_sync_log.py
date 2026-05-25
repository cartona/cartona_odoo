from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class CartonaSyncLog(models.Model):
    _name = 'cartona.sync.log'
    _description = 'Cartona Synchronization Log'
    _order = 'create_date desc'
    _rec_name = 'operation_type'

    cartona_config_id = fields.Many2one(
        'cartona.config',
        required=True,
        ondelete='cascade',
    )
    operation_type = fields.Selection([
        ('product_sync', 'Product Sync'),
        ('stock_sync', 'Stock Sync'),
        ('order_pull', 'Order Pull'),
        ('status_sync', 'Status Sync'),
        ('connection_test', 'Connection Test'),
        ('bulk_operation', 'Bulk Operation'),
    ], required=True)
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ], required=True)

    record_model = fields.Char()
    record_id = fields.Integer()
    record_name = fields.Char()
    message = fields.Text(required=True)
    error_details = fields.Text()
    request_data = fields.Text()
    response_data = fields.Text()
    duration = fields.Float(string='Duration (seconds)')
    records_processed = fields.Integer(default=0)
    records_success = fields.Integer(default=0)
    records_error = fields.Integer(default=0)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.uid)
    action_type = fields.Selection([
        ('manual', 'Manual'),
        ('automated', 'Automated'),
    ], default='automated')
    line_ids = fields.One2many('cartona.sync.log.line', 'sync_log_id', string='Details')
    detail_count = fields.Integer(compute='_compute_detail_count')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.context.get('cartona_sync_log_internal'):
            raise AccessError(_('Sync logs cannot be created manually.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.context.get('cartona_sync_log_internal'):
            raise AccessError(_('Sync logs are read-only.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.context.get('cartona_sync_log_internal'):
            raise AccessError(_('Sync logs cannot be deleted manually.'))
        return super().unlink()

    def copy(self, default=None):
        raise AccessError(_('Sync logs cannot be duplicated.'))

    @api.depends('line_ids')
    def _compute_detail_count(self):
        for record in self:
            record.detail_count = len(record.line_ids)

    @api.model
    def log_operation(self, cartona_config_id, operation_type, status, message, line_vals_list=None, **kwargs):
        vals = {
            'cartona_config_id': cartona_config_id,
            'operation_type': operation_type,
            'status': status,
            'message': message,
            'user_id': self.env.uid,
            **kwargs,
        }
        if 'action_type' not in vals:
            vals['action_type'] = 'automated'
        log = self.sudo().create(vals)
        if line_vals_list:
            self.env['cartona.sync.log.line'].sudo().create([
                {**line_vals, 'sync_log_id': log.id}
                for line_vals in line_vals_list
            ])
        return log

    @api.model
    def log_product_sync(self, cartona_config_id, variant, status, message, **kwargs):
        operation_type = kwargs.pop('operation_type', 'product_sync')
        return self.log_operation(
            cartona_config_id=cartona_config_id,
            operation_type=operation_type,
            status=status,
            message=message,
            record_model='product.product',
            record_id=variant.id if variant else None,
            record_name=variant.display_name if variant else None,
            **kwargs,
        )

    @api.model
    def cleanup_old_logs(self, days=30):
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff)])
        count = len(old_logs)
        if old_logs:
            old_logs.with_context(cartona_sync_log_internal=True).sudo().unlink()
            _logger.info('Cleaned up %s old Cartona sync logs', count)
        return count

    def action_view_record(self):
        self.ensure_one()
        if not self.record_model or not self.record_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.record_model,
            'res_id': self.record_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_detail_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync Log Details'),
            'res_model': 'cartona.sync.log.line',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('cartona_odoo.view_cartona_sync_log_line_list').id, 'list'),
                (self.env.ref('cartona_odoo.view_cartona_sync_log_line_form').id, 'form'),
            ],
            'search_view_id': self.env.ref('cartona_odoo.view_cartona_sync_log_line_search').id,
            'domain': [('sync_log_id', '=', self.id)],
            'target': 'new',
        }
