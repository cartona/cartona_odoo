from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def write(self, vals):
        result = super().write(vals)
        if 'list_price' in vals and not self.env.context.get('skip_cartona_sync'):
            variants = self.mapped('product_variant_ids').filtered(
                lambda variant: variant.active and variant.sale_ok
            )
            if variants:
                variants._trigger_cartona_sync('price')
        return result
