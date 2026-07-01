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
        """Race-safe get-or-create.

        Two jobs can legitimately try to create the sync row for the same
        (product, config) pair at the same time (e.g. a price change and a
        stock change on the same variant). A plain search-then-create would
        let both pass the search and then have the second create() raise
        UniqueViolation, failing the whole job. Using a raw upsert instead
        lets Postgres resolve the collision with no exception at all.

        NOTE: bypasses the ORM create() (no create()-hook side effects) -
        fine today since this model has no create() override or tracking.
        """
        if not product or not config:
            return self.browse()
        sync_rec = self.sudo().search([
            ('product_id', '=', product.id),
            ('cartona_config_id', '=', config.id),
        ], limit=1)
        if sync_rec or not create:
            return sync_rec
        self.env.cr.execute("""
            INSERT INTO cartona_product_sync
                (product_id, cartona_config_id, company_id, sync_status, create_date, write_date, create_uid, write_uid)
            VALUES (%s, %s, %s, 'not_synced', now(), now(), %s, %s)
            ON CONFLICT (product_id, cartona_config_id) DO NOTHING
            RETURNING id
        """, (product.id, config.id, config.company_id.id, self.env.uid, self.env.uid))
        row = self.env.cr.fetchone()
        if row:
            return self.browse(row[0])
        # Lost the race - the other job's row is already there.
        return self.sudo().search([
            ('product_id', '=', product.id),
            ('cartona_config_id', '=', config.id),
        ], limit=1)

    @api.model
    def ensure_for_products(self, products, config):
        """Bulk get-or-create for many products against one config.

        Replaces per-product get_for_product_config loops with a single
        query pass plus one bulk upsert for whatever is missing - both
        faster for large catalogs and race-safe under concurrent callers.
        """
        if not products or not config:
            return self.browse()
        existing = self.sudo().search([
            ('product_id', 'in', products.ids),
            ('cartona_config_id', '=', config.id),
        ])
        missing_ids = set(products.ids) - set(existing.product_id.ids)
        if missing_ids:
            self.env.cr.execute("""
                INSERT INTO cartona_product_sync
                    (product_id, cartona_config_id, company_id, sync_status, create_date, write_date, create_uid, write_uid)
                SELECT p, %(config_id)s, %(company_id)s, 'not_synced', now(), now(), %(uid)s, %(uid)s
                FROM unnest(%(product_ids)s) AS p
                ON CONFLICT (product_id, cartona_config_id) DO NOTHING
            """, {
                'config_id': config.id,
                'company_id': config.company_id.id,
                'uid': self.env.uid,
                'product_ids': list(missing_ids),
            })
        return self.sudo().search([
            ('product_id', 'in', products.ids),
            ('cartona_config_id', '=', config.id),
        ])

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
