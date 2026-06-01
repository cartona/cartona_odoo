from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from datetime import timedelta
import requests
import logging

from .cartona_mixin import CARTONA_AUTH_HEADER

_logger = logging.getLogger(__name__)

CARTONA_STATE_MAPPING = {
    'approved': 'sale',
    'assigned_to_salesman': 'sale',
    'delivered': 'sale',
    'cancelled': 'cancel',
    'cancelled_by_supplier': 'cancel',
    'cancelled_by_retailer': 'cancel',
    'return': 'draft',
}

_STATE_MAPPING_FIELDS = frozenset(['enable_custom_state_mapping', 'custom_state_mapping'])

_PRODUCT_MAPPING_ERROR_CODES = (
    'missing_internal_product_id',
    'invalid_internal_product_id',
    'variant_not_found',
    'variant_not_available',
)
DASHBOARD_ISSUE_LOOKBACK_HOURS = 24
DASHBOARD_ISSUE_EMBED_LIMIT = 50
DASHBOARD_ISSUE_CACHE_MINUTES = 5


class CartonaConfig(models.Model):
    _name = 'cartona.config'
    _description = 'Cartona Integration Configuration'
    _rec_name = 'name'
    _order = 'sequence, name'
    _sql_constraints = [
        (
            'company_uniq',
            'unique(company_id)',
            'Only one Cartona configuration is allowed per company.',
        ),
    ]

    name = fields.Char(default='Cartona', required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    api_base_url = fields.Char(
        required=True,
        default='https://supplier-integrations.cartona.com/api/v1/',
    )
    auth_token = fields.Char(required=True, groups='cartona_odoo.group_cartona_manager')
    is_cartona_sync_enabled = fields.Boolean(
        string='Enable Cartona Sync',
        default=False,
        help='Master switch for all Cartona sync (orders, products, status).',
    )

    batch_size = fields.Integer(default=100)
    timeout = fields.Integer(default=30, string='Request Timeout (seconds)')

    last_sync_date = fields.Datetime(readonly=True)
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], default='not_tested', readonly=True)
    error_message = fields.Text(readonly=True)

    total_products_synced = fields.Integer(readonly=True, default=0)
    total_orders_pulled = fields.Integer(readonly=True, default=0)
    last_order_pull = fields.Datetime(readonly=True)
    dashboard_issues_refreshed_at = fields.Datetime(readonly=True)

    stat_products_synced = fields.Integer(compute='_compute_dashboard_stats', string='Synced Variants')
    stat_products_error = fields.Integer(compute='_compute_dashboard_stats', string='Sync Errors')
    stat_products_pending = fields.Integer(compute='_compute_dashboard_stats', string='Pending Variants')
    stat_orders_cartona = fields.Integer(compute='_compute_dashboard_stats', string='Cartona Orders')
    stat_sync_errors_24h = fields.Integer(compute='_compute_dashboard_stats', string='Issues (24h)')
    stat_pending_jobs = fields.Integer(compute='_compute_dashboard_stats', string='Queued Jobs')

    dashboard_product_mapping_issue_ids = fields.Many2many(
        'cartona.sync.log.line',
        'cartona_config_product_mapping_rel',
        'config_id',
        'line_id',
        string='Product Mapping Issues (24h)',
        readonly=True,
    )
    dashboard_product_mapping_issue_count = fields.Integer(
        compute='_compute_dashboard_issue_counts',
        string='Product Mapping Issues',
    )
    dashboard_recent_sync_issue_ids = fields.Many2many(
        'cartona.sync.log',
        'cartona_config_recent_sync_rel',
        'config_id',
        'log_id',
        string='Recent Sync Issues (24h)',
        readonly=True,
    )
    dashboard_recent_sync_issue_count = fields.Integer(
        compute='_compute_dashboard_issue_counts',
        string='Recent Sync Issues',
    )

    enable_custom_state_mapping = fields.Boolean(default=False, readonly=True)
    custom_state_mapping = fields.Text(readonly=True)

    def write(self, vals):
        if _STATE_MAPPING_FIELDS.intersection(vals):
            raise UserError(_('Cartona order state mapping is fixed and cannot be changed.'))
        return super().write(vals)

    @api.constrains('api_base_url')
    def _check_api_base_url(self):
        for record in self:
            if record.api_base_url and not record.api_base_url.startswith(('http://', 'https://')):
                raise ValidationError(_('API Base URL must start with http:// or https://'))
            if record.api_base_url and not record.api_base_url.endswith('/'):
                record.api_base_url += '/'

    @api.constrains('batch_size')
    def _check_batch_size(self):
        for record in self:
            if record.batch_size < 1 or record.batch_size > 1000:
                raise ValidationError(_('Batch size must be between 1 and 1000'))

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def copy(self, default=None):
        raise UserError(_('Cartona configuration cannot be duplicated.'))

    def unlink(self):
        manager_group = self.env.ref(
            'cartona_odoo.group_cartona_manager', raise_if_not_found=False,
        )
        if not manager_group or manager_group not in self.env.user.groups_id:
            raise UserError(_('Cartona configuration cannot be deleted.'))
        for config in self:
            if self.env['sale.order'].search_count([
                ('cartona_config_id', '=', config.id),
            ]):
                raise UserError(_(
                    'Cannot delete Cartona configuration for %s: '
                    'Cartona orders are still linked to it.',
                ) % config.company_id.display_name)
        return super().unlink()

    @api.model
    def get_for_company(self, company=None):
        company = company or self.env.company
        return self.search([('company_id', '=', company.id)], limit=1)

    @api.model
    def require_for_company(self, company=None):
        company = company or self.env.company
        config = self.get_for_company(company)
        if not config:
            raise UserError(_(
                'No Cartona configuration for company %s.',
            ) % company.display_name)
        return config

    def _config_form_view_id(self):
        return self.env.ref('cartona_odoo.view_cartona_config_form').id

    @api.model
    def action_open_for_company(self):
        company = self.env.company
        config = self.get_for_company(company)
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Cartona Configuration'),
            'res_model': 'cartona.config',
            'view_mode': 'form',
            'views': [(self._config_form_view_id(), 'form')],
            'target': 'current',
        }
        if config:
            action['res_id'] = config.id
        else:
            action['context'] = {
                'default_company_id': company.id,
                'default_name': company.name,
            }
        return action

    @api.model
    def action_dashboard_for_company(self):
        config = self.get_for_company()
        if not config:
            return self.action_open_for_company()
        config._update_sync_stats()
        return config.action_dashboard_overview()

    @api.model
    def action_recent_activity_for_company(self):
        config = self.get_for_company()
        if not config:
            return self.action_open_for_company()
        return config.action_dashboard_recent_activity()

    @api.model
    def action_log_details_for_company(self):
        config = self.get_for_company()
        if not config:
            return self.action_open_for_company()
        return config.action_dashboard_log_details()

    def _cartona_pending_jobs_domain(self):
        return [
            ('state', 'in', ['pending', 'enqueued', 'started', 'wait_dependencies']),
            '|', ('channel', 'ilike', 'cartona'), ('name', 'ilike', 'Cartona'),
        ]

    def _filter_cartona_jobs_for_company(self, jobs):
        self.ensure_one()
        company = self.company_id
        allowed = self.env['queue.job']
        for job in jobs:
            records = job.records
            if not records:
                continue
            if all(
                not getattr(record, 'company_id', False)
                or record.company_id in (False, company)
                for record in records
            ):
                allowed |= job
        return allowed

    def get_api_headers(self):
        self.ensure_one()
        return {
            CARTONA_AUTH_HEADER: self.auth_token,
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo-Cartona-Integration/18.0',
        }

    @api.model
    def get_active_configs(self):
        return self.search([])

    def get_state_mapping(self):
        self.ensure_one()
        return dict(CARTONA_STATE_MAPPING)

    def _dashboard_sync_domain(self, extra=None):
        self.ensure_one()
        domain = [('cartona_config_id', '=', self.id)]
        if extra:
            domain.extend(extra)
        return domain

    def _dashboard_eligible_product_domain(self):
        self.ensure_one()
        return [
            ('sale_ok', '=', True),
            ('company_id', 'in', [False, self.company_id.id]),
        ]

    def _count_pending_variants(self):
        self.ensure_one()
        sync_model = self.env['cartona.product.sync']
        pivot_pending = sync_model.search_count(
            self._dashboard_sync_domain([
                ('sync_status', 'in', ['not_synced', 'syncing']),
            ]),
        )
        has_pivot_product_ids = sync_model.search(
            self._dashboard_sync_domain(),
        ).mapped('product_id').ids
        no_row_pending = self.env['product.product'].search_count(
            self._dashboard_eligible_product_domain() + [
                ('id', 'not in', has_pivot_product_ids),
            ],
        )
        return pivot_pending + no_row_pending

    @api.depends(
        'is_cartona_sync_enabled', 'connection_status', 'last_order_pull',
        'last_sync_date', 'total_products_synced', 'total_orders_pulled',
        'company_id',
    )
    def _compute_dashboard_stats(self):
        log_model = self.env['cartona.sync.log']
        sync_model = self.env['cartona.product.sync']
        order_model = self.env['sale.order']
        job_model = self.env['queue.job']
        since = fields.Datetime.now() - timedelta(hours=24)
        for config in self:
            config.stat_products_synced = sync_model.search_count(
                config._dashboard_sync_domain([('sync_status', '=', 'synced')]),
            )
            config.stat_products_error = sync_model.search_count(
                config._dashboard_sync_domain([('sync_status', '=', 'error')]),
            )
            config.stat_products_pending = config._count_pending_variants()
            config.stat_orders_cartona = order_model.search_count([
                ('is_cartona_order', '=', True),
                ('cartona_config_id', '=', config.id),
            ])
            config.stat_sync_errors_24h = log_model.search_count([
                ('cartona_config_id', '=', config.id),
                ('status', 'in', ['error', 'warning']),
                ('create_date', '>=', since),
            ])
            config.stat_pending_jobs = len(
                config._filter_cartona_jobs_for_company(
                    job_model.search(config._cartona_pending_jobs_domain()),
                ),
            )

    @api.depends(
        'dashboard_product_mapping_issue_ids',
        'dashboard_recent_sync_issue_ids',
    )
    def _compute_dashboard_issue_counts(self):
        for config in self:
            config.dashboard_product_mapping_issue_count = len(
                config.dashboard_product_mapping_issue_ids,
            )
            config.dashboard_recent_sync_issue_count = len(
                config.dashboard_recent_sync_issue_ids,
            )

    def _dashboard_issue_since(self):
        return fields.Datetime.now() - timedelta(hours=DASHBOARD_ISSUE_LOOKBACK_HOURS)

    def _dashboard_product_mapping_domain(self, since=None):
        self.ensure_one()
        since = since or self._dashboard_issue_since()
        return [
            ('sync_log_id.cartona_config_id', '=', self.id),
            ('sync_log_id.create_date', '>=', since),
            ('entry_type', '=', 'order_line'),
            ('status', 'in', ['error', 'warning']),
            ('error_code', 'in', list(_PRODUCT_MAPPING_ERROR_CODES)),
        ]

    def _dashboard_recent_sync_domain(self, since=None):
        self.ensure_one()
        since = since or self._dashboard_issue_since()
        return [
            ('cartona_config_id', '=', self.id),
            ('create_date', '>=', since),
            ('status', 'in', ['error', 'warning']),
        ]

    def _compute_dashboard_issue_snapshots(self):
        line_model = self.env['cartona.sync.log.line']
        log_model = self.env['cartona.sync.log']
        line_order = 'sync_log_create_date desc, id desc'
        log_order = 'create_date desc, id desc'
        for config in self:
            since = config._dashboard_issue_since()
            mapping_domain = config._dashboard_product_mapping_domain(since)
            sync_domain = config._dashboard_recent_sync_domain(since)
            config.sudo().write({
                'dashboard_product_mapping_issue_ids': [(6, 0, line_model.search(
                    mapping_domain, order=line_order, limit=DASHBOARD_ISSUE_EMBED_LIMIT,
                ).ids)],
                'dashboard_recent_sync_issue_ids': [(6, 0, log_model.search(
                    sync_domain, order=log_order, limit=DASHBOARD_ISSUE_EMBED_LIMIT,
                ).ids)],
                'dashboard_issues_refreshed_at': fields.Datetime.now(),
            })

    def _dashboard_issues_cache_expired(self):
        self.ensure_one()
        if not self.dashboard_issues_refreshed_at:
            return True
        age = fields.Datetime.now() - self.dashboard_issues_refreshed_at
        return age > timedelta(minutes=DASHBOARD_ISSUE_CACHE_MINUTES)

    def _refresh_dashboard_issues_if_stale(self, force=False):
        for config in self:
            if force or config._dashboard_issues_cache_expired():
                config._compute_dashboard_issue_snapshots()

    def _get_dashboard_window_action(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cartona_odoo.action_cartona_dashboard_window',
        )
        action['res_id'] = self.id
        return action

    def _get_dashboard_embedded_actions(self):
        self.ensure_one()
        parent_action = self.env.ref('cartona_odoo.action_cartona_dashboard_window')
        embedded = self.env['ir.embedded.actions'].with_context(
            active_id=self.id,
            active_model='cartona.config',
        ).search([
            ('parent_action_id', '=', parent_action.id),
        ], order='sequence, id').filtered('is_visible')
        embedded_data = embedded.read(list(embedded._get_readable_fields()))
        embedded_data.append({
            'id': False,
            'name': parent_action.name,
            'parent_action_id': parent_action.id,
            'parent_res_model': 'cartona.config',
            'action_id': parent_action.id,
            'user_id': False,
            'context': '{}',
            'domain': '[]',
            'default_view_mode': 'form',
            'groups_ids': [],
            'parent_res_id': 0,
            'filter_ids': [],
            'is_deletable': False,
            'python_method': False,
        })
        return embedded_data

    def _dashboard_embedded_context(self, embedded_xmlid):
        self.ensure_one()
        parent_action = self.env.ref('cartona_odoo.action_cartona_dashboard_window')
        embedded_action = self.env.ref(embedded_xmlid)
        return {
            'active_id': self.id,
            'active_model': 'cartona.config',
            'parent_action_id': parent_action.id,
            'current_embedded_action_id': embedded_action.id,
            'parent_action_embedded_actions': self._get_dashboard_embedded_actions(),
        }

    def action_dashboard_overview(self):
        self.ensure_one()
        self._refresh_dashboard_issues_if_stale()
        action = self._get_dashboard_window_action()
        ctx = action.get('context') or {}
        if isinstance(ctx, str):
            ctx = safe_eval(ctx, {'uid': self.env.uid}) if ctx else {}
        action['context'] = {
            **ctx,
            **self._dashboard_embedded_context('cartona_odoo.cartona_embedded_dashboard_overview'),
        }
        return action

    def action_dashboard_recent_activity(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recent Activity'),
            'res_model': 'cartona.sync.log',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('cartona_odoo.view_cartona_sync_log_list').id, 'list'),
                (self.env.ref('cartona_odoo.view_cartona_sync_log_form').id, 'form'),
            ],
            'search_view_id': self.env.ref('cartona_odoo.view_cartona_sync_log_search').id,
            'domain': [('cartona_config_id', '=', self.id)],
            'context': {
                'default_cartona_config_id': self.id,
                **self._dashboard_embedded_context('cartona_odoo.cartona_embedded_recent_activity'),
            },
        }

    def action_dashboard_log_details(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Details'),
            'res_model': 'cartona.sync.log.line',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('cartona_odoo.view_cartona_sync_log_line_list').id, 'list'),
                (self.env.ref('cartona_odoo.view_cartona_sync_log_line_form').id, 'form'),
            ],
            'search_view_id': self.env.ref('cartona_odoo.view_cartona_sync_log_line_search').id,
            'domain': [('sync_log_id.cartona_config_id', '=', self.id)],
            'context': self._dashboard_embedded_context('cartona_odoo.cartona_embedded_log_details'),
        }

    def action_view_product_mapping_issues(self):
        self.ensure_one()
        action = self.action_dashboard_log_details()
        action['name'] = _('Product Mapping Issues (24h)')
        action['domain'] = self._dashboard_product_mapping_domain()
        action['context'] = {
            **(action.get('context') or {}),
            'search_default_filter_order_line': 1,
            'search_default_filter_product_mapping': 1,
        }
        return action

    def action_view_recent_sync_issues(self):
        self.ensure_one()
        action = self.action_dashboard_recent_activity()
        action['name'] = _('Recent Sync Issues (24h)')
        action['domain'] = self._dashboard_recent_sync_domain()
        action['context'] = {
            **(action.get('context') or {}),
            'search_default_filter_error': 1,
        }
        return action

    def action_refresh_dashboard(self):
        self.ensure_one()
        self._update_sync_stats()
        self._refresh_dashboard_issues_if_stale(force=True)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def action_open_dashboard(self):
        return self.action_dashboard_for_company()

    def action_view_products_synced(self):
        return self._action_view_sync_by_status('synced')

    def action_view_products_error(self):
        return self._action_view_sync_by_status('error')

    def action_view_products_pending(self):
        return self._action_view_sync_by_status(['not_synced', 'syncing'])

    def _action_view_sync_by_status(self, status):
        self.ensure_one()
        if isinstance(status, (list, tuple)):
            status_filter = ('sync_status', 'in', list(status))
            name = _('Pending Variants')
        else:
            status_filter = ('sync_status', '=', status)
            names = {
                'synced': _('Synced Variants'),
                'error': _('Variants With Sync Errors'),
                'not_synced': _('Unsynced Variants'),
                'syncing': _('Variants Syncing'),
            }
            name = names.get(status, _('Variants'))
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'cartona.product.sync',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('cartona_odoo.view_cartona_product_sync_list').id, 'list'),
                (self.env.ref('cartona_odoo.view_cartona_product_sync_form').id, 'form'),
            ],
            'domain': self._dashboard_sync_domain([status_filter]),
            'context': {'default_cartona_config_id': self.id},
        }

    def action_view_sync_errors_24h(self):
        self.ensure_one()
        since = fields.Datetime.now() - timedelta(hours=24)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recent Sync Issues'),
            'res_model': 'cartona.sync.log',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('cartona_odoo.view_cartona_sync_log_list').id, 'list'),
                (self.env.ref('cartona_odoo.view_cartona_sync_log_form').id, 'form'),
            ],
            'domain': [
                ('cartona_config_id', '=', self.id),
                ('status', 'in', ['error', 'warning']),
                ('create_date', '>=', since),
            ],
        }

    def action_view_pending_jobs(self):
        self.ensure_one()
        jobs = self._filter_cartona_jobs_for_company(
            self.env['queue.job'].search(self._cartona_pending_jobs_domain()),
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cartona Queue Jobs'),
            'res_model': 'queue.job',
            'view_mode': 'list,form',
            'domain': [('id', 'in', jobs.ids)],
        }

    def action_open_singleton(self):
        return self.action_open_for_company()

    def test_connection(self):
        self.ensure_one()
        test_url = f'{self.api_base_url.rstrip("/")}/supplier-product'
        try:
            response = requests.get(
                test_url,
                headers=self.get_api_headers(),
                timeout=self.timeout,
                params={'page': 1, 'per_page': 1},
            )
            if response.status_code == 200:
                self.write({
                    'connection_status': 'connected',
                    'error_message': False,
                    'last_sync_date': fields.Datetime.now(),
                })
                self.env['cartona.sync.log'].log_operation(
                    cartona_config_id=self.id,
                    operation_type='connection_test',
                    status='success',
                    message='Connection test successful',
                    action_type='manual',
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to Cartona API.'),
                        'type': 'success',
                    },
                }
            self.write({
                'connection_status': 'error',
                'error_message': f'HTTP {response.status_code}: {response.text}',
            })
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=self.id,
                operation_type='connection_test',
                status='error',
                message=f'Connection test failed (HTTP {response.status_code})',
                error_details=response.text,
                action_type='manual',
            )
            raise UserError(_('Connection failed (HTTP %s). Check your token and URL.') % response.status_code)
        except UserError:
            raise
        except requests.exceptions.Timeout:
            self.write({'connection_status': 'error', 'error_message': 'Timeout'})
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=self.id,
                operation_type='connection_test',
                status='error',
                message=f'Connection test timed out after {self.timeout}s',
                action_type='manual',
            )
            raise UserError(_('Connection timeout after %s seconds') % self.timeout)
        except requests.exceptions.ConnectionError as err:
            self.write({'connection_status': 'error', 'error_message': str(err)})
            self.env['cartona.sync.log'].log_operation(
                cartona_config_id=self.id,
                operation_type='connection_test',
                status='error',
                message='Connection test failed',
                error_details=str(err),
                action_type='manual',
            )
            raise UserError(_('Cannot connect to Cartona API: %s') % err)

    def manual_pull_orders(self):
        self.ensure_one()
        if not self.is_cartona_sync_enabled:
            raise UserError(_('Enable Cartona sync on configuration first.'))
        api = self.env['cartona.api'].with_company(self.company_id).with_context(
            cartona_config_id=self.id,
            cartona_log_action_type='manual',
        )
        result = api.pull_and_process_orders()
        self._update_sync_stats()
        self._refresh_dashboard_issues_if_stale(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Order Pull Complete'),
                'message': result.get('message', ''),
                'type': 'success' if result.get('success') else 'warning',
            },
        }

    def manual_sync_all_variants(self):
        self.ensure_one()
        if not self.is_cartona_sync_enabled:
            raise UserError(_('Enable Cartona sync on configuration first.'))
        company = self.company_id
        variant_count = self.env['product.product'].with_company(company).search_count(
            self._dashboard_eligible_product_domain(),
        )
        if not variant_count:
            raise UserError(_(
                'No saleable product variants found for %s.',
            ) % company.display_name)
        self.with_delay(
            channel='cartona',
            description=_(
                'Sync all saleable variants to Cartona (%s)',
            ) % company.display_name,
        ).sync_all_variants_job()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Variant Sync Queued'),
                'message': _(
                    '%(count)s variant(s) queued for price and stock sync '
                    'for %(company)s. Track progress in Recent Activity.',
                ) % {'count': variant_count, 'company': company.display_name},
                'type': 'info',
            },
        }

    def sync_all_variants_job(self):
        """Queue job entrypoint: restore config context then run bulk sync."""
        self.ensure_one()
        if not self.is_cartona_sync_enabled:
            return
        self.env['cartona.api'].with_company(self.company_id).with_context(
            cartona_config_id=self.id,
            cartona_log_action_type='manual',
        ).sync_all_variants()

    def action_view_synced_variants(self):
        return self._action_view_sync_by_status('synced')

    def action_view_cartona_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cartona Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [
                ('is_cartona_order', '=', True),
                ('cartona_config_id', '=', self.id),
            ],
        }

    def action_view_sync_logs(self):
        self.ensure_one()
        return self.action_dashboard_recent_activity()

    def _update_sync_stats(self):
        self.ensure_one()
        self.write({
            'total_products_synced': self.env['cartona.product.sync'].search_count(
                self._dashboard_sync_domain([('sync_status', '=', 'synced')]),
            ),
            'total_orders_pulled': self.env['sale.order'].search_count([
                ('is_cartona_order', '=', True),
                ('cartona_config_id', '=', self.id),
            ]),
            'last_sync_date': fields.Datetime.now(),
        })
