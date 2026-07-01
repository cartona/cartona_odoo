{
    'name': 'Cartona Integration',
    'version': '18.0.2.0.49',
    'category': 'Sales',
    'summary': 'Cartona supplier integration for Odoo 18',
    'description': """
Cartona Integration
===================

Connect Odoo to Cartona supplier-integrations API:

- Variant-only product sync via internal_product_id (Odoo variant id)
- Inbound order pull and outbound status/line sync
- Global sync gate on cartona.config.is_cartona_sync_enabled
- One cartona.config per Odoo warehouse (company-aware, warehouse-scoped stock)
- Queue-based async processing via OCA queue_job
    """,
    'author': 'Cartona Integration Team',
    'website': 'https://cartona.com',
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
    'depends': [
        'base',
        'mail',
        'sale_management',
        'stock',
        'product',
        'queue_job',
    ],
    'assets': {
        'web.assets_backend': [
            (
                'after',
                'mail/static/src/webclient/web/webclient.js',
                'cartona_odoo/static/src/js/dev_skip_web_push.js',
            ),
        ],
    },
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/cartona_security.xml',
        'security/ir.model.access.csv',
        'data/queue_job_data.xml',
        'data/cron_data.xml',
        'views/cartona_config_views.xml',
        'views/cartona_dashboard_views.xml',
        'views/cartona_sync_log_views.xml',
        'views/cartona_product_sync_views.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/cartona_delivery_otp_wizard_views.xml',
        'views/cartona_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
