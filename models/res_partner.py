from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cartona_id = fields.Char(
        string='External Partner ID',
        index=True,
        copy=False,
    )
    cartona_config_id = fields.Many2one(
        'cartona.config',
        string='Cartona Configuration',
    )
    is_cartona_customer = fields.Boolean(
        help='This partner was created from a Cartona order',
    )
    cartona_sync_date = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            cartona_id = vals.get('cartona_id')
            if cartona_id and isinstance(cartona_id, str) and cartona_id.startswith('retailer_'):
                vals.setdefault('is_cartona_customer', True)
        return super().create(vals_list)

    @api.model
    def find_or_create_cartona_customer(self, customer_data, cartona_config):
        if not customer_data:
            return None

        retailer_name = (
            customer_data.get('retailer_name')
            or customer_data.get('name')
            or 'Cartona Customer'
        )
        retailer_number = (
            customer_data.get('retailer_number')
            or customer_data.get('phone')
            or customer_data.get('retailer_code')
        )
        retailer_code = (
            customer_data.get('retailer_code')
            or customer_data.get('external_id')
            or customer_data.get('id')
            or customer_data.get('retailer_id')
        )

        if retailer_code:
            external_id = f'retailer_{retailer_code}'
        elif retailer_name and retailer_number:
            external_id = f'retailer_{retailer_name}_{retailer_number}'.replace('+', '').replace(' ', '_')
        elif retailer_name:
            external_id = f'retailer_{retailer_name}'.replace(' ', '_')
        elif retailer_number:
            external_id = f'retailer_{retailer_number}'.replace('+', '')
        else:
            external_id = f'retailer_unknown_{fields.Datetime.now().timestamp()}'
            retailer_name = 'Cartona Customer'

        partner = self.with_context(skip_cartona_sync=True).search([
            ('company_id', 'in', [self.env.company.id, False]),
            '|', '|',
            ('cartona_id', '=', external_id),
            ('phone', '=', retailer_number),
            ('name', '=', retailer_name),
        ], limit=1)

        if partner:
            partner._update_from_cartona_data(customer_data, cartona_config)
            return partner

        vals = {
            'name': retailer_name,
            'company_id': self.env.company.id,
            'phone': retailer_number,
            'email': customer_data.get('retailer_email') or customer_data.get('email'),
            'street': customer_data.get('retailer_address') or customer_data.get('street'),
            'is_company': False,
            'customer_rank': 1,
            'cartona_id': external_id,
            'is_cartona_customer': True,
            'cartona_config_id': cartona_config.id,
            'cartona_sync_date': fields.Datetime.now(),
            'country_id': self._find_country_id('Egypt'),
        }
        return self.with_context(skip_cartona_sync=True).create(
            {k: v for k, v in vals.items() if v is not None}
        )

    def _update_from_cartona_data(self, customer_data, cartona_config):
        self.ensure_one()
        update_vals = {
            'cartona_sync_date': fields.Datetime.now(),
            'cartona_config_id': cartona_config.id,
        }
        if customer_data.get('name'):
            update_vals['name'] = customer_data['name']
        if customer_data.get('email'):
            update_vals['email'] = customer_data['email']
        if customer_data.get('phone'):
            update_vals['phone'] = customer_data['phone']
        self.with_context(skip_cartona_sync=True).write(update_vals)

    def _find_country_id(self, country_name):
        if not country_name:
            return False
        country = self.env['res.country'].search([
            ('code', '=', country_name.upper()),
        ], limit=1)
        if not country:
            country = self.env['res.country'].search([
                ('name', 'ilike', country_name),
            ], limit=1)
        return country.id if country else False
