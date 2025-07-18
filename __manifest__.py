{
    'name': 'Cartona Marketplace Integration',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Generic marketplace integration for suppliers - Cartona, Amazon, eBay, and more',
    'description': """
Cartona Marketplace Integration
===============================

Universal marketplace integration module for suppliers to connect their Odoo system 
to various marketplace platforms including Cartona, Amazon, eBay, Shopify, and others.

Key Features:
- Direct supplier-to-marketplace integration
- Real-time price and stock synchronization
- Automatic order pull and processing
- Multi-marketplace support with single configuration
- Bearer token authentication
- Queue-based processing for reliability
- Extend existing Odoo views (no duplicate interfaces)

Installation:
Each supplier installs this module in their own Odoo instance and configures
their unique authentication tokens for their marketplace connections.

Architecture:
- One Odoo Instance = One Supplier
- Direct Connection: Supplier's Odoo ↔ Marketplace Platform(s)
- Universal cartona_id field for external product/partner matching
- Generic API client works with any REST API marketplace
    """,
    'author': 'Cartona Integration Team',
    'website': 'https://cartona.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_management',
        'stock',
        'product',
        'purchase',
        'queue_job',  # For asynchronous processing
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/marketplace_security.xml',
        
        # Data
        'data/queue_job_data.xml',
        'data/cron_data.xml',
        
        # Views - Extend existing views
        'views/product_views.xml',
        'views/res_partner_views.xml', 
        'views/sale_order_views.xml',
        'views/stock_views.xml',
        
        # Views - New configuration views only
        'views/marketplace_config_views.xml',
        'views/sync_dashboard_views.xml',
        
        # Menu
        'views/marketplace_menu.xml',
    ],
    'images': ['static/description/icon.png'],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
