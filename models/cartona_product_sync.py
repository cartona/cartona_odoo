from odoo import models, fields, api, _


class CartonaProductSync(models.Model):
    _name = 'cartona.product.sync'
    _description = 'Cartona Product Sync State (per variant and config)'
    _rec_name = 'display_name'
    _order = 'cartona_config_id, product_id'

    _sql_constraints = [
        (
            'product_config_uniq',
            'unique(product_id, cartona_config_id)',
            'Only one sync record per variant and Cartona configuration.',
        ),
    ]

    product_id = fields.Many2one(
        'product.product',
        required=True,
        ondelete='cascade',
        index=True,
    )
    cartona_config_id = fields.Many2one(
        'cartona.config',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='cartona_config_id.company_id',
        store=True,
        index=True,
    )
    sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
    ], default='not_synced', required=True, index=True)
    sync_date = fields.Datetime(readonly=True)
    sync_error = fields.Text(readonly=True)
    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('product_id', 'cartona_config_id')
    def _compute_display_name(self):
        for record in self:
            product_name = record.product_id.display_name or _('Variant')
            config_name = record.cartona_config_id.name or _('Config')
            record.display_name = f'{product_name} / {config_name}'

    @api.model
    def get_for_product_config(self, product, config, create=True):
        if not product or not config:
            return self.browse()
        sync_rec = self.sudo().search([
            ('product_id', '=', product.id),
            ('cartona_config_id', '=', config.id),
        ], limit=1)
        if not sync_rec and create:
            sync_rec = self.sudo().create({
                'product_id': product.id,
                'cartona_config_id': config.id,
                'sync_status': 'not_synced',
            })
        return sync_rec

    def mark_syncing(self):
        self.sudo().write({'sync_status': 'syncing', 'sync_error': False})

    def mark_success(self):
        self.sudo().write({
            'sync_status': 'synced',
            'sync_date': fields.Datetime.now(),
            'sync_error': False,
        })

    def mark_error(self, error=None):
        self.sudo().write({
            'sync_status': 'error',
            'sync_date': fields.Datetime.now(),
            'sync_error': error or False,
        })
