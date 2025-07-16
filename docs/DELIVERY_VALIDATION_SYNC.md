# Delivery Validation Sync Feature

## Overview

This feature implements automatic synchronization of delivery validation status from Odoo to Cartona marketplace. When a user clicks "Validate" on a delivery in Odoo and the delivery status becomes "done", the system automatically updates the corresponding order status in Cartona to "assigned_to_salesman".

## Business Context

In the Cartona marketplace workflow:
- **assigned_to_salesman** status indicates that the supplier has marked the order as shipped/delivered
- This status change notifies the retailer that their order is on its way
- It represents the transition from "prepared for delivery" to "actually shipped"

## Implementation Details

### Files Modified

1. **models/stock_move.py**
   - Extended `StockPicking` class with `button_validate()` override
   - Added logic to detect delivery validation and trigger sync

2. **models/sale_order.py**
   - Added `_sync_delivery_validation_to_cartona()` method
   - Handles the actual API call to update Cartona status

3. **docs/BIDIRECTIONAL_STATUS_SYNC.md**
   - Updated documentation to include the new feature

### Key Features

#### Automatic Trigger
- **When**: User clicks "Validate" button on delivery
- **Condition**: Delivery state becomes 'done'
- **Scope**: Only outgoing deliveries (shipments)

#### Business Rule Compliance
- Only syncs for orders with `delivered_by='delivered_by_supplier'`
- Skips orders delivered by Cartona (as per business rules)
- Requires both `cartona_id` and `marketplace_config_id` on the order

#### Async Processing
- Uses background jobs (`with_delay()`) to prevent UI blocking
- Queued with 'marketplace' channel for proper processing
- Descriptive job names for monitoring

#### Error Handling
- Comprehensive logging at all stages
- Sync status tracking on the order record
- Error messages stored for troubleshooting
- Marketplace sync log entries for audit trail

## Code Flow

```python
# 1. User clicks "Validate" on delivery
StockPicking.button_validate()

# 2. Original validation logic executes
result = super().button_validate()

# 3. Check conditions
if (outgoing_delivery and 
    state_is_done and 
    linked_to_cartona_order and 
    delivered_by_supplier):
    
    # 4. Queue background job
    sale_order.with_delay()._sync_delivery_validation_to_cartona()

# 5. Background job executes
def _sync_delivery_validation_to_cartona():
    # 6. Call Cartona API
    api_client.update_single_order_status(order, 'assigned_to_salesman')
    
    # 7. Update order sync status
    order.marketplace_sync_status = 'synced'
    order.marketplace_status = 'assigned_to_salesman'
    
    # 8. Log results
    marketplace.sync.log.create(...)
```

## API Integration

### Cartona API Endpoint
- **URL**: `POST /api/v1/order/update-order-status/{cartona_id}`
- **Body**: `{"status": "assigned_to_salesman", "hashed_id": "cartona_id"}`

### Status Mapping
- **Odoo**: Delivery state 'done' + Order state 'sale'
- **Cartona**: Order status 'assigned_to_salesman'

## Monitoring and Troubleshooting

### Sync Status Tracking
- Order field: `marketplace_sync_status`
- Values: 'not_synced', 'syncing', 'synced', 'error'
- Error details stored in: `marketplace_error_message`

### Logging
- **Success**: Info level logs with order details
- **Errors**: Error level logs with full exception details
- **Business Rule Skips**: Info level logs explaining why sync was skipped

### Marketplace Sync Log
- **Model**: `marketplace.sync.log`
- **Operation Type**: 'status_sync'
- **Includes**: Success/error counts, detailed error messages, timestamps

## Testing

### Manual Testing
1. Create a sales order with `cartona_id` and `delivered_by='delivered_by_supplier'`
2. Confirm the order (creates delivery)
3. Go to the delivery and click "Validate"
4. Check that:
   - Order `marketplace_sync_status` becomes 'synced'
   - Order `marketplace_status` becomes 'assigned_to_salesman'
   - Marketplace sync log entry is created
   - Cartona receives the status update

### Edge Cases to Test
1. **Order without cartona_id**: Should skip sync
2. **Order delivered_by_cartona**: Should skip sync
3. **API failure**: Should log error and update sync status
4. **Multiple deliveries**: Should only sync once when first delivery is validated
5. **Context skip_marketplace_sync**: Should skip sync

## Configuration

### Business Rules
- Configurable via `delivered_by` field on sales orders
- Default: 'delivered_by_supplier' (allows sync)
- Alternative: 'delivered_by_cartona' (blocks sync)

### Queue Configuration
- Channel: 'marketplace'
- Priority: Normal (default)
- Retry: Handled by queue system

## Security Considerations

- Uses existing marketplace API authentication
- Respects business rules to prevent unauthorized syncs
- Logs all operations for audit trail
- Background processing prevents timing attacks

## Future Enhancements

1. **Batch Processing**: Handle multiple deliveries in one API call
2. **Retry Logic**: Implement exponential backoff for failed syncs
3. **Real-time Notifications**: Notify users of sync status changes
4. **Advanced Filtering**: More granular control over which orders sync
5. **Performance Monitoring**: Track sync performance and API response times 