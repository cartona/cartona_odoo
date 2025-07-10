## Dashboard Statistics Fix

### Problem
- Dashboard was showing incremental counts (adding 25 each time sync is performed)
- Real data: 25 products, 15 orders
- Dashboard was showing cumulative sync operations instead of actual totals

### Solution Implemented

#### 1. Fixed Statistics Calculation
- **Before**: `_update_sync_stats()` was adding to existing counts
- **After**: `_update_sync_stats()` can now set actual totals or increment based on `is_increment` parameter
- Dashboard now shows actual count of products/orders with `cartona_id` field

#### 2. Enhanced Sync Notifications
- **Product Sync**: Shows "Synced X products (Y new, Z total synced)"
- **Order Pull**: Shows "Pulled X orders (Y new, Z total pulled)"
- Notifications now display meaningful differences, not just "sync started"

#### 3. Added Statistics Refresh
- New `recalculate_sync_stats()` method counts actual synced items
- "Refresh Stats" button in configuration form
- Automatic stats refresh when configuration form is loaded
- Automatic stats initialization when configuration is created

#### 4. Dashboard Behavior Changes
- **Products Synced**: Shows total products with `cartona_id != False`
- **Orders Pulled**: Shows total orders with `cartona_id != False`
- Counts remain stable between syncs (no more incremental increases)
- Only increases when new items are actually synced from marketplace

### Usage
1. **Manual Sync**: Click "Sync Products" or "Pull Orders" - see actual results
2. **Refresh Stats**: Click "Refresh Stats" button to recalculate dashboard numbers
3. **Automatic**: Dashboard automatically shows correct totals when opened

### Technical Details
- Products counted: `product.template` records with `cartona_id != False`
- Orders counted: `sale.order` records with `cartona_id != False`
- Real-time difference calculation shows newly synced items in notifications
- Statistics persist correctly between sessions
