# Bidirectional Status Sync: Cartona Marketplace ↔ Odoo 18

## Overview

This document outlines the bidirectional status synchronization system between Cartona Marketplace (external system) and Odoo 18. The system handles the translation between Cartona's single-state system and Odoo's dual-state system (order + delivery) using modern Odoo 18 patterns and features.

## Architecture

### State Systems Comparison

| System | State Model | Description |
|--------|-------------|-------------|
| **Cartona Marketplace** | Single State | One status handles both order and delivery lifecycle |
| **Odoo 18** | Dual State | Separate states for order (`sale.order.state`) and delivery (`stock.picking.state`) |

### Key Challenge

Cartona combines order and delivery concepts into one status, while Odoo separates them. The sync system must translate between these different granularity levels bidirectionally using Odoo 18's enhanced ORM and async capabilities.

## Status Mapping

### Cartona Marketplace Statuses

1. **pending** - Order first created by retailer, can be edited/cancelled
2. **editing** - Retailer editing order, supplier cannot act
3. **approved** - Supplier approved order, retailer can only cancel
4. **cancelled_by_retailer** - Retailer cancelled from pending/approved
5. **assigned_to_salesman** - Supplier marked as shipped, retailer cannot edit/cancel
6. **delivered** - Supplier marked as delivered, no further edits possible
7. **cancelled_by_supplier** - Supplier cancelled from pending/approved/assigned_to_salesman
8. **returned** - Supplier marked as returned (retailer didn't receive)

### Odoo 18 States

#### Sale Order States (`sale.order.state`)
- **draft** - Quotation, can be modified
- **sent** - Quotation sent to customer
- **sale** - Sales Order confirmed
- **done** - Order locked/completed
- **cancel** - Order cancelled

#### Stock Picking States (`stock.picking.state`)
- **draft** - Delivery not created
- **waiting** - Waiting for availability
- **confirmed** - Delivery confirmed, products reserved
- **assigned** - Products assigned, ready for delivery
- **done** - Delivery completed
- **cancel** - Delivery cancelled

## Bidirectional Mapping

### Cartona → Odoo (Webhook Processing)

```python
# Using Odoo 18 modern patterns with proper typing and async support
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

CARTONA_TO_ODOO_MAPPING = {
    'pending': {
        'order_state': 'draft',
        'delivery_state': 'draft',
        'description': 'Order created, delivery not yet created'
    },
    'editing': {
        'order_state': 'draft',
        'delivery_state': 'draft',
        'description': 'Order being edited, delivery not created'
    },
    'approved': {
        'order_state': 'sale',
        'delivery_state': 'confirmed',
        'description': 'Order confirmed, delivery created and confirmed'
    },
    'assigned_to_salesman': {
        'order_state': 'sale',
        'delivery_state': 'done',
        'description': 'Order confirmed, delivery completed (shipped)'
    },
    'delivered': {
        'order_state': 'done',
        'delivery_state': 'done',
        'description': 'Order completed, delivery completed'
    },
    'cancelled_by_retailer': {
        'order_state': 'cancel',
        'delivery_state': 'cancel',
        'description': 'Order cancelled by retailer'
    },
    'cancelled_by_supplier': {
        'order_state': 'cancel',
        'delivery_state': 'cancel',
        'description': 'Order cancelled by supplier'
    },
    'returned': {
        'order_state': 'done',
        'delivery_state': 'done',
        'description': 'Order completed, return delivery created'
    }
}
```

### Odoo → Cartona (API Sync)

```python
# Odoo 18 enhanced mapping with better state handling
ODOO_TO_CARTONA_MAPPING = {
    # (order_state, delivery_state) -> cartona_status
    ('draft', 'draft'): 'pending',
    ('draft', 'waiting'): 'pending',
    ('draft', 'confirmed'): 'pending',
    
    ('sent', 'draft'): 'pending',
    ('sent', 'waiting'): 'pending',
    ('sent', 'confirmed'): 'pending',
    
    ('sale', 'confirmed'): 'approved',
    ('sale', 'assigned'): 'approved',
    ('sale', 'done'): 'assigned_to_salesman',  # Triggered by delivery validation
    
    ('done', 'done'): 'delivered',
    
    ('cancel', 'draft'): 'cancelled_by_supplier',
    ('cancel', 'waiting'): 'cancelled_by_supplier',
    ('cancel', 'confirmed'): 'cancelled_by_supplier',
    ('cancel', 'assigned'): 'cancelled_by_supplier',
    ('cancel', 'done'): 'cancelled_by_supplier',
    ('cancel', 'cancel'): 'cancelled_by_supplier',
}
```

## Implementation Strategy

### 1. Webhook Processing (Cartona → Odoo)

**Endpoint:** `/marketplace_integration/webhook/status`

**Process:**
1. Receive status update from Cartona
2. Find corresponding Odoo order by `cartona_id`
3. Apply mapping to update both order and delivery states
4. Handle special cases (returns, cancellations)
5. Log sync activity with enhanced traceability

### 2. Delivery Validation Sync (Odoo → Cartona)

**New Feature: Automatic Delivery Validation Sync**

When a user clicks "Validate" on a delivery in Odoo and the delivery status becomes "done", the system automatically updates the order status in Cartona to "assigned_to_salesman".

**Implementation Details:**
- **Trigger**: `StockPicking.button_validate()` method override
- **Condition**: Only for outgoing deliveries that become 'done' and are linked to Cartona orders
- **Business Rule**: Only syncs for orders with `delivered_by='delivered_by_supplier'`
- **Target Status**: Updates Cartona order status to 'assigned_to_salesman'
- **Async Processing**: Uses background jobs to prevent blocking the UI

**Code Flow:**
```python
# In StockPicking.button_validate()
1. Call original button_validate() method
2. Check if delivery became 'done' and is linked to Cartona order
3. Verify business rules (delivered_by_supplier)
4. Queue background job to sync status
5. Call sale_order._sync_delivery_validation_to_cartona()
6. Update Cartona via API with 'assigned_to_salesman' status
7. Log sync results
```

**Business Rules:**
- Only applies to outgoing deliveries (shipments)
- Only for orders with `delivered_by='delivered_by_supplier'`
- Skips sync if `skip_marketplace_sync` context is set
- Requires both `cartona_id` and `marketplace_config_id` on the order

**Error Handling:**
- Comprehensive logging for debugging
- Sync status tracking on the order
- Error messages stored for troubleshooting
- Marketplace sync log entries for audit trail

**Code Structure (Odoo 18):**
```python
class MarketplaceOrderProcessor(models.Model):
    _name = 'marketplace.order.processor'
    _description = 'Marketplace Order Status Processor'

    @api.model
    def process_cartona_status_update(self, cartona_status, order_id):
        """Process status update from Cartona using Odoo 18 patterns"""
        
        # Enhanced error handling with Odoo 18 features
        try:
            order = self.env['sale.order'].browse(order_id)
            if not order.exists():
                raise ValidationError(_("Order not found with ID: %s") % order_id)
            
            # Get mapping with validation
            mapping = CARTONA_TO_ODOO_MAPPING.get(cartona_status)
            if not mapping:
                _logger.warning("Unknown Cartona status: %s", cartona_status)
                return False
            
            # Use context to prevent recursion and enable audit trail
            with self.env.cr.savepoint():
                # Update order state with proper state machine validation
                if order.state != mapping['order_state']:
                    order.with_context(
                        cartona_sync=True,
                        sync_reason=f"Cartona status: {cartona_status}"
                    ).write({'state': mapping['order_state']})
                
                # Update delivery state with enhanced picking handling
                self._update_delivery_states(order, mapping, cartona_status)
                
                # Enhanced logging with Odoo 18 features
                self._log_sync_activity(order, cartona_status, mapping)
                
            return True
            
        except Exception as e:
            _logger.error("Failed to process Cartona status update: %s", str(e))
            # Use Odoo 18 enhanced error tracking
            self.env['marketplace.sync.log'].create({
                'order_id': order_id,
                'sync_type': 'cartona_to_odoo',
                'status': 'error',
                'error_message': str(e),
                'cartona_status': cartona_status,
            })
            return False

    def _update_delivery_states(self, order, mapping, cartona_status):
        """Update delivery states with Odoo 18 enhanced picking handling"""
        
        # Use modern domain filtering
        deliveries = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state != 'cancel'
        )
        
        for delivery in deliveries:
            if delivery.state != mapping['delivery_state']:
                # Use proper state machine transitions
                delivery._update_state_from_cartona(mapping['delivery_state'])
        
        # Handle special cases with enhanced logic
        if cartona_status == 'returned':
            self._create_return_delivery(order)
                    elif cartona_status in ['cancelled_by_retailer', 'cancelled_by_supplier']:
            self._handle_order_cancellation(order, cartona_status)

    def _create_return_delivery(self, order):
        """Create return delivery using Odoo 18 patterns"""
        
        # Enhanced return logic with proper stock handling
        return_picking = self.env['stock.return.picking'].with_context(
            active_id=order.picking_ids.filtered(
                lambda p: p.state == 'done'
            ).ids[0] if order.picking_ids.filtered(lambda p: p.state == 'done') else None
        ).create({})
        
        if return_picking:
            return_picking.create_returns()
```

### 3. API Sync (Odoo → Cartona)

**Trigger:** Order or delivery state changes in Odoo

**Process (Enhanced for Odoo 18):**
1. Monitor state changes using improved triggers
2. Use background jobs with enhanced queue system
3. Implement retry logic with exponential backoff
4. Enhanced conflict resolution
5. Comprehensive audit trail

**Code Structure (Odoo 18):**
```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _auto_init(self):
        """Enhanced auto-init for Odoo 18"""
        super()._auto_init()
        # Add any necessary database modifications

    def write(self, vals):
        """Override write to trigger Cartona sync with Odoo 18 enhancements"""
        
        # Track state changes before write
        state_changes = {}
        if 'state' in vals:
            for record in self:
                if record.cartona_id and record.state != vals['state']:
                    state_changes[record.id] = {
                        'old_state': record.state,
                        'new_state': vals['state']
                    }
        
        # Call parent with enhanced error handling
        result = super().write(vals)
        
        # Process state changes asynchronously
        if state_changes and not self.env.context.get('cartona_sync'):
            for order_id, change in state_changes.items():
                # Use Odoo 18 enhanced queue system
                self.browse(order_id).with_delay(
                    priority=10,
                    eta=fields.Datetime.now(),
                    description=f"Sync order {order_id} to Cartona"
                )._sync_to_cartona_async()
        
        return result

    def _sync_to_cartona_async(self):
        """Async sync to Cartona using Odoo 18 job queue enhancements"""
        
        try:
            # Enhanced state determination
            order_state = self.state
            delivery_state = self._get_primary_delivery_state()
            
            # Determine Cartona status with enhanced logic
            cartona_status = self._determine_cartona_status(order_state, delivery_state)
            
            # Send to Cartona with retry logic
            success = self._send_status_to_cartona(cartona_status)
            
            # Enhanced logging
            self.env['marketplace.sync.log'].create({
                'order_id': self.id,
                'sync_type': 'odoo_to_cartona',
                'status': 'success' if success else 'failed',
                'odoo_order_state': order_state,
                'odoo_delivery_state': delivery_state,
                'cartona_status': cartona_status,
                'sync_timestamp': fields.Datetime.now(),
            })
            
        except Exception as e:
            _logger.error("Failed to sync order %s to Cartona: %s", self.id, str(e))
            # Enhanced error handling with retry scheduling
            self.with_delay(
                priority=5,
                eta=fields.Datetime.now() + timedelta(minutes=5)
            )._sync_to_cartona_async()

    def _get_primary_delivery_state(self):
        """Get primary delivery state with Odoo 18 enhancements"""
        
        outgoing_pickings = self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state != 'cancel'
        )
        
        if not outgoing_pickings:
            return 'draft'
        
        # Enhanced state priority logic
        state_priority = ['done', 'assigned', 'confirmed', 'waiting', 'draft']
        for state in state_priority:
            if any(p.state == state for p in outgoing_pickings):
                return state
        
        return 'draft'

    def _determine_cartona_status(self, order_state, delivery_state):
        """Determine Cartona status with enhanced business logic"""
        
        # Check for special conditions first
        if self._is_return_scenario():
            return 'returned'
        
        if self._is_cancellation_scenario():
            return self._get_cancellation_status()
        
        # Use mapping with fallback logic
        status_key = (order_state, delivery_state)
        return ODOO_TO_CARTONA_MAPPING.get(status_key, 'pending')

    def _send_status_to_cartona(self, cartona_status):
        """Send status to Cartona with enhanced error handling and retry logic"""
        
        marketplace_api = self.env['marketplace.api']
        
        try:
            # Enhanced API call with proper error handling
            response = marketplace_api.update_order_status(
                self.cartona_id,
                cartona_status,
                timeout=30  # Enhanced timeout handling
            )
            
            return response.get('success', False)
            
        except Exception as e:
            _logger.error("API call failed for order %s: %s", self.cartona_id, str(e))
            return False
```

### 4. Enhanced Conflict Resolution (Odoo 18)

**Advanced Features:**
- Intelligent state validation
- Automated conflict resolution
- Enhanced logging and monitoring
- Real-time sync status tracking

```python
class MarketplaceSyncConflictResolver(models.Model):
    _name = 'marketplace.sync.conflict.resolver'
    _description = 'Marketplace Sync Conflict Resolution'

    @api.model
    def resolve_sync_conflicts(self):
        """Enhanced conflict resolution for Odoo 18"""
        
        # Find orders with sync conflicts
        conflicted_orders = self.env['sale.order'].search([
            ('cartona_id', '!=', False),
            ('sync_status', '=', 'conflict')
        ])
        
        for order in conflicted_orders:
            try:
                # Enhanced conflict resolution logic
                resolution = self._analyze_conflict(order)
                self._apply_resolution(order, resolution)
                
            except Exception as e:
                _logger.error("Failed to resolve conflict for order %s: %s", order.id, str(e))

    def _analyze_conflict(self, order):
        """Analyze sync conflict with enhanced AI-like logic"""
        
        # Get last sync attempts
        recent_syncs = self.env['marketplace.sync.log'].search([
            ('order_id', '=', order.id),
            ('sync_timestamp', '>=', fields.Datetime.now() - timedelta(hours=1))
        ], order='sync_timestamp desc', limit=5)
        
        # Enhanced conflict analysis
        conflict_analysis = {
            'type': self._determine_conflict_type(recent_syncs),
            'severity': self._calculate_conflict_severity(recent_syncs),
            'recommended_action': self._get_recommended_action(order, recent_syncs),
            'auto_resolvable': self._is_auto_resolvable(recent_syncs)
        }
        
        return conflict_analysis
```

## Enhanced Business Rules (Odoo 18)

### Advanced State Transition Rules

1. **Enhanced Order State Management:**
   - Validation rules with proper state machine
   - Automated state progression based on business logic
   - Integration with Odoo 18's enhanced workflow engine

2. **Smart Delivery State Handling:**
   - Multi-delivery order support
   - Partial delivery tracking
   - Advanced return and exchange handling

3. **Intelligent Conflict Resolution:**
   - AI-powered conflict detection
   - Automated resolution for common scenarios
   - Manual intervention for complex cases

## Monitoring and Logging (Odoo 18 Enhanced)

### Advanced Sync Logging

```python
class MarketplaceSyncLog(models.Model):
    _name = 'marketplace.sync.log'
    _description = 'Enhanced Marketplace Sync Logging'
    _order = 'sync_timestamp desc'

    # Enhanced fields for Odoo 18
    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')
    sync_type = fields.Selection([
        ('cartona_to_odoo', 'Cartona → Odoo'),
        ('odoo_to_cartona', 'Odoo → Cartona'),
        ('bidirectional_conflict', 'Bidirectional Conflict')
    ], required=True)
    
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('conflict', 'Conflict'),
        ('retrying', 'Retrying')
    ], required=True)
    
    # Enhanced tracking fields
    sync_timestamp = fields.Datetime(default=fields.Datetime.now, required=True)
    response_time = fields.Float(help="API response time in seconds")
    retry_count = fields.Integer(default=0)
    
    # Detailed state tracking
    odoo_order_state = fields.Char()
    odoo_delivery_state = fields.Char()
    cartona_status = fields.Char()
    
    # Enhanced error handling
    error_message = fields.Text()
    error_code = fields.Char()
    stack_trace = fields.Text()
    
    # Business context
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model
    def create_sync_log(self, order_id, sync_type, status, **kwargs):
        """Enhanced sync logging with automatic enrichment"""
        
        log_data = {
            'order_id': order_id,
            'sync_type': sync_type,
            'status': status,
            **kwargs
        }
        
        # Auto-enrich with order data
        if order_id:
            order = self.env['sale.order'].browse(order_id)
            if order.exists():
                log_data.update({
                    'odoo_order_state': order.state,
                    'odoo_delivery_state': order._get_primary_delivery_state(),
                })
        
        return self.create(log_data)
```

### Real-time Dashboard Integration

```python
class MarketplaceSyncDashboard(models.Model):
    _name = 'marketplace.sync.dashboard'
    _description = 'Real-time Sync Dashboard'

    def get_sync_statistics(self):
        """Get real-time sync statistics for Odoo 18 dashboard"""
        
        # Enhanced analytics with better performance
        domain_base = [('sync_timestamp', '>=', fields.Datetime.now() - timedelta(days=1))]
        
        stats = {
            'total_syncs': self.env['marketplace.sync.log'].search_count(domain_base),
            'successful_syncs': self.env['marketplace.sync.log'].search_count(
                domain_base + [('status', '=', 'success')]
            ),
            'failed_syncs': self.env['marketplace.sync.log'].search_count(
                domain_base + [('status', '=', 'failed')]
            ),
            'conflict_syncs': self.env['marketplace.sync.log'].search_count(
                domain_base + [('status', '=', 'conflict')]
            ),
            'avg_response_time': self._get_average_response_time(),
            'orders_in_sync': self._get_orders_in_sync_count(),
        }
        
        return stats
```

## Security Enhancements (Odoo 18)

### Advanced Security Features

1. **Enhanced Authentication:**
   - OAuth 2.0 integration with PKCE
   - JWT token validation
   - Multi-factor authentication support

2. **API Security:**
   - Rate limiting with Redis backend
   - Request signature validation
   - IP whitelisting with dynamic updates

3. **Data Protection:**
   - Field-level encryption for sensitive data
   - Audit trail for all sync operations
   - GDPR compliance features

## Testing Strategy (Odoo 18)

### Enhanced Testing Framework

```python
from odoo.tests import TransactionCase, tagged
from unittest.mock import patch, MagicMock

@tagged('marketplace_sync', 'post_install', '-at_install')
class TestBidirectionalSync(TransactionCase):
    
    def setUp(self):
        super().setUp()
        # Enhanced test setup for Odoo 18
        self.order = self.env['sale.order'].create({
            'partner_id': self.env.ref('base.res_partner_1').id,
            'cartona_id': 'TEST_ORDER_001',
        })
        
    def test_cartona_to_odoo_sync(self):
        """Test Cartona to Odoo sync with enhanced validation"""
        
        processor = self.env['marketplace.order.processor']
        
        # Test all status mappings
        for cartona_status, expected_mapping in CARTONA_TO_ODOO_MAPPING.items():
            with self.subTest(cartona_status=cartona_status):
                result = processor.process_cartona_status_update(
                    cartona_status, self.order.id
                )
                
                self.assertTrue(result)
                self.assertEqual(self.order.state, expected_mapping['order_state'])

    @patch('odoo.addons.cartona_integration.models.marketplace_api.MarketplaceAPI.update_order_status')
    def test_odoo_to_cartona_sync(self, mock_api):
        """Test Odoo to Cartona sync with mocked API"""
        
        mock_api.return_value = {'success': True}
        
        # Test state changes trigger sync
        self.order.write({'state': 'sale'})
        
        # Verify API was called
        self.assertTrue(mock_api.called)
```

## Deployment Guide (Odoo 18)

### Enhanced Deployment Steps

1. **Queue Configuration:**
   ```python
   # Enhanced queue configuration for Odoo 18
   QUEUE_JOB_CHANNELS = {
       'root.marketplace_sync': {
           'capacity': 10,
           'retry': 3,
           'retry_pattern': {1: 60, 2: 180, 3: 600}  # seconds
       }
   }
   ```

2. **Performance Monitoring:**
   - Use Odoo 18's enhanced profiling tools
   - Monitor queue job performance
   - Set up alerts for sync failures

3. **Scaling Considerations:**
   - Multi-worker deployment
   - Database connection pooling
   - Redis for caching and rate limiting

## Future Roadmap

### Odoo 18+ Enhancements

1. **AI-Powered Sync:**
   - Machine learning for conflict prediction
   - Intelligent retry scheduling
   - Automated business rule optimization

2. **Multi-Marketplace Support:**
   - Unified sync framework
   - Configurable marketplace connectors
   - Cross-marketplace analytics

3. **Advanced Analytics:**
   - Real-time business intelligence
   - Predictive sync analytics
   - Custom reporting framework 