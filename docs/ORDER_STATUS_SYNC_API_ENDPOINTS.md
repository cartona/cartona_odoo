# Order Status Sync API Endpoints

## Overview

The order status sync now uses Cartona's single order endpoint by default for better error handling and more precise API responses. This document explains the available endpoints and when to use each.

## Available Endpoints

### 1. Single Order Update (Primary)

**Used by default for all order status sync operations**

```
POST /api/v1/order/update-order-status/{hashed_id}
```

**Example:**
```
POST /api/v1/order/update-order-status/632717520571

Body:
{
    "status": "approved",
    "hashed_id": "632717520571"
}
```

**Advantages:**
- Better error responses for individual orders
- Clearer API semantics for single order operations
- Immediate feedback if order ID is invalid
- More granular error handling

### 2. Bulk Order Update (Available for multiple orders)

```
POST /api/v1/order/update-order-status
```

**Example:**
```
POST /api/v1/order/update-order-status

Body:
[
    {
        "hashed_id": "632717520571",
        "status": "approved"
    },
    {
        "hashed_id": "611517520572", 
        "status": "delivered",
        "retailer_otp": "123456"
    }
]
```

**Use Cases:**
- Updating multiple orders at once
- Batch operations
- Mass status changes

## Implementation Details

### Single Order Sync (Default Behavior)

```python
# In sale_order.py _sync_status_to_marketplace()
result = api_client.update_single_order_status(self, marketplace_status)
```

**API Call Structure:**
```python
def update_single_order_status(self, order_record, new_status):
    endpoint = f'order/update-order-status/{order_record.cartona_id}'
    
    status_data = {
        'status': new_status,
        'hashed_id': order_record.cartona_id
    }
    
    # Optional fields
    if new_status == 'delivered' and requires_otp:
        status_data['retailer_otp'] = get_otp()
    
    if new_status == 'cancelled_by_supplier':
        status_data['cancellation_reason'] = get_reason()
    
    return self._make_api_request(endpoint, method='POST', data=status_data)
```

### Bulk Order Sync (Available for special cases)

```python
# New method for bulk operations
result = api_client.bulk_update_order_status(order_records, status_list)
```

## Status Values

All endpoints support these status values:

### Standard Statuses
- `pending` - Order created, awaiting action
- `approved` - Order confirmed by supplier
- `assigned_to_salesman` - Order marked as shipped
- `delivered` - Order completed/delivered
- `cancelled_by_supplier` - Order cancelled by supplier

### Special Statuses
- `synced` - Confirms receipt of order data (doesn't change actual status)
- `editing` - Retailer is editing order
- `cancelled_by_retailer` - Order cancelled by customer
- `returned` - Order returned/not received

## Optional Fields

### For Delivery Confirmation
```json
{
    "status": "delivered",
    "hashed_id": "632717520571",
    "retailer_otp": "123456"
}
```

**Required when:**
- Status is `delivered`
- Payment method is `installment` or `wallet_top_up`

### For Cancellations
```json
{
    "status": "cancelled_by_supplier", 
    "hashed_id": "632717520571",
    "cancellation_reason": "out_of_stock"
}
```

**Valid cancellation reasons:**
- `out_of_stock`
- `cannot_deliver_the_order`
- `delayed_order`
- `supplier_asked_me_to_cancel`
- `expired_products`
- `missing_items`

## Response Handling

### Success Response
```json
// Single endpoint typically returns empty object or success confirmation
{}

// Or detailed response
{
    "message": "Order status updated successfully",
    "order_id": "632717520571",
    "new_status": "approved"
}
```

### Error Response
```json
{
    "error": "Order not found",
    "details": "No order exists with hashed_id: 632717520571"
}
```

## Logging and Debugging

### Request Logging
```
INFO: Updating single order status for 632717520571 to approved
INFO: API Call: POST order/update-order-status/632717520571
INFO: Request Body: {'status': 'approved', 'hashed_id': '632717520571'}
```

### Response Logging
```
INFO: Cartona API response for single order 632717520571: {}
```

### Error Logging
```
ERROR: Failed to sync order SO001 status: API Error 404: Order not found
```

## Testing

### Manual Testing
1. Use "Test Sync" button to see API call details without making actual request
2. Check logs for actual API calls and responses
3. Monitor `marketplace_sync_status` field for success/error state

### Debug Commands
```python
# Test single order endpoint
order = env['sale.order'].search([('cartona_id', '!=', False)], limit=1)
api_client = env['marketplace.api'].with_context(
    marketplace_config_id=order.marketplace_config_id.id
)

result = api_client.update_single_order_status(order, 'approved')
print(f"Result: {result}")

# Test API call directly
endpoint = f'order/update-order-status/{order.cartona_id}'
body = {'status': 'approved', 'hashed_id': order.cartona_id}
raw_result = api_client._make_api_request(endpoint, 'POST', body)
print(f"Raw API result: {raw_result}")
```

## Migration from Bulk to Single

### What Changed
- Default sync method changed from `update_order_status()` to `update_single_order_status()`
- URL format: `order/update-order-status` → `order/update-order-status/{hashed_id}`
- Body format: `[{...}]` → `{...}` (object instead of array)
- Field order: `hashed_id` moved after `status` in body

### Backward Compatibility
- Bulk endpoint still available via `update_order_status()` method
- New `bulk_update_order_status()` method for true bulk operations
- All existing functionality preserved

### Benefits
- Better error messages for individual orders
- More precise API semantics
- Reduced payload size for single orders
- Clearer debugging and logging

## Best Practices

1. **Use Single Endpoint** for individual order status changes (default behavior)
2. **Use Bulk Endpoint** only when updating multiple orders simultaneously
3. **Monitor Logs** for API request/response details
4. **Handle OTP** for delivery confirmations properly
5. **Provide Cancellation Reasons** for better tracking
6. **Test with Debug Mode** before production deployment

This change improves the reliability and clarity of order status synchronization between Odoo and Cartona. 