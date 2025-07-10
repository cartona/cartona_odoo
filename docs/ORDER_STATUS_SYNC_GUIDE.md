# Order Status Sync Implementation Guide

## Overview

This document explains the implementation of bidirectional order status synchronization between Odoo and Cartona marketplace. The system respects business rules based on delivery responsibility and provides robust error handling.

## Key Features

### 1. Automatic Status Sync
- **Trigger**: Automatically syncs when order state changes in Odoo
- **Method**: Uses background jobs (queue system) for non-blocking operation
- **Business Rules**: Respects delivery responsibility constraints

### 2. Manual Sync Options
- **Standard Sync**: Basic status mapping using `action_manual_sync_to_marketplace()`
- **Enhanced Sync**: Advanced mapping considering delivery state using `action_sync_enhanced_status()`
- **Test Mode**: Diagnostic tool using `action_test_status_sync()`

### 3. Business Logic Implementation
- **Delivered by Supplier**: Can sync any status change to Cartona
- **Delivered by Cartona**: Can only sync cancellation status to Cartona

## Implementation Details

### Core Models

#### 1. Sale Order Extensions (`models/sale_order.py`)

**New Fields:**
```python
delivered_by = fields.Selection([
    ('delivered_by_supplier', 'Delivered by Supplier'),
    ('delivered_by_cartona', 'Delivered by Cartona')
], string='Delivered By', default='delivered_by_supplier')

marketplace_mapped_status = fields.Char(
    string="Mapped Status", 
    help="Marketplace status mapped to Odoo state when imported",
    readonly=True
)
```

**Key Methods:**
- `_filter_orders_for_sync()`: Applies business rules before sync
- `_map_odoo_status_to_marketplace()`: Basic status mapping
- `_map_combined_status_to_marketplace()`: Enhanced mapping with delivery state
- `_sync_status_to_marketplace()`: Core sync implementation

### Status Mapping When Pulling Orders

#### 1. Automatic Status Mapping (`models/marketplace_order_processor.py`)

**New Method:**
```python
def _map_cartona_status_to_odoo(self, cartona_status):
    """Map Cartona status to Odoo sale order state"""
    cartona_to_odoo_mapping = {
        'pending': 'draft',
        'approved': 'sale', 
        'delivered': 'done',
        'cancelled_by_supplier': 'cancel',
        'cancelled_by_cartona': 'cancel',
        'cancelled': 'cancel',
    }
    return cartona_to_odoo_mapping.get(cartona_status, 'draft')
```

#### 2. Enhanced Order Creation

When pulling orders from Cartona, the system now:

1. **Stores Original Status**: Keeps the original Cartona status in `marketplace_status` field
2. **Maps to Odoo State**: Automatically converts Cartona status to appropriate Odoo sale order state
3. **Records Mapping**: Stores the mapping relationship in `marketplace_mapped_status` field (e.g., "approved → sale")
4. **Sets Sync Status**: Marks order as 'synced' with sync timestamp

**Example Mapping:**
- Cartona "pending" → Odoo "draft" → Stored as "pending → draft"
- Cartona "approved" → Odoo "sale" → Stored as "approved → sale"  
- Cartona "delivered" → Odoo "done" → Stored as "delivered → done"
- Cartona "cancelled_by_supplier" → Odoo "cancel" → Stored as "cancelled_by_supplier → cancel"

#### 3. Order Update Processing

When updating existing orders:
- Only updates Odoo state if Cartona status has changed
- Maintains audit trail of status changes
- Updates mapping display to show current relationship
- Logs all status transitions for debugging

### UI Enhancements for Status Mapping

#### 1. Form View Updates
The marketplace tab now displays:
- **Marketplace Status**: Original status from Cartona
- **Mapped Status**: Shows the mapping (e.g., "approved → sale")
- **Delivered By**: Business rule control
- **Sync Status**: Current synchronization state

#### 2. Tree View Columns
Optional columns added for:
- Marketplace Status
- Mapped Status  
- Delivery Responsibility
- Sync Status and Date

### Benefits of Stored Mapping

1. **Audit Trail**: Clear visibility of how marketplace status was interpreted
2. **Debugging**: Easy identification of mapping issues
3. **Business Intelligence**: Better reporting on status transitions
4. **Troubleshooting**: Quick identification of sync problems
5. **Compliance**: Full traceability of order status changes

## Order Updates During Pull Operations

### 1. Enhanced Order Processing Logic

When pulling orders from Cartona, the system now handles both new orders and existing order updates:

#### **New Order Creation**
- Creates order with mapped Odoo state based on Cartona status
- Sets all marketplace fields and sync status
- Creates order lines with product matching

#### **Existing Order Updates**
- **Comprehensive Updates**: Updates customer info, payment method, delivery responsibility
- **Status Updates**: Maps new Cartona status to Odoo state with validation
- **Order Line Updates**: Updates existing lines and adds new ones
- **State Transition Validation**: Prevents invalid order state changes

### 2. Order Update Process (`_update_existing_order`)

#### **Customer Information**
```python
# Updates customer if changed
customer = self._find_or_create_customer(order_data['customer_data'], config)
if customer.id != order.partner_id.id:
    # Updates order with new customer
```

#### **Status Updates with Validation**
```python
# Only updates state if transition is valid
valid_transitions = {
    'draft': ['sale', 'cancel'],
    'sent': ['sale', 'cancel'], 
    'sale': ['done', 'cancel'],
    'done': [],  # Final state
    'cancel': []  # Final state
}
```

#### **Order Line Management**
- **Update Existing Lines**: Matches by `marketplace_line_id`
- **Add New Lines**: Creates lines for new products
- **Preserve Existing**: Conservative approach - doesn't remove lines
- **Product Matching**: Uses `_find_or_create_product` for consistency

### 3. Enhanced Tracking and Notifications

#### **Statistics Tracking**
- **New Orders**: Tracks newly created orders
- **Updated Orders**: Tracks existing orders that were updated
- **Processing Results**: Detailed success/failure tracking

#### **Notification Messages**
```
Examples:
- "Pulled 5 orders: 3 new, 2 updated (25 total in system)"
- "Pulled 3 new orders (25 total in system)"
- "Updated 2 existing orders (25 total in system)"
- "No new orders found (25 total in system)"
```

#### **Logging Enhancements**
```python
# Enhanced log entry
log_message = f"Successfully processed {orders_processed} orders ({orders_new} new, {orders_updated} updated)"
```

### 4. State Transition Management

#### **Valid Transitions**
- `draft` → `sale`, `cancel`
- `sent` → `sale`, `cancel`
- `sale` → `done`, `cancel`
- `done` → *(no transitions - final state)*
- `cancel` → *(no transitions - final state)*

#### **Blocked Transitions**
When invalid transitions are attempted:
```python
# Shows blocked transition in mapping
marketplace_mapped_status = "delivered → done (blocked)"
```

### 5. Business Benefits

#### **Data Consistency**
- Ensures orders stay synchronized with marketplace
- Prevents data divergence between systems
- Maintains accurate order status at all times

#### **Business Process Support**
- Handles order modifications from marketplace
- Updates customer information changes
- Supports order line adjustments

#### **Operational Efficiency**
- Reduces manual order management
- Provides real-time order synchronization
- Eliminates duplicate order handling

#### 2. Marketplace API Updates (`models/marketplace_api.py`)

**Enhanced Methods:**
- `update_order_status()`: Uses correct Cartona API format
- `update_single_order_status()`: Single order endpoint for better error handling
- Supports OTP for delivery confirmation
- Handles cancellation reasons

### Status Mapping

#### Basic Mapping (Odoo → Cartona)
```python
status_mapping = {
    'draft': 'pending',
    'sent': 'pending', 
    'sale': 'approved',
    'done': 'delivered',
    'cancel': 'cancelled_by_supplier',
}
```

#### Enhanced Mapping (Order + Delivery State)
```python
# Examples:
('sale', 'confirmed') → 'approved'      # Confirmed but not shipped
('sale', 'done') → 'assigned_to_salesman'  # Shipped
('done', 'done') → 'delivered'         # Fully completed
('cancel', '*') → 'cancelled_by_supplier'  # Any cancellation
```

### API Integration

#### Cartona API Format
```python
# Bulk update format
status_data = [{
    'hashed_id': order.cartona_id,
    'status': new_status,
    # Optional fields:
    'retailer_otp': '123456',  # For delivery confirmation
    'cancellation_reason': 'out_of_stock'  # For cancellations
}]
```

#### Endpoints Used
- **Bulk**: `POST /api/v1/order/update-order-status`
- **Single**: `POST /api/v1/order/update-order-status/{hashed_id}`

## Usage Examples

### 1. Automatic Sync (Default Behavior)

When an order state changes:
```python
# This will automatically trigger sync if conditions are met
order.write({'state': 'sale'})  # Triggers sync to 'approved' status
```

### 2. Manual Sync

```python
# Standard sync
order.action_manual_sync_to_marketplace()

# Enhanced sync (considers delivery state)
order.action_sync_enhanced_status()
```

### 3. Testing and Debugging

```python
# Test sync logic without actually calling API
order.action_test_status_sync()
```

### 4. Business Rule Examples

```python
# Supplier delivery - can sync any status
order = Order.create({
    'delivered_by': 'delivered_by_supplier',
    'state': 'sale'  # Will sync as 'approved'
})

# Cartona delivery - only cancellation allowed
order = Order.create({
    'delivered_by': 'delivered_by_cartona',
    'state': 'sale'  # Will NOT sync (blocked by business rules)
})

order.write({'state': 'cancel'})  # Will sync as 'cancelled_by_supplier'
```

## User Interface

### Sale Order Form Enhancements

**New Buttons:**
- **Sync Status**: Standard sync button
- **Enhanced Sync**: Advanced sync with delivery state consideration
- **Test Sync**: Diagnostic tool showing sync logic

**New Fields:**
- **Delivered By**: Controls sync permissions
- **Marketplace Payment Method**: Shows payment type
- **Marketplace Sync Date**: Last sync timestamp

### Tree View and Filters

**New Columns:**
- Delivered By
- Marketplace Sync Status
- External Order ID

**New Filters:**
- Delivered by Supplier
- Delivered by Cartona
- Sync Errors
- Group by Delivery Responsibility

## Error Handling

### Sync Status Tracking
```python
marketplace_sync_status = fields.Selection([
    ('not_synced', 'Not Synced'),
    ('syncing', 'Syncing'),
    ('synced', 'Synced'),
    ('error', 'Sync Error'),
])
```

### Error Scenarios
1. **Missing cartona_id**: Sync skipped with warning
2. **Business rule violation**: Sync blocked with notification
3. **API failure**: Error logged with retry capability
4. **Network timeout**: Graceful handling with retry

### Logging
- All sync attempts logged with details
- Error messages stored in `marketplace_error_message`
- Debug logging for API requests/responses

## Order Creation Integration

### Setting delivered_by During Import

```python
# In marketplace_order_processor.py
delivered_by = order_data.get('delivered_by', 'delivered_by_supplier')
if delivered_by not in ['delivered_by_supplier', 'delivered_by_cartona']:
    delivered_by = 'delivered_by_supplier'  # Safe default

order_vals = {
    'delivered_by': delivered_by,
    'marketplace_payment_method': payment_method,
    # ... other fields
}
```

## Configuration and Setup

### Required Configuration
1. **Marketplace Config**: Active marketplace configuration
2. **External IDs**: Orders must have `cartona_id` set
3. **Queue Jobs**: Background job system must be configured

### Optional Features
- OTP integration for delivery confirmation
- Custom cancellation reason mapping
- Enhanced delivery state tracking

## Best Practices

### 1. Error Monitoring
- Monitor `marketplace_sync_status` for errors
- Check logs for API failures
- Use dashboard for sync overview

### 2. Business Rule Management
- Set `delivered_by` correctly during order import
- Train users on sync restrictions
- Use test mode to understand sync behavior

### 3. Performance Optimization
- Background jobs prevent UI blocking
- Bulk operations when possible
- Appropriate error handling and retries

## Troubleshooting

### Common Issues

1. **Sync Not Triggered**
   - Check if order has `cartona_id`
   - Verify `is_marketplace_order` is True
   - Ensure business rules allow sync

2. **API Errors**
   - Verify marketplace configuration
   - Check API credentials
   - Review request format in logs

3. **Business Rule Blocks**
   - Check `delivered_by` field value
   - Understand sync restrictions
   - Use test mode to diagnose

### Debug Commands

```python
# Check sync eligibility
orders_to_sync = order.filtered('is_marketplace_order')._filter_orders_for_sync()

# Manual API test
api_client = env['marketplace.api'].with_context(marketplace_config_id=config_id)
result = api_client.update_order_status(order, 'approved')

# View sync logs
logs = env['marketplace.sync.log'].search([('order_id', '=', order.id)])
```

## API Reference

### Main Methods

#### SaleOrder
- `_filter_orders_for_sync()`: Apply business rules
- `_trigger_status_sync()`: Queue background sync
- `_sync_status_to_marketplace()`: Execute sync
- `_map_odoo_status_to_marketplace()`: Basic mapping
- `_map_combined_status_to_marketplace()`: Enhanced mapping

#### MarketplaceAPI
- `update_order_status(order, status)`: Bulk update API
- `update_single_order_status(order, status)`: Single update API

### Configuration
- Background jobs: `queue_job` module required
- API endpoints: Cartona marketplace integration
- Business rules: Based on `delivered_by` field

This implementation provides a robust, business-rule-aware order status sync system that handles the complexities of marketplace integration while maintaining data integrity and user experience. 