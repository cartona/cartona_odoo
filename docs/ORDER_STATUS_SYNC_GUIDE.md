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
```

**Key Methods:**
- `_filter_orders_for_sync()`: Applies business rules before sync
- `_map_odoo_status_to_marketplace()`: Basic status mapping
- `_map_combined_status_to_marketplace()`: Enhanced mapping with delivery state
- `_sync_status_to_marketplace()`: Core sync implementation

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