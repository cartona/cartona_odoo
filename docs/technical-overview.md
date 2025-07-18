# Cartona Marketplace Integration - Technical Overview

**Document Version:** 1.0  
**Date:** July 17, 2025  
**Audience:** Developers, Tech Leads  
**Module Version:** 18.0.1.0.0  
**Odoo Compatibility:** 18.0

---

## 1. Architecture Overview

### Design Pattern

- **Universal Marketplace Integration**: Generic framework supporting multiple marketplaces (Cartona, Amazon, eBay, etc.)
- **Inheritance-Based Extensions**: Extends existing Odoo models rather than creating duplicates
- **Queue-Based Processing**: Asynchronous processing using `queue_job` module
- **API-First Design**: RESTful API client with normalized response handling

### Core Principles

- **Single Tenant**: One Odoo instance serves one supplier
- **Extend, Don't Duplicate**: Enhance existing views/models instead of creating new ones
- **Universal External IDs**: Single `cartona_id` field for all marketplace integrations
- **Business Logic Compliance**: Respects Odoo's standard workflows and state transitions

---

## 2. Modules and Files

| File/Folder         | Purpose                            | Key Components                                       |
| ------------------- | ---------------------------------- | ---------------------------------------------------- |
| **models/**         | Business logic and data models     | 9 model files extending core Odoo functionality      |
| **controllers/**    | External APIs exposed              | Currently empty - no webhook controllers implemented |
| **data/**           | Scheduled actions and default data | `cron_data.xml`, `queue_job_data.xml`                |
| **security/**       | Access rights and permissions      | `ir.model.access.csv`, `marketplace_security.xml`    |
| **views/**          | UI extensions and new views        | Extends existing views + 2 new config views          |
| ****manifest**.py** | Module definition                  | Dependencies, data files, version info               |

### File Structure Details

```
models/
├── __init__.py                    # Model imports
├── marketplace_config.py          # Core configuration (797 lines)
├── marketplace_api.py             # API client (667 lines)
├── marketplace_order_processor.py # Order processing logic (559 lines)
├── marketplace_sync_log.py        # Logging system (196 lines)
├── product_template.py            # Product extensions (264 lines)
├── product_product.py             # Product variant extensions
├── res_partner.py                 # Customer extensions
├── sale_order.py                  # Order extensions (682 lines)
└── stock_move.py                  # Inventory extensions (113 lines)

data/
├── cron_data.xml                  # 3 scheduled jobs
└── queue_job_data.xml             # Queue job configurations

security/
├── ir.model.access.csv            # Model access permissions
└── marketplace_security.xml       # Security groups and rules

views/
├── marketplace_config_views.xml   # Configuration interface
├── sync_dashboard_views.xml       # Monitoring dashboard
├── product_views.xml              # Product form extensions
├── res_partner_views.xml          # Customer form extensions
├── sale_order_views.xml           # Order form extensions
├── stock_views.xml                # Inventory extensions
└── marketplace_menu.xml           # Menu structure
```

---

## 3. Key Models & Fields

### New Models

#### `marketplace.config` (Core Configuration)

```python
# Primary configuration model - 797 lines
_name = 'marketplace.config'

# API Configuration
name = fields.Char()                      # Marketplace name
api_base_url = fields.Char()              # API endpoint
auth_token = fields.Char()                # Bearer token
auth_header = fields.Char()               # Header name (default: AuthorizationToken)

# Sync Settings
auto_sync_stock = fields.Boolean()        # Auto stock sync
auto_sync_prices = fields.Boolean()       # Auto price sync
auto_pull_orders = fields.Boolean()       # Auto order pull

# Performance Settings
batch_size = fields.Integer(default=100)  # Batch processing size
retry_attempts = fields.Integer(default=3) # Retry count
timeout = fields.Integer(default=30)      # Request timeout

# Status & Statistics
connection_status = fields.Selection()    # not_tested/connected/error
last_sync_date = fields.Datetime()        # Last sync timestamp
total_products_synced = fields.Integer()  # Stats counter
total_orders_pulled = fields.Integer()    # Stats counter

# State Mapping (JSON)
custom_state_mapping = fields.Text()      # Cartona->Odoo state mapping
```

#### `marketplace.api` (API Client)

```python
# Generic API client - 667 lines
_name = 'marketplace.api'

# Key Methods:
_make_api_request()                       # Core HTTP client
pull_orders()                            # GET order/pull-orders
update_single_order_status()            # POST order/update-order-status/{id}
bulk_update_products()                   # POST supplier-product/bulk-update
bulk_update_stock()                      # POST supplier-product/bulk-update
_normalize_api_response()                # Response standardization
```

#### `marketplace.order.processor` (Order Logic)

```python
# Order processing business logic - 559 lines
_name = 'marketplace.order.processor'

# Key Methods:
process_marketplace_order()              # Main order processing entry point
_validate_order_data()                   # Cartona JSON validation
_create_new_order()                      # Sale order creation
_apply_cartona_state_action()            # Business logic for state transitions
_complete_delivery()                     # Delivery completion automation
```

#### `marketplace.sync.log` (Logging System)

```python
# Comprehensive logging - 196 lines
_name = 'marketplace.sync.log'

# Fields:
operation_type = fields.Selection()       # product_sync/order_pull/status_sync
status = fields.Selection()               # success/error/warning/info
message = fields.Text()                   # Log message
error_details = fields.Text()             # Detailed error info
records_processed = fields.Integer()      # Count of processed records
```

### Extended Models

#### `product.template` Extensions

```python
# Added fields to existing product model
cartona_id = fields.Char()                # Universal external product ID
delivered_by = fields.Selection()         # delivered_by_supplier/delivered_by_cartona
marketplace_sync_status = fields.Selection() # not_synced/syncing/synced/error
marketplace_sync_enabled = fields.Boolean()  # Enable/disable sync
marketplace_sync_date = fields.Datetime()    # Last sync timestamp
marketplace_error_message = fields.Text()    # Error details

# Triggers:
write() -> _trigger_marketplace_sync()    # Auto-sync on price changes
create() -> _trigger_marketplace_sync()   # Auto-sync new products
```

#### `sale.order` Extensions

```python
# Added fields to existing order model
cartona_id = fields.Char()                # External order ID (indexed)
marketplace_config_id = fields.Many2one() # Source marketplace
marketplace_sync_status = fields.Selection() # Sync status tracking
is_marketplace_order = fields.Boolean()   # Flag for marketplace orders
marketplace_order_number = fields.Char()  # Original order number
marketplace_status = fields.Char()        # Cartona status
delivered_by = fields.Selection()         # Delivery responsibility
marketplace_payment_method = fields.Char() # Payment method

# Business Logic:
write() -> _filter_orders_for_sync()     # Business rules for sync eligibility
_sync_status_to_marketplace()            # Queue job for status sync
_map_odoo_status_to_marketplace()        # State mapping logic
```

#### `res.partner` Extensions

```python
# Customer/supplier extensions
cartona_id = fields.Char()                # External customer ID
marketplace_customer_type = fields.Selection() # Customer classification
marketplace_sync_status = fields.Selection()   # Sync status
```

#### `stock.move` & `stock.quant` Extensions

```python
# Inventory sync extensions
marketplace_stock_sync_status = fields.Selection() # Stock sync status
_action_done() -> _trigger_stock_sync()  # Auto-sync on inventory moves
write() -> _trigger_stock_sync()         # Auto-sync on quantity changes
```

---

## 4. Cartona API Integration

### Authentication Method

- **Type**: Bearer Token Authentication
- **Header**: `AuthorizationToken: <token>` (configurable header name)
- **Storage**: Encrypted in `marketplace.config.auth_token`
- **Validation**: Built-in connection testing via `test_connection()`

### API Endpoints Used

#### Order Management

```python
# GET /api/v1/order/pull-orders
# Purpose: Retrieve orders from Cartona
# Parameters: page, per_page, from, to (date range)
# Response: List of order objects

# POST /api/v1/order/update-order-status/{hashed_id}
# Purpose: Update single order status
# Body: {"status": "delivered", "hashed_id": "xyz"}
# Response: Success/error confirmation

# POST /api/v1/order/update-order-status
# Purpose: Bulk update order statuses
# Body: [{"hashed_id": "xyz", "status": "delivered"}]
# Response: List of results
```

#### Product Management

```python
# POST /api/v1/supplier-product/bulk-update
# Purpose: Update products (price/stock)
# Body: [{"supplier_product_id": "123", "selling_price": "100.00"}]
# Response: Success confirmation

# GET /api/v1/supplier-product
# Purpose: Connection testing and product validation
# Parameters: page, per_page
# Response: Product list
```

### Request/Response Flow

```python
# 1. Prepare headers
headers = {
    self.auth_header: self.auth_token,  # Default: AuthorizationToken
    'Content-Type': 'application/json',
    'User-Agent': 'Odoo-Cartona-Integration/1.0'
}

# 2. Make request with timeout/retry
response = requests.request(method, url, headers=headers, timeout=30)

# 3. Normalize response format
def _normalize_api_response(self, response):
    # Converts any response type to: {"success": bool, "data": any, "error": str}
    if isinstance(response, list):
        return {'success': True, 'data': response}
    elif isinstance(response, dict):
        return response if 'success' in response else {'success': True, 'data': response}
    else:
        return {'success': False, 'error': 'Invalid response format'}
```

### Response Mapping Structure

#### Cartona Order JSON → Odoo Sale Order

```python
# Cartona Order Structure:
{
    "hashed_id": "abc123",           -> sale_order.cartona_id
    "status": "approved",            -> marketplace_status + state transition
    "total_price": 150.00,           -> amount_total
    "delivered_by": "delivered_by_supplier", -> delivered_by
    "retailer": {
        "retailer_name": "ABC Store", -> res_partner.name
        "retailer_code": "R001"       -> res_partner.cartona_id
    },
    "order_details": [               -> sale_order_line records
        {
            "supplier_product_id": "P123", -> product matching
            "amount": 5,                   -> product_uom_qty
            "selling_price": 30.00         -> price_unit
        }
    ]
}
```

#### State Mapping Configuration

```python
# Default Cartona → Odoo State Mapping
{
    "approved": "sale",              # action_confirm()
    "cancelled": "cancel",           # action_cancel()
    "assigned_to_salesman": "sale",  # action_confirm() + assign delivery
    "delivered": "done",             # complete delivery workflow
    "return": "draft"                # manual handling required
}
```

---

## 5. Scheduled Jobs

### Cron Job Configuration (`data/cron_data.xml`)

#### 1. Pull Orders (Every 1 minute)

```xml
<record id="cron_pull_marketplace_orders" model="ir.cron">
    <field name="name">Pull Marketplace Orders</field>
    <field name="interval_number">1</field>
    <field name="interval_type">minutes</field>
    <field name="active">True</field>
    <field name="code">
# Pull orders from all active marketplaces
marketplaces = env['marketplace.config'].search([
    ('active', '=', True),
    ('auto_pull_orders', '=', True)
])

for marketplace in marketplaces:
    try:
        api_client = env['marketplace.api'].with_context(
            marketplace_config_id=marketplace.id
        )
        api_client.pull_and_process_orders()
    except Exception as e:
        env['marketplace.sync.log'].log_operation(
            marketplace_config_id=marketplace.id,
            operation_type='order_pull',
            status='error',
            message=f"Cron job error: {str(e)}"
        )
    </field>
</record>
```

#### 2. Sync Product Data (Every 30 minutes)

```xml
<record id="cron_sync_product_data" model="ir.cron">
    <field name="name">Sync Product Data to Marketplaces</field>
    <field name="interval_number">30</field>
    <field name="interval_type">minutes</field>
    <field name="code">
# Sync products that need updating
products_to_sync = env['product.template'].search([
    ('marketplace_sync_enabled', '=', True),
    ('marketplace_sync_status', 'in', ['not_synced', 'error']),
    ('active', '=', True)
], limit=100)  # Process in batches
    </field>
</record>
```

#### 3. Cleanup Logs (Daily)

```xml
<record id="cron_cleanup_sync_logs" model="ir.cron">
    <field name="name">Clean up Marketplace Sync Logs</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="code">
# Clean up logs older than 30 days
model.cleanup_old_logs(days=30)
    </field>
</record>
```

### Retry Logic Implementation

#### Queue Job Retry (queue_job module)

```python
# Automatic retry with exponential backoff
order.with_delay(
    channel='marketplace',
    max_retries=3,
    retry_pattern=60  # seconds base delay
)._sync_status_to_marketplace()

# Manual retry configuration in marketplace.config
retry_attempts = fields.Integer(default=3)  # Max retry attempts
timeout = fields.Integer(default=30)        # Request timeout
```

#### API Request Retry Logic

```python
def _make_api_request(self, endpoint, method='GET', data=None, params=None):
    try:
        response = requests.request(method, **request_params)
        # Handle response codes
        if response.status_code == 200:
            return response.json()
        elif response.status_code in [401, 403]:
            # Authentication error - no retry
            return {'success': False, 'error': 'Authentication failed'}
        else:
            # Other errors - will be retried by queue job
            return {'success': False, 'error': f'API Error {response.status_code}'}
    except requests.exceptions.Timeout:
        # Timeout - will be retried
        return {'success': False, 'error': 'Request timeout'}
    except requests.exceptions.ConnectionError:
        # Connection error - will be retried
        return {'success': False, 'error': 'Connection error'}
```

### Logs Location

#### Custom Logging System (`marketplace.sync.log`)

- **Location**: Database table `marketplace_sync_log`
- **Retention**: 30 days (configurable cleanup)
- **Access**: Via Marketplace > Sync Logs menu
- **Fields**: operation_type, status, message, error_details, records_processed

#### Python Logging

```python
import logging
_logger = logging.getLogger(__name__)

# Log levels used:
_logger.info()     # General information
_logger.warning()  # Warning conditions
_logger.error()    # Error conditions
_logger.debug()    # Debug information
```

---

## 6. Odoo Business Logic

### Sale Order Creation Logic

#### Order Processing Flow

```python
def process_marketplace_order(self, order_data):
    """Main entry point for order processing"""
    # 1. Validate order data structure
    validated_order = self._validate_order_data(order_data)

    # 2. Check for existing order
    existing_order = self._find_existing_order(validated_order['order_id'])

    # 3. Create or update order
    if existing_order:
        return self._update_existing_order(existing_order, validated_order)
    else:
        return self._create_new_order(validated_order, config)
```

#### Order Creation Process

```python
def _create_new_order(self, order_data, config):
    # 1. Find or create customer
    customer = self._find_or_create_customer(order_data['customer_data'])

    # 2. Create draft order
    order_vals = {
        'partner_id': customer.id,
        'cartona_id': order_data['order_id'],
        'marketplace_config_id': config.id,
        'is_marketplace_order': True,
        'marketplace_status': order_data.get('status'),
        'state': 'draft',  # Always start in draft
    }
    order = self.env['sale.order'].create(order_vals)

    # 3. Create order lines
    self._create_order_lines(order, order_data['order_lines'])

    # 4. Apply proper state transitions
    self._apply_cartona_state_action(order, order_data.get('status'))

    return order
```

### State Transition Logic

#### Cartona Status → Odoo Actions

```python
def _apply_cartona_state_action(self, order, cartona_status):
    """Apply proper Odoo actions based on Cartona status"""
    order_ctx = order.with_context(skip_marketplace_sync=True)

    if cartona_status == 'approved':
        # Confirm order: draft → sale
        if order.state == 'draft':
            order_ctx.action_confirm()

    elif cartona_status == 'assigned_to_salesman':
        # Confirm + assign delivery
        if order.state == 'draft':
            order_ctx.action_confirm()
        # Assign inventory to deliveries
        for picking in order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing'):
            if picking.state in ['confirmed', 'waiting']:
                picking.action_assign()

    elif cartona_status == 'delivered':
        # Complete entire workflow
        if order.state == 'draft':
            order_ctx.action_confirm()
        # Complete all deliveries
        for picking in order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing'):
            if picking.state in ['confirmed', 'waiting']:
                picking.action_assign()
            if picking.state == 'assigned':
                self._complete_delivery(picking)

    elif cartona_status in ['cancelled', 'cancelled_by_retailer']:
        # Cancel order and all related operations
        if order.state not in ['cancel', 'done']:
            order_ctx.action_cancel()
```

### Delivery Validation & Completion

#### Automatic Delivery Completion

```python
def _complete_delivery(self, picking):
    """Complete delivery by auto-filling quantities and validating"""
    try:
        # Auto-fill quantities for all moves
        for move in picking.move_ids:
            if move.state in ['confirmed', 'waiting', 'assigned']:
                move.quantity_done = move.product_uom_qty

        # Validate the picking (complete delivery)
        if picking.state == 'assigned':
            picking.button_validate()
            _logger.info(f"Delivery {picking.name} completed automatically")

    except Exception as e:
        _logger.error(f"Error completing delivery {picking.name}: {e}")
```

#### Stock Move Integration

```python
class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        """Override to trigger stock sync when moves are done"""
        result = super()._action_done(cancel_backorder)

        # Trigger stock sync for affected products
        if not self.env.context.get('skip_marketplace_sync'):
            products_to_sync = self.mapped('product_id').filtered('marketplace_stock_sync_enabled')
            if products_to_sync:
                products_to_sync._trigger_stock_sync()

        return result
```

### Bidirectional Sync Business Rules

#### Order Status Sync Rules

```python
def _filter_orders_for_sync(self):
    """Filter orders based on business rules for syncing"""
    allowed_orders = self.env['sale.order']

    for order in self:
        if order.delivered_by == 'delivered_by_cartona':
            # Only sync cancellation status
            if order.state == 'cancel':
                allowed_orders |= order
        elif order.delivered_by == 'delivered_by_supplier':
            # Sync all status changes
            allowed_orders |= order

    return allowed_orders
```

#### Context-Based Sync Control

```python
# Prevent infinite loops during marketplace sync
order.with_context(skip_marketplace_sync=True).action_confirm()

# Prevent sync during batch operations
products.with_context(skip_marketplace_sync=True).write({'list_price': 100})
```

### Error Handling & Recovery

#### Exception Handling Pattern

```python
try:
    # Business operation
    result = api_client.update_order_status(order, new_status)

    if result.get('success'):
        order.write({'marketplace_sync_status': 'synced'})
    else:
        order.write({
            'marketplace_sync_status': 'error',
            'marketplace_error_message': result.get('error')
        })

except Exception as e:
    # Log error and update status
    _logger.error(f"Sync error for order {order.name}: {e}")
    order.write({
        'marketplace_sync_status': 'error',
        'marketplace_error_message': str(e)
    })
```

#### Queue Job Error Recovery

```python
# Failed jobs are automatically retried
# Manual reprocessing available via:
self.env['queue.job'].search([('state', '=', 'failed')]).requeue()
```

---

## 7. Security & Permissions

### Access Control (`security/ir.model.access.csv`)

```csv
# Model access rules
access_marketplace_config_user,marketplace.config.user,model_marketplace_config,base.group_user,1,0,0,0
access_marketplace_config_manager,marketplace.config.manager,model_marketplace_config,base.group_system,1,1,1,1

# Pattern: _user (read-only), _manager (full access)
# Groups: base.group_user (all users), base.group_system (admins)
```

### Security Groups

- **Users**: Read-only access to marketplace data
- **System Administrators**: Full access to configuration and management
- **No Custom Groups**: Uses standard Odoo security model

---

## 8. Performance Considerations

### Batch Processing

- **Default Batch Size**: 100 records per operation
- **Configurable**: Via `marketplace.config.batch_size`
- **Memory Management**: Processes large datasets in chunks

### Queue Job Channels

```python
# Dedicated channel for marketplace operations
order.with_delay(channel='marketplace')._sync_to_marketplace()

# Prevents blocking main queue
# Allows parallel processing
```

### Database Optimization

- **Indexed Fields**: `cartona_id` fields have database indexes
- **Efficient Queries**: Uses `search()` with appropriate filters
- **Minimal SQL**: Leverages ORM efficiently

### API Rate Limiting

- **Timeout Control**: 30-second default timeout
- **Retry Logic**: 3 attempts with exponential backoff
- **Connection Pooling**: Reuses HTTP connections where possible

This technical overview provides developers with comprehensive understanding of the module's architecture, implementation patterns, and integration points within the Odoo framework.
