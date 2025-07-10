# Order Status Sync Troubleshooting Guide

## Error Fixed: "'list' object has no attribute 'get'"

### What Was the Problem?

The Cartona API was returning a list response for bulk order status updates, but our code expected a dictionary with a `.get()` method. This caused the error when trying to check `result.get('success')`.

### What Was Fixed?

1. **Added Response Normalization**: Created `_normalize_api_response()` method that ensures all API responses are returned as dictionaries with consistent format.

2. **Updated All API Methods**: Applied the normalization to all methods that call the Cartona API:
   - `update_order_status()`
   - `update_single_order_status()`
   - `bulk_update_products()`
   - `update_product_stock()`
   - `bulk_update_stock()`
   - `pull_orders()`

3. **Enhanced Error Handling**: Added better error checking and logging in the sync process.

### How to Test the Fix

#### 1. Test Manual Sync

1. Go to a sales order that has:
   - `cartona_id` field populated
   - `is_marketplace_order` = True
   - `marketplace_config_id` set

2. Use any of the sync buttons:
   - **Sync Status**: Basic sync
   - **Enhanced Sync**: Advanced sync with delivery state
   - **Test Sync**: Shows what would happen without API call

#### 2. Test Automatic Sync

```python
# Change order status to trigger automatic sync
order = env['sale.order'].search([('cartona_id', '!=', False)], limit=1)
order.action_confirm()  # Should trigger sync
```

#### 3. Debug API Response

```python
# Manual API test
order = env['sale.order'].search([('cartona_id', '!=', False)], limit=1)
api_client = env['marketplace.api'].with_context(
    marketplace_config_id=order.marketplace_config_id.id
)

# Test the normalization directly
raw_result = api_client._make_api_request('order/update-order-status', 'POST', [{
    'hashed_id': order.cartona_id,
    'status': 'approved'
}])

normalized_result = api_client._normalize_api_response(raw_result)
print(f"Raw result type: {type(raw_result)}")
print(f"Raw result: {raw_result}")
print(f"Normalized result: {normalized_result}")
```

### Expected Behavior Now

#### Success Case
```python
# API returns list: []
# Normalized to: {'success': True, 'data': [], 'message': 'Empty response list'}

# API returns dict: {'status': 'updated'}  
# Normalized to: {'success': True, 'data': {'status': 'updated'}}
```

#### Error Case
```python
# API returns error dict: {'success': False, 'error': 'Invalid order'}
# Returned as-is: {'success': False, 'error': 'Invalid order'}
```

### How to Monitor

1. **Check Sync Status**:
   ```python
   # View orders with sync errors
   orders = env['sale.order'].search([('marketplace_sync_status', '=', 'error')])
   for order in orders:
       print(f"Order: {order.name}, Error: {order.marketplace_error_message}")
   ```

2. **Check Logs**:
   Look for log entries with "Cartona API response" to see actual API responses.

3. **Use Test Mode**:
   The "Test Sync" button shows exactly what would happen without making API calls.

### Business Rules Reminder

The sync respects delivery responsibility:

- **Delivered by Supplier**: Can sync any status change to Cartona
- **Delivered by Cartona**: Can only sync cancellation status to Cartona

### Common Issues After Fix

1. **API Authentication**: Ensure marketplace config has valid credentials
2. **Missing cartona_id**: Orders need external ID to sync
3. **Business Rule Blocks**: Check `delivered_by` field value
4. **Network Issues**: API timeout or connection problems

### Verification Commands

```python
# Check if an order can sync
order = env['sale.order'].browse(ORDER_ID)
can_sync = order.filtered('is_marketplace_order')._filter_orders_for_sync()
print(f"Can sync: {bool(can_sync)}")

# Test response normalization
api = env['marketplace.api']
test_responses = [
    [],  # Empty list
    [{'id': 1}],  # List with data
    {'key': 'value'},  # Dict without success
    {'success': True, 'data': 'test'},  # Dict with success
    None,  # None response
]

for response in test_responses:
    normalized = api._normalize_api_response(response)
    print(f"Input: {response} -> Output: {normalized}")
```

### Success Indicators

✅ **Fixed Successfully** when:
- No more "'list' object has no attribute 'get'" errors
- Sync status updates correctly to 'synced' or 'error'  
- API responses are properly logged
- Manual sync buttons work without errors
- Automatic sync triggers on state changes

🔧 **Still Having Issues?**
1. Check the marketplace configuration
2. Verify API credentials  
3. Check network connectivity
4. Review the detailed error logs
5. Use the test sync feature to diagnose

The normalization fix ensures that regardless of what type of response the Cartona API returns (list, dict, or other), our code will always have a consistent dictionary interface to work with. 