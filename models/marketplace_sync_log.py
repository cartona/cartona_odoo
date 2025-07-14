from odoo import models, fields, api, _
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class MarketplaceSyncLog(models.Model):
    _name = 'marketplace.sync.log'
    _description = 'Marketplace Synchronization Log'
    _order = 'create_date desc'
    _rec_name = 'operation_type'

    # Basic log information
    marketplace_config_id = fields.Many2one(
        'marketplace.config', 
        string="Marketplace", 
        required=True,
        ondelete='cascade'
    )
    
    operation_type = fields.Selection([
        ('product_sync', 'Product Sync'),
        ('stock_sync', 'Stock Sync'),
        ('order_pull', 'Order Pull'),
        ('status_sync', 'Status Sync'),
        ('connection_test', 'Connection Test'),
        ('bulk_operation', 'Bulk Operation'),
    ], string="Operation Type", required=True)
    
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ], string="Status", required=True)
    
    # Add state field for compatibility with queue systems
    state = fields.Selection([
        ('pending', 'Pending'),
        ('started', 'Started'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string="State", default='done', 
       help="Processing state of the log entry")
    
    # Record references
    record_model = fields.Char(string="Record Model")
    record_id = fields.Integer(string="Record ID")
    record_name = fields.Char(string="Record Name")
    
    # Log details
    message = fields.Text(string="Message", required=True)
    error_details = fields.Text(string="Error Details")
    request_data = fields.Text(string="Request Data")
    response_data = fields.Text(string="Response Data")
    
    # Processing information
    duration = fields.Float(string="Duration (seconds)")
    records_processed = fields.Integer(string="Records Processed", default=0)
    records_success = fields.Integer(string="Successful Records", default=0)
    records_error = fields.Integer(string="Failed Records", default=0)

    user_id = fields.Many2one('res.users', string="Triggered By", default=lambda self: self.env.uid)
    action_type = fields.Selection([
        ('manual', 'Manual'),
        ('automated', 'Automated'),
    ], string="Action Type", default='automated')

    @api.model
    def log_operation(self, marketplace_config_id, operation_type, status, message, 
                     record_model=None, record_id=None, record_name=None, 
                     error_details=None, request_data=None, response_data=None,
                     duration=None, records_processed=0, records_success=0, records_error=0):
        """Create a log entry for marketplace operations"""
        
        # Set state based on status
        state = 'failed' if status == 'error' else 'done'
        
        vals = {
            'marketplace_config_id': marketplace_config_id,
            'operation_type': operation_type,
            'status': status,
            'state': state,
            'message': message,
            'record_model': record_model,
            'record_id': record_id,
            'record_name': record_name,
            'error_details': error_details,
            'request_data': request_data,
            'response_data': response_data,
            'duration': duration,
            'records_processed': records_processed,
            'records_success': records_success,
            'records_error': records_error,
            'user_id': self.env.uid,
            'action_type': 'automated',
        }
        
        return self.create(vals)

    @api.model
    def log_product_sync(self, marketplace_config_id, product, status, message, **kwargs):
        """Log product synchronization operations"""
        return self.log_operation(
            marketplace_config_id=marketplace_config_id,
            operation_type='product_sync',
            status=status,
            message=message,
            record_model='product.template',
            record_id=product.id if product else None,
            record_name=product.name if product else None,
            **kwargs
        )

    @api.model
    def log_stock_sync(self, marketplace_config_id, product, status, message, **kwargs):
        """Log stock synchronization operations"""
        return self.log_operation(
            marketplace_config_id=marketplace_config_id,
            operation_type='stock_sync',
            status=status,
            message=message,
            record_model='product.product',
            record_id=product.id if product else None,
            record_name=product.display_name if product else None,
            **kwargs
        )

    @api.model
    def log_order_pull(self, marketplace_config_id, order, status, message, **kwargs):
        """Log order pull operations"""
        return self.log_operation(
            marketplace_config_id=marketplace_config_id,
            operation_type='order_pull',
            status=status,
            message=message,
            record_model='sale.order',
            record_id=order.id if order else None,
            record_name=order.name if order else None,
            **kwargs
        )

    @api.model
    def cleanup_old_logs(self, days=30):
        """Clean up old log entries"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff_date)])
        
        if old_logs:
            count = len(old_logs)
            old_logs.unlink()
            _logger.info(f"Cleaned up {count} old marketplace sync logs")
            
        return count

    def action_view_record(self):
        """View the related record"""
        self.ensure_one()
        
        if not self.record_model or not self.record_id:
            return
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.record_model,
            'res_id': self.record_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def get_log_summary(self):
        """Get summary statistics for logs"""
        self.ensure_one()
        
        domain = [('marketplace_config_id', '=', self.marketplace_config_id.id)]
        
        # Get counts by status
        total_logs = self.search_count(domain)
        success_logs = self.search_count(domain + [('status', '=', 'success')])
        error_logs = self.search_count(domain + [('status', '=', 'error')])
        warning_logs = self.search_count(domain + [('status', '=', 'warning')])
        
        # Get recent activity
        recent_domain = domain + [('create_date', '>=', fields.Datetime.now() - timedelta(hours=24))]
        recent_logs = self.search_count(recent_domain)
        
        return {
            'total_logs': total_logs,
            'success_logs': success_logs,
            'error_logs': error_logs,
            'warning_logs': warning_logs,
            'recent_logs': recent_logs,
            'success_rate': (success_logs / total_logs * 100) if total_logs > 0 else 0,
        }
