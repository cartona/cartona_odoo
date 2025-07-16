# Cartona State Transitions Implementation

## Overview
This implementation provides **proper Odoo action calls** instead of just setting order states when pulling orders from Cartona marketplace. This ensures all business consequences (delivery creation, inventory allocation, etc.) happen correctly.

## Status Mapping

| Cartona Status | Odoo Action Called | Result | Comments |
|---|---|---|---|
| `approved` | `action_confirm()` | Draft → Sale (creates deliveries) | Creates delivery orders, allocates inventory |
| `assigned_to_salesman` | `action_confirm()` + `action_assign()` | Sale + Ready delivery | Reserves inventory for delivery |
| `delivered` | `action_confirm()` + `action_assign()` + `button_validate()` | Sale + Done delivery | Completes delivery, updates stock |
| `cancelled` | `action_cancel()` | Cancelled (cancels deliveries) | Releases inventory, cancels all related operations |
| `return` | Log only | Manual handling required | Complex returns need human intervention |

## Code Architecture

### Core Components

#### 1. Order Processor (`marketplace_order_processor.py`)
- **`_create_new_order()`**: Creates orders in draft, then applies proper transitions
- **`_apply_cartona_state_action()`**: Core method that calls proper Odoo actions
- **`_complete_delivery()`**: Auto-fills quantities and validates deliveries
- **`_update_existing_order()`**: Handles status changes for existing orders

#### 2. Sale Order Extensions (`sale_order.py`)
- **`write()`**: Triggers marketplace sync on status changes
- **`_filter_orders_for_sync()`**: Applies business rules for sync filtering
- **`action_fill_move_quantity_with_demand()`**: Utility for bulk quantity filling

#### 3. Configuration (`marketplace_config.py`)
- **`get_state_mapping()`**: Provides status mapping configuration
- **`manual_pull_orders()`**: Manual order import with statistics

## Key Features

### ✅ **Proper Business Logic**
```python
# Instead of just setting state = 'sale'
order.action_confirm()  # Creates deliveries, allocates inventory, sends notifications

# Instead of just setting state = 'cancel'  
order.action_cancel()   # Cancels deliveries, releases inventory, handles consequences
```

### ✅ **Smart State Management**
- Orders always start in `draft` state
- Transitions happen in proper sequence (draft → sale → done)
- Prevents sync loops with `skip_marketplace_sync=True` context
- Idempotent operations (no duplicate processing)

### ✅ **Auto-Delivery Completion**
```python
# Automatically fills move quantities with demand
for move in picking.move_ids:
    move.quantity_done = move.product_uom_qty

# Validates deliveries and updates inventory
picking.button_validate()
```

### ✅ **Comprehensive Error Handling**
- Graceful handling of failed transitions
- Error messages stored in order records
- Comprehensive logging for debugging
- Rollback on failures

## Implementation Flow

### New Order Creation
```
1. Pull order from Cartona API
2. Create order in 'draft' state
3. Create order lines
4. Apply Cartona status action:
   - approved → action_confirm()
   - assigned_to_salesman → action_confirm() + action_assign()
   - delivered → action_confirm() + action_assign() + button_validate()
   - cancelled → action_cancel()
5. Log results and update sync status
```

### Existing Order Update
```
1. Check if Cartona status changed
2. Update marketplace fields
3. If status changed:
   - Apply new status action
   - Log transition
4. Update sync status
```

## Business Rules

### Sync Filtering
- **Orders delivered by Cartona**: Only sync cancellation status
- **Orders delivered by Supplier**: Sync all status changes
- **No cartona_id**: Skip sync entirely

### State Transition Rules
- **Draft orders**: Can transition to any state
- **Confirmed orders**: Can be cancelled or completed
- **Done orders**: Cannot be modified
- **Cancelled orders**: Cannot be reactivated

## Usage Examples

### Manual Testing
```python
# Test state transitions for a specific order
processor = env['marketplace.order.processor']
result = processor.test_cartona_state_transitions('cartona_order_123')

# Result shows before/after states for each transition
print(result['test_results'])
```

### Manual Order Pull
```python
# Pull orders from Cartona dashboard
config = env['marketplace.config'].browse(1)
result = config.manual_pull_orders()
```

### Bulk Quantity Filling
```python
# Fill all delivery quantities with demand
order = env['sale.order'].browse(123)
order.action_fill_move_quantity_with_demand()
```

## Error Handling

### Common Issues and Solutions

1. **Inventory Not Available**
   - Error: "Cannot assign delivery - insufficient stock"
   - Solution: Check product availability, adjust quantities

2. **Invalid State Transition**
   - Error: "Cannot confirm cancelled order"
   - Solution: Check order state before applying transitions

3. **API Connection Issues**
   - Error: "Failed to sync status to marketplace"
   - Solution: Check API credentials and network connectivity

### Debugging Tools

1. **Check sync logs**: `marketplace.sync.log` model
2. **Test state transitions**: `test_cartona_state_transitions()` method
3. **View order sync status**: Check `marketplace_sync_status` field
4. **Error messages**: Check `marketplace_error_message` field

## Benefits

- **Consistency**: Orders follow proper Odoo workflows
- **Reliability**: All related records handled correctly
- **Traceability**: Full logging of state changes
- **Maintainability**: Clean, well-documented code
- **Performance**: Efficient batch processing
- **Flexibility**: Configurable state mappings
- **Error Recovery**: Comprehensive error handling 