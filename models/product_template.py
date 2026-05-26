import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _sync_to_marketplaces(self):
        """Legacy queue_job method — sync moved to product variants."""
        _logger.info(
            'Skipping legacy template marketplace sync job for templates %s',
            self.ids,
        )

    def write(self, vals):
        result = super().write(vals)
        if 'list_price' in vals and not self.env.context.get('skip_cartona_sync'):
            variants = self.mapped('product_variant_ids').filtered(
                lambda variant: variant.active and variant.sale_ok
            )
            if variants:
                variants._trigger_cartona_sync('price')
        return result
