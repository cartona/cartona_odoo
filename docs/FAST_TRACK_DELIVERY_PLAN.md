# 🚀 CARTONA MARKETPLACE INTEGRATION: 1-2 WEEK FAST TRACK DELIVERY PLAN

**Project:** Cartona Marketplace Integration Module for Suppliers  
**Timeline:** June 24 - July 8, 2025 (14 days maximum)  
**Current Date:** June 24, 2025 - DAY 1 ACTIVE  
**Status:** 🟢 ACTIVE DEVELOPMENT - Foundation Phase  
**Target:** Direct supplier-to-Cartona marketplace integration  
**Scope:** Complete integration module for individual supplier installation

**Integration Model:**
- **One Odoo Instance = One Supplier**
- **Each Supplier** installs this module in their own Odoo system
- **Each Supplier** receives unique auth token from Cartona
- **Direct Connection:** Supplier's Odoo ↔ Cartona Marketplace Platform

**Development Progress:**
- ✅ **Architecture Finalized** - Design principles and module structure confirmed
- 🟡 **Foundation Setup** - Currently in progress (Day 1)
- ⏳ **Core Logic** - Scheduled for completion by June 30
- ⏳ **Advanced Features** - Week 2 development
- ⏳ **Testing & Deployment** - Final week

---

## 📋 COMPLETE BUSINESS REQUIREMENTS

### **Cartona Marketplace Integration Module**
- **Supplier-Side Installation:** Each supplier installs module in their own Odoo
- **Direct Integration:** Supplier's Odoo connects directly to Cartona marketplace
- **Unique Authentication:** Each supplier receives unique auth token from Cartona
- **Minimal View Architecture:** Extend existing Odoo views, don't duplicate
- **Version Compatibility:** Odoo 15.0+, 16.0+, 17.0+

### **Key Design Principles:**
✅ **Extend, Don't Duplicate** - Enhance existing product/order views  
✅ **Supplier-Side Integration** - Each supplier has their own module instance  
✅ **Direct API Connection** - Connect directly to Cartona marketplace API  
✅ **Unique Authentication** - Each supplier uses their own Cartona auth token  
❌ **No Multi-Supplier Management** - One supplier per Odoo instance  
❌ **No Separate Product Views** - Use existing product management  
❌ **No Separate Order Views** - Use existing sales order management  

### **Module Architecture:**
- **Extended Views:** Product forms, Sales order forms, Stock views (with sync fields)
- **New Views:** Only 3-4 views (Supplier config, Sync dashboard, Connection test)
- **API Framework:** Generic REST API client with configurable endpoints
- **Multi-Supplier:** Each supplier has independent configuration and sync settings

---

## 📅 DEVELOPMENT TIMELINE - ACTIVE TRACKING

### **CURRENT WEEK: WEEK 1 SPRINT (June 24-30, 2025) - Foundation + Core Logic**
**Status:** 🟢 IN PROGRESS  
**Focus:** Module structure, API framework, basic synchronization

### **TODAY: DAY 1 (June 24, 2025) - Architecture & Foundation** 
**Total: 8 hours - IN PROGRESS**
**Status:** 🟡 ACTIVE DEVELOPMENT

#### **FAST-001: Cartona Integration Configuration** ⏱️ 3 hours
**Priority:** CRITICAL

**Implementation:**
```python
# Single supplier configuration per Odoo instance
class CartonaIntegrationConfig(models.Model):
    _name = 'cartona.integration.config'
    _description = 'Cartona Integration Configuration'
    
    supplier_name = fields.Char(string="Supplier Name", required=True)
    auth_token = fields.Char(string="Cartona Auth Token", required=True)
    active = fields.Boolean(string="Active", default=True)
    auto_sync_products = fields.Boolean(string="Auto Sync Products", default=True)
    auto_sync_orders = fields.Boolean(string="Auto Sync Orders", default=True)
    
    # Fixed API configuration for Cartona platform
    BASE_URL = 'https://supplier-integrations.cartona.com/api/v1/'
    AUTH_HEADER = 'AuthorizationToken'
    AUTH_METHOD = 'bearer_token'
    
    def test_connection(self):
        """Test API connection with Cartona"""
        try:
            headers = {self.AUTH_HEADER: self.auth_token}
            response = requests.get(f"{self.get_api_url()}test", headers=headers)
            return {'success': response.status_code == 200}
        except Exception as e:
            return {'success': False, 'error': str(e)}
```

**Acceptance Criteria:**
- [ ] Multi-supplier configuration model created
- [ ] Bearer token authentication implemented
- [ ] Connection testing functional
- [ ] Configuration UI accessible to admin users

#### **FAST-002: Module Structure Setup** ⏱️ 3 hours
**Priority:** CRITICAL

**Complete module structure with minimal views:**
```
marketplace_integration/
├── __manifest__.py              # Dependencies: queue_job, sale, stock, base
├── models/
│   ├── __init__.py
│   ├── marketplace_supplier_config.py  # Multi-supplier configuration
│   ├── product_template.py             # Product extensions (cartona_id)
│   ├── product_product.py              # Product variant extensions  
│   ├── res_partner.py                  # Partner extensions (cartona_id)
│   ├── sale_order.py                   # Order management extensions
│   ├── stock_move.py                   # Stock monitoring extensions
│   └── marketplace_api.py              # Generic API client
├── controllers/
│   ├── __init__.py
│   └── marketplace_webhook.py          # Generic webhook endpoints
├── views/
│   ├── product_views.xml               # Extend existing product forms
│   ├── sale_order_views.xml            # Extend existing order forms
│   ├── supplier_config_views.xml       # New: Supplier configuration
│   └── sync_dashboard_views.xml        # New: Sync monitoring
├── security/
│   └── ir.model.access.csv             # Complete access rights
└── data/
    └── queue_job_data.xml              # Queue configuration
```

**Key Points:**
- **Minimal New Views:** Only 2 new views (config + dashboard)
- **Extended Views:** Enhance existing product/order forms
- **Generic API:** Works with any marketplace platform
- **Multi-Supplier:** Support multiple marketplace connections

**Acceptance Criteria:**
- [ ] Module loads in Odoo without errors
- [ ] Dependencies configured (queue_job, sale, stock, base)
- [ ] Security permissions set for multi-supplier access
- [ ] Module installable and uninstallable

#### **FAST-003: cartona_id Field (Generic External Product ID)** ⏱️ 2 hours

**Purpose:** Add universal external product identifier field that works with ANY marketplace or supplier platform

**Description:** The `cartona_id` field serves as the generic external product identifier for ALL integrations - Cartona, Amazon, eBay, Shopify, or any custom API. This single field eliminates the need for multiple supplier-specific fields and provides maximum flexibility.
**Priority:** CRITICAL

**Implementation:**
```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    cartona_id = fields.Char(
        string="External Product ID",
        help="Generic external product ID for any marketplace/supplier integration"
    )
    marketplace_sync_status = fields.Selection([
        ('pending', 'Pending Sync'),
        ('synced', 'Synced'),
        ('error', 'Sync Error')
    ], string="Sync Status", default='pending')
    last_sync_date = fields.Datetime(string="Last Sync Date")
    
    def sync_to_marketplace(self):
        """Manual sync trigger - works with any configured supplier"""
        active_suppliers = self.env['marketplace.supplier.config'].search([('active', '=', True)])
        for supplier in active_suppliers:
            self.with_delay()._sync_to_supplier(supplier)
    
    def _sync_to_supplier(self, supplier):
        """Generic sync method for any supplier"""
        try:
            api_client = self.env['marketplace.api'].with_context(supplier_id=supplier.id)
            result = api_client.sync_product(self)
            if result.get('success'):
                self.marketplace_sync_status = 'synced'
                self.last_sync_date = fields.Datetime.now()
        except Exception as e:
            self.marketplace_sync_status = 'error'
            self._log_sync_error(str(e))
```

**Acceptance Criteria:**
- [ ] cartona_id field added to product.template and product.product
- [ ] Sync status tracking implemented
- [ ] Manual sync functionality works
- [ ] Generic sync method supports any supplier
- [ ] Fields visible in extended product forms

---

## **Key Field: cartona_id (Generic External Product ID)**

### **Important: Universal Field for All Suppliers**
The field `cartona_id` serves as the **generic external product identifier** for ALL marketplace and supplier integrations, not just Cartona-specific implementations. 

**Why "cartona_id"?**
- **Historical Context:** Named after the original Cartona integration use case
- **Generic Purpose:** Used for ANY external supplier/marketplace product ID
- **Universal Application:** Works with Amazon, eBay, Shopify, WooCommerce, or any API-enabled platform
- **Single Field Strategy:** One field handles all external product matching needs

**Field Usage Examples:**
```python
# For Cartona marketplace:
product.cartona_id = "12345"

# For Amazon marketplace:  
product.cartona_id = "B08XYZ123"

# For eBay marketplace:
product.cartona_id = "394857392"

# For custom supplier API:
product.cartona_id = "PROD_789"
```

**Key Benefits:**
- **Simplified Architecture:** One field handles all external integrations
- **Reduced Complexity:** No need for multiple supplier-specific fields
- **Easy Migration:** Existing integrations work without field changes
- **Flexible Matching:** Same field works with different external ID formats

**Configuration Per Supplier:**
Each supplier configuration specifies how to use the `cartona_id` field:
```python
supplier_config = {
    'name': 'Amazon Integration',
    'product_id_field': 'cartona_id',  # Maps to our universal field
    'api_product_id_key': 'asin',      # Amazon's API field name
}
```

This approach ensures maximum compatibility and simplicity while supporting unlimited marketplace integrations.

---

### **DAY 2 (June 25): Generic API Framework + View Extensions**
**Total: 8 hours**

#### **FAST-004: Generic API Client** ⏱️ 4 hours
**Priority:** CRITICAL

**Complete implementation:**
```python
class MarketplaceAPI(models.Model):
    _name = 'marketplace.api'
    _description = 'Generic Marketplace API Client'
    
    # Fixed API configuration - IDENTICAL for all suppliers
    # Only auth_token varies per supplier
    BASE_URL = 'https://supplier-integrations.cartona.com/api/v1/'  # Fixed domain
    AUTH_HEADER = 'AuthorizationToken'                              # Always AuthorizationToken
    
    def _get_supplier_config(self):
        """Get supplier config from context or default"""
        supplier_id = self.env.context.get('supplier_id')
        if supplier_id:
            return self.env['marketplace.supplier.config'].browse(supplier_id)
        return self.env['marketplace.supplier.config'].search([('active', '=', True)], limit=1)
    
    def _make_api_call(self, endpoint, method='GET', data=None):
        """Generic API call with bearer token authentication"""
        supplier = self._get_supplier_config()
        if not supplier:
            raise ValueError("No active supplier configuration found")
        
        headers = {
            self.AUTH_HEADER: supplier.auth_token,
            'Content-Type': 'application/json'
        }
        
        # Build URL using fixed base URL (same for all suppliers)
        url = f"{self.BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            
            response.raise_for_status()
            return {'success': True, 'data': response.json()}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def sync_product(self, product):
        """Generic product sync"""
        product_data = {
            'internal_product_id': product.cartona_id or product.default_code,
            'name': product.name,
            'price': product.list_price,
            'available_stock_quantity': product.qty_available,
            'in_stock': product.qty_available > 0,
            'is_published': True
        }
        return self._make_api_call('supplier-product/bulk-update', 'POST', [product_data])
```

**Acceptance Criteria:**
- [ ] Generic API client supports any marketplace
- [ ] Bearer token authentication implemented
- [ ] Error handling and retry logic
- [ ] Product sync API calls functional
- [ ] Multi-supplier support working

#### **FAST-005: View Extensions (Minimal Architecture)** ⏱️ 4 hours
**Priority:** CRITICAL

**Key Implementation - Extend Existing Views Only:**
```xml
<!-- Extend Product Form - NO separate product views -->
<record id="view_product_template_form_marketplace" model="ir.ui.view">
    <field name="name">product.template.form.marketplace</field>
    <field name="model">product.template</field>
    <field name="inherit_id" ref="product.product_template_form_view"/>
    <field name="arch" type="xml">
        <group name="group_general" position="after">
            <group name="marketplace_sync" string="Marketplace Integration">
                <field name="cartona_id"/>
                <field name="marketplace_sync_status"/>
                <field name="last_sync_date"/>
                <button name="sync_to_marketplace" string="Sync Now" type="object" 
                        class="btn-primary"/>
            </group>
        </group>
    </field>
</record>

<!-- Extend Sales Order Form - NO separate order views -->
<record id="view_order_form_marketplace" model="ir.ui.view">
    <field name="name">sale.order.form.marketplace</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <group name="sale_header" position="after">
            <group name="marketplace_info" string="Marketplace Integration" 
                   attrs="{'invisible': [('marketplace_order_id', '=', False)]}">
                <field name="marketplace_order_id"/>
                <field name="marketplace_status"/>
                <button name="update_marketplace_status" string="Update Status" 
                        type="object" class="btn-primary"/>
            </group>
        </group>
    </field>
</record>
```

**Benefits of This Approach:**
✅ **Familiar Interface** - Users work in existing views  
✅ **No Training Required** - Same product/order management screens  
✅ **Reduced Development** - Only 2 new views needed  
✅ **Seamless Integration** - Marketplace features blend naturally  

**Acceptance Criteria:**
- [ ] Product forms enhanced with marketplace sync fields
- [ ] Sales order forms enhanced with marketplace status
- [ ] NO separate product management views created
- [ ] NO separate order management views created
- [ ] Only supplier config and dashboard views are new

---

### **DAY 3 (June 26): Real-time Price & Stock Sync**
**Total: 8 hours**

#### **FAST-006: Real-time Price Sync** ⏱️ 4 hours
**Priority:** CRITICAL

**Implementation:**
```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    def write(self, vals):
        old_prices = {rec.id: rec.list_price for rec in self}
        result = super().write(vals)
        
        if 'list_price' in vals:
            for record in self:
                # Generic sync - works with any configured supplier
                if record.cartona_id and old_prices[record.id] != record.list_price:
                    # Queue async sync to prevent UI blocking
                    active_suppliers = self.env['marketplace.supplier.config'].search([('active', '=', True)])
                    for supplier in active_suppliers:
                        record.with_delay(priority=1)._sync_price_to_supplier(supplier)
        return result
    
    def _sync_price_to_supplier(self, supplier):
        """Generic price sync to any marketplace"""
        try:
            api_client = self.env['marketplace.api'].with_context(supplier_id=supplier.id)
            product_data = {
                'internal_product_id': self.cartona_id,
                'price': self.list_price
            }
            response = api_client._make_api_call('supplier-product/bulk-update', 'POST', [product_data])
            
            if response.get('success'):
                self.marketplace_sync_status = 'synced'
                self.last_sync_date = fields.Datetime.now()
            else:
                raise Exception(f"API Error: {response.get('error')}")
        except Exception as e:
            self.marketplace_sync_status = 'error'
            self._log_sync_error(f"Price sync failed for {supplier.name}: {str(e)}")
```

**Acceptance Criteria:**
- [ ] Price changes trigger sync to all active suppliers
- [ ] Queue system prevents UI blocking
- [ ] Performance: <5 second sync time
- [ ] Generic API works with any marketplace
- [ ] Error handling and retry logic functional

#### **FAST-007: Real-time Stock Sync** ⏱️ 4 hours
**Priority:** CRITICAL

**Implementation:**
```python
class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def _action_done(self):
        result = super()._action_done()
        
        # Trigger stock sync for affected products with cartona_id
        for move in self:
            if move.product_id.cartona_id:
                move.product_id.with_delay()._sync_stock_to_suppliers()
        
        return result

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    def _sync_stock_to_suppliers(self):
        """Generic stock sync to all active suppliers"""
        active_suppliers = self.env['marketplace.supplier.config'].search([('active', '=', True)])
        for supplier in active_suppliers:
            self.with_delay()._sync_stock_to_supplier(supplier)
    
    def _sync_stock_to_supplier(self, supplier):
        """Sync stock to specific supplier"""
        try:
            api_client = self.env['marketplace.api'].with_context(supplier_id=supplier.id)
            
            # Aggregate stock across all warehouses
            total_stock = sum(self.mapped('qty_available'))
            
            stock_data = {
                'internal_product_id': self.cartona_id,
                'available_stock_quantity': total_stock,
                'in_stock': total_stock > 0
            }
            
            response = api_client._make_api_call('supplier-product/bulk-update', 'POST', [stock_data])
            
            if response.get('success'):
                self.marketplace_sync_status = 'synced'
                self.last_sync_date = fields.Datetime.now()
            else:
                raise Exception(f"API Error: {response.get('error')}")
        except Exception as e:
            self.marketplace_sync_status = 'error'
            self._log_sync_error(f"Stock sync failed for {supplier.name}: {str(e)}")
```

**Acceptance Criteria:**
- [ ] Stock changes trigger immediate sync to all suppliers
- [ ] Multi-warehouse stock aggregation works
- [ ] Queue-based processing prevents UI blocking
- [ ] Error handling and retry logic
- [ ] Support for all stock operations (adjustments, transfers, receipts)

---

### **DAY 4-5 (June 27-28): Order Management & Status Sync**
**Total: 16 hours**

#### **FAST-008: Generic Order Pull System** ⏱️ 10 hours
**Priority:** CRITICAL

**Complete order pull features:**
- Generic webhook endpoint for any marketplace (`/marketplace_integration/webhook/orders`)
- Multi-supplier order processing with supplier identification
- Customer auto-creation and updates with validation
- Product matching using cartona_id
- Order validation and error handling
- Support for various payment methods
- Multi-currency support

**Key implementation:**
```python
class MarketplaceWebhook(http.Controller):
    
    @http.route('/marketplace_integration/webhook/orders', 
                type='json', auth='public', methods=['POST'])
    def receive_order(self, **kwargs):
        try:
            order_data = request.jsonrequest
            
            # Identify supplier from webhook data or headers
            supplier_id = self._identify_supplier(request)
            if not supplier_id:
                return {'success': False, 'error': 'Supplier not identified'}
            
            order_processor = request.env['marketplace.order.processor']
            sale_order = order_processor.create_order_from_marketplace(order_data, supplier_id)
            
            return {'success': True, 'order_id': sale_order.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _identify_supplier(self, request):
        """Identify supplier from webhook data or headers"""
        # Method 1: From Authorization header
        auth_token = request.httprequest.headers.get('Authorization', '')
        supplier = self.env['marketplace.supplier.config'].search([('auth_token', '=', auth_token)], limit=1)
        
        if supplier:
            return supplier.id
        
        # Method 2: From request data
        supplier_name = request.jsonrequest.get('supplier_name')
        if supplier_name:
            supplier = self.env['marketplace.supplier.config'].search([('name', '=', supplier_name)], limit=1)
            return supplier.id if supplier else False
        
        return False

class MarketplaceOrderProcessor(models.Model):
    _name = 'marketplace.order.processor'
    
    def create_order_from_marketplace(self, order_data, supplier_id):
        """Generic order creation from any marketplace"""
        supplier = self.env['marketplace.supplier.config'].browse(supplier_id)
        
        # Create/update customer
        partner = self._create_or_update_customer(order_data.get('customer'))
        
        # Create sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'marketplace_order_id': order_data.get('order_id'),
            'marketplace_supplier_id': supplier_id,
            'marketplace_status': order_data.get('status', 'pending'),
            'origin': f"Marketplace: {supplier.name}",
        })
        
        # Create order lines
        for line_data in order_data.get('order_lines', []):
            self._create_order_line(sale_order, line_data)
        
        return sale_order
    
    def _create_order_line(self, order, line_data):
        """Create order line with product matching"""
        # Find product by cartona_id
        product = self.env['product.product'].search([
            ('cartona_id', '=', line_data.get('product_id'))
        ], limit=1)
        
        if product:
            # Create order line
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': line_data.get('quantity', 1),
                'price_unit': line_data.get('price', product.list_price)
            })
        
        if not product:
            # Create product if not found
            product = self._create_product_from_marketplace(line_data)
        
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': line_data.get('quantity', 1),
            'price_unit': line_data.get('price', 0),
        })
```

**Acceptance Criteria:**
- [ ] Generic webhook endpoint receives orders from any marketplace
- [ ] Supplier identification from webhook data works
- [ ] Customer creation and updates functional
- [ ] Product matching using cartona_id
- [ ] Customer matching using cartona_id
- [ ] Automatic customer creation from marketplace orders
- [ ] Order line creation with proper product/customer links
- [ ] Order validation prevents data corruption
- [ ] Error handling with proper logging
- [ ] Multi-supplier order processing
- [ ] Order pull system processing test orders
- [ ] **Order Pull:** < 30 seconds for order processing

#### **FAST-009: Bidirectional Status Sync** ⏱️ 6 hours
**Priority:** CRITICAL

**Bidirectional status synchronization:**
- Odoo → Marketplace status updates with generic API calls
- Marketplace → Odoo status webhooks with supplier identification
- Generic status mapping (configurable per supplier)
- Special delivery confirmation handling
- Cancellation and refund support
- Status consistency validation

**Implementation:**
```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    marketplace_order_id = fields.Char(string="Marketplace Order ID")
    marketplace_supplier_id = fields.Many2one('marketplace.supplier.config', string="Marketplace Supplier")
    marketplace_status = fields.Char(string="Marketplace Status")
    marketplace_sync_date = fields.Datetime(string="Last Status Sync")
    
    def write(self, vals):
        old_states = {rec.id: rec.state for rec in self}
        result = super().write(vals)
        
        if 'state' in vals:
            for record in self:
                if record.marketplace_order_id and old_states[record.id] != record.state:
                    # Sync status to marketplace
                    record.with_delay()._sync_status_to_marketplace()
        
        return result
    
    def _sync_status_to_marketplace(self):
        """Generic status sync to marketplace"""
        if not self.marketplace_supplier_id:
            return
        
        try:
            api_client = self.env['marketplace.api'].with_context(supplier_id=self.marketplace_supplier_id.id)
            
            # Map Odoo states to marketplace states
            status_mapping = {
                'draft': 'pending',
                'sent': 'confirmed', 
                'sale': 'approved',
                'done': 'delivered',
                'cancel': 'cancelled'
            }
            
            marketplace_status = status_mapping.get(self.state, self.state)
            
            status_data = [{
                'hashed_id': self.marketplace_order_id,
                'status': marketplace_status
            }]
            
            response = api_client._make_api_call('order/update-order-status', 'POST', status_data)
            
            if response.get('success'):
                self.marketplace_status = marketplace_status
                self.marketplace_sync_date = fields.Datetime.now()
        except Exception as e:
            self._log_sync_error(f"Status sync failed: {str(e)}")
    
    def update_marketplace_status(self):
        """Manual status update button"""
        self._sync_status_to_marketplace()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Status Sync',
                'message': 'Order status synchronized with marketplace',
                'type': 'success'
            }
        }
```

**Acceptance Criteria:**
- [ ] Odoo order status changes sync to marketplace
- [ ] Marketplace status updates received via webhook
- [ ] Generic status mapping works for any supplier
- [ ] Special cases handled (delivery, cancellations)
- [ ] No status sync conflicts
- [ ] Manual status sync button functional

---

## 📅 WEEK 2 SPRINT (July 1 - July 8): Advanced Features + Production

### **DAY 6-7 (July 1-2): Configuration Views & Monitoring**
**Total: 16 hours**

#### **FAST-010: Supplier Configuration Views** ⏱️ 8 hours
**Priority:** HIGH

**Only 2 New Views Needed:**
```xml
<!-- Supplier Configuration Form -->
<record id="view_marketplace_supplier_config_form" model="ir.ui.view">
    <field name="name">marketplace.supplier.config.form</field>
    <field name="model">marketplace.supplier.config</field>
    <field name="arch" type="xml">
        <form>
            <header>
                <button name="test_connection" string="Test Connection" type="object" class="btn-primary"/>
                <field name="connection_status" widget="statusbar"/>
            </header>
            <sheet>
                <group>
                    <group>
                        <field name="name"/>
                        <field name="api_endpoint"/>
                        <field name="auth_token" password="True"/>
                        <field name="auth_header"/>
                    </group>
                    <group>
                        <field name="active"/>
                        <field name="auto_sync_products"/>
                        <field name="auto_sync_orders"/>
                    </group>
                </group>
            </sheet>
        </form>
    </field>
</record>

<!-- Supplier Configuration Tree -->
<record id="view_marketplace_supplier_config_tree" model="ir.ui.view">
    <field name="name">marketplace.supplier.config.tree</field>
    <field name="model">marketplace.supplier.config</field>
    <field name="arch" type="xml">
        <tree>
            <field name="name"/>
            <field name="api_endpoint"/>
            <field name="active"/>
            <field name="connection_status"/>
            <button name="test_connection" string="Test" type="object" icon="fa-plug"/>
        </tree>
    </field>
</record>
```

**Menu Structure (Minimal):**
```xml
<menuitem id="menu_marketplace_root" name="Marketplace Integration" sequence="100"/>
<menuitem id="menu_marketplace_config" name="Configuration" parent="menu_marketplace_root" sequence="10"/>
<menuitem id="menu_suppliers" name="Suppliers" parent="menu_marketplace_config" action="action_marketplace_supplier_config"/>
<menuitem id="menu_sync_dashboard" name="Sync Dashboard" parent="menu_marketplace_root" sequence="20"/>
```

**Acceptance Criteria:**
- [ ] Supplier configuration form functional
- [ ] Connection testing works
- [ ] Bearer token authentication setup
- [ ] Multi-supplier management
- [ ] Minimal menu structure (no product/order menus)

#### **FAST-011: Sync Monitoring Dashboard** ⏱️ 8 hours
**Priority:** HIGH

**Single Dashboard View:**
```xml
<!-- Sync Dashboard - Only New View #2 -->
<record id="view_sync_dashboard_kanban" model="ir.ui.view">
    <field name="name">marketplace.sync.dashboard</field>
    <field name="model">marketplace.sync.log</field>
    <field name="arch" type="xml">
        <kanban class="o_kanban_dashboard">
            <field name="supplier_id"/>
            <field name="operation_type"/>
            <field name="status"/>
            <field name="create_date"/>
            <templates>
                <t t-name="kanban-box">
                    <div class="oe_kanban_card">
                        <div class="o_kanban_card_header">
                            <div class="o_kanban_card_header_title">
                                <field name="supplier_id"/>
                            </div>
                        </div>
                        <div class="o_kanban_card_content">
                            <div class="row">
                                <div class="col-6">
                                    <button type="object" name="sync_all_products" class="btn btn-primary">
                                        Sync All Products
                                    </button>
                                </div>
                                <div class="col-6">
                                    <field name="status" widget="badge"/>
                                </div>
                            </div>
                        </div>
                    </div>
                </t>
            </templates>
        </kanban>
    </field>
</record>
```

**Dashboard Features:**
- Real-time sync status for all suppliers
- Manual sync controls (products, stock, orders)
- Error monitoring and alerts
- Performance metrics (success rates, timing)
- Health check indicators

**Acceptance Criteria:**
- [ ] Dashboard shows real-time status for all suppliers
- [ ] Manual sync controls functional
- [ ] Error monitoring works
- [ ] Performance metrics displayed
- [ ] Health checks available

---

### **DAY 8-9 (July 3-4): Error Handling & Bulk Operations**
**Total: 16 hours**

#### **FAST-012: Comprehensive Error Handling** ⏱️ 8 hours
**Priority:** CRITICAL

**Features:**
- Automatic retry with exponential backoff algorithm
- Dead letter queue for permanently failed operations
- Error classification and intelligent routing
- Manual intervention tools for administrators
- Alerting and notification system (email/webhook)

**Implementation:**
```python
class MarketplaceErrorHandler(models.Model):
    _name = 'marketplace.error.handler'
    
    def handle_sync_error(self, operation, error, record_id, supplier_id):
        # Classify error type
        error_type = self._classify_error(error)
        
        # Apply retry logic based on error type
        if error_type in ['network', 'temporary']:
            self._schedule_retry(operation, record_id, supplier_id)
        elif error_type == 'data':
            self._send_to_manual_queue(operation, error, record_id, supplier_id)
        else:
            self._send_alert(operation, error, record_id, supplier_id)
    
    def _classify_error(self, error):
        """Classify error for appropriate handling"""
        error_str = str(error).lower()
        
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'network']):
            return 'network'
        elif any(keyword in error_str for keyword in ['rate limit', '429', 'quota']):
            return 'temporary'  
        elif any(keyword in error_str for keyword in ['validation', 'invalid', 'missing']):
            return 'data'
        else:
            return 'unknown'
```

**Acceptance Criteria:**
- [ ] Automatic retry with exponential backoff
- [ ] Dead letter queue implemented
- [ ] Error classification working
- [ ] Manual intervention tools available
- [ ] Alerting system functional

#### **FAST-013: Bulk Operations & Performance** ⏱️ 8 hours
**Priority:** HIGH

**Features:**
- Bulk price updates with batch processing
- Bulk stock synchronization for large inventories  
- Bulk product setup tools with CSV import/export
- Performance optimization for large datasets
- Progress tracking and cancellation support

**Implementation:**
```python
class MarketplaceBulkOperations(models.Model):
    _name = 'marketplace.bulk.operations'
    
    def bulk_sync_products(self, supplier_id, product_ids):
        """Bulk sync products to specific supplier"""
        supplier = self.env['marketplace.supplier.config'].browse(supplier_id)
        products = self.env['product.template'].browse(product_ids)
        
        # Process in batches of 100
        batch_size = 100
        total_batches = len(products) // batch_size + (1 if len(products) % batch_size else 0)
        
        for i, batch_start in enumerate(range(0, len(products), batch_size)):
            batch_products = products[batch_start:batch_start + batch_size]
            
            # Prepare batch data
            product_data = []
            for product in batch_products:
                if product.cartona_id:
                    product_data.append({
                        'internal_product_id': product.cartona_id,
                        'name': product.name,
                        'price': product.list_price,
                        'available_stock_quantity': product.qty_available,
                        'in_stock': product.qty_available > 0,
                        'is_published': True
                    })
            
            # Make bulk API call
            if product_data:
                api_client = self.env['marketplace.api'].with_context(supplier_id=supplier_id)
                response = api_client._make_api_call('supplier-product/bulk-update', 'POST', product_data)
                
                # Update progress
                progress = ((i + 1) / total_batches) * 100
                self._update_progress(f"Batch {i+1}/{total_batches} completed", progress)
        
        return {'success': True, 'processed': len(products)}
```

**Acceptance Criteria:**
- [ ] Bulk operations don't block UI
- [ ] Progress tracking visible to users
- [ ] Batch processing for large datasets
- [ ] Performance optimized for 1000+ products
- [ ] Error handling for partial failures

---

### **DAY 10-11 (July 4-5): Version Compatibility & Testing**
**Total: 16 hours**

#### **FAST-012: Multi-Version Support** ⏱️ 8 hours
**Priority:** HIGH

**Features:**
- Odoo 15.0+ compatibility testing and adjustments
- Odoo 16.0+ compatibility testing and adjustments
- Odoo 17.0+ compatibility testing and adjustments
- Version-specific feature handling and graceful degradation
- Backward compatibility maintenance with feature flags

**Acceptance Criteria:**
- [ ] Tested and working on Odoo 15.0+
- [ ] Tested and working on Odoo 16.0+
- [ ] Tested and working on Odoo 17.0+
- [ ] Version-specific features handled
- [ ] Backward compatibility maintained

#### **FAST-013: Comprehensive Testing** ⏱️ 8 hours
**Priority:** CRITICAL

**Testing scenarios:**
- End-to-end integration testing (full order lifecycle)
- Environment switching testing (internal ↔ external)
- Performance and load testing (1000+ products, 100+ orders)
- Error scenario testing (network failures, API errors)
- Security and authentication testing

**Acceptance Criteria:**
- [ ] End-to-end tests passing
- [ ] Environment switching works
- [ ] Performance meets requirements
- [ ] Error scenarios handled
- [ ] Security tests passing

---

### **DAY 12-14 (July 6): Production Deployment**
**Total: 16 hours**

#### **FAST-014: Documentation & Training** ⏱️ 8 hours
**Priority:** HIGH

**Documentation deliverables:**
- Complete installation guide with step-by-step instructions
- User documentation for both environments (internal vs external)
- Admin configuration guide with screenshots
- Troubleshooting documentation with common issues
- API reference documentation for developers

**Acceptance Criteria:**
- [ ] Installation guide complete
- [ ] User documentation available
- [ ] Admin guide finished
- [ ] Troubleshooting guide ready
- [ ] API documentation complete

#### **FAST-015: Production Deployment** ⏱️ 8 hours
**Priority:** CRITICAL

**Deployment activities:**
- Staging environment deployment and validation
- Production deployment procedures and checklists
- Data migration scripts for existing systems
- Rollback procedures and emergency protocols
- Post-deployment validation and smoke tests

**Acceptance Criteria:**
- [ ] Staging deployment successful
- [ ] Production procedures documented
- [ ] Data migration scripts ready
- [ ] Rollback procedures tested
- [ ] Post-deployment validation complete

---

## 🎯 COMPREHENSIVE SUCCESS CRITERIA

### **Technical Requirements (100% Coverage):**
- [ ] **Multi-Supplier Support:** Configure and manage multiple marketplace suppliers
- [ ] **Generic API Framework:** Works with any REST API using bearer token authentication
- [ ] **Minimal View Architecture:** Only 2 new views (config + dashboard), extend existing views
- [ ] **Real-time Sync:** Price and stock updates <5 seconds with queue system
- [ ] **Order Import:** Generic webhook endpoint processes orders from any marketplace
- [ ] **Status Sync:** Bidirectional status updates with configurable mapping
- [ ] **Error Handling:** <1% failure rate with automatic recovery
- [ ] **Performance:** Handles bulk operations without UI blocking
- [ ] **Version Support:** Works on Odoo 15.0+, 16.0+, 17.0+
- [ ] **Security:** Secure bearer token authentication and data handling

### **Business Requirements (100% Coverage):**
- [ ] **Universal Design:** Works with any marketplace or supplier platform
- [ ] **Seamless Integration:** Marketplace features integrated into existing Odoo workflows
- [ ] **No Duplicate Views:** Product and order management through existing Odoo views
- [ ] **Real-time Updates:** Price, stock, and order changes sync instantly to all suppliers
- [ ] **Order Processing:** Complete order lifecycle automation with supplier identification
- [ ] **Multi-currency:** Support for different currencies and pricing across suppliers
- [ ] **Bulk Operations:** Efficient processing of large product datasets
- [ ] **Monitoring:** Real-time dashboard for operations teams

### **User Experience Requirements (100% Coverage):**
- [ ] **Familiar Interface:** Users work in existing product and sales order views
- [ ] **No Training Required:** No new interfaces to learn
- [ ] **Simple Configuration:** Easy supplier setup through admin interface
- [ ] **Clear Status Indicators:** Sync status visible in product and order forms
- [ ] **Manual Controls:** Manual sync buttons when needed
- [ ] **Error Visibility:** Clear error messages and resolution paths

### **Deployment Requirements (100% Coverage):**
- [ ] **Universal Module:** Same module works with any marketplace platform
- [ ] **Easy Installation:** One-click module installation
- [ ] **Simple Configuration:** Intuitive supplier setup interface
- [ ] **Monitoring:** Built-in health checks and status monitoring
- [ ] **Maintenance:** Self-healing with manual intervention capabilities
- [ ] **Documentation:** Complete setup and user guides

---

## 📊 PROJECT METRICS

### **Timeline Summary:**
- **Total Duration:** 14 days maximum (June 24 - July 8, 2025)
- **Week 1 Focus:** Foundation + Core Sync Logic (40 hours)
- **Week 2 Focus:** Configuration + Monitoring + Production (88 hours)
- **Total Effort:** 128 hours (manageable with 2-3 developers)

### **View Architecture Summary:**
- **Total New Views:** Only 2 (Supplier Config + Sync Dashboard)
- **Extended Views:** 4 (Product Form, Product Variant, Sales Order, Stock Quant)
- **No Duplicate Views:** No separate product/order management interfaces
- **Minimal Menu:** Simple marketplace configuration menu only

### **Key Success Factors:**
1. **Minimal View Approach** - Extend existing views, don't duplicate
2. **Generic API Design** - Works with any marketplace platform
3. **Multi-Supplier Architecture** - Support multiple marketplaces simultaneously
4. **Bearer Token Standard** - Standardized authentication across platforms
5. **Real-time Sync** - Immediate updates with queue-based processing

---

## 🚀 READY TO START

This updated plan reflects the **minimal view architecture** and **generic marketplace integration** approach from the Implementation Guide.

**Key Changes from Original Plan:**
✅ **Generic Design** - Works with any marketplace, not just Cartona  
✅ **Minimal Views** - Only 2 new views instead of 10+  
✅ **Multi-Supplier** - Support multiple marketplace connections  
✅ **Bearer Token Auth** - Standardized authentication method  
✅ **Extended Views** - Enhance existing product/order forms  
❌ **No Environment Detection** - Replaced with multi-supplier config  
❌ **No Separate Views** - Use existing Odoo product/order management  

**Immediate Next Steps:**
1. ✅ Confirm team availability and roles
2. ✅ Set up development environment  
3. ✅ Begin FAST-001: Multi-Supplier Configuration System
4. ✅ Start Daily Stand-ups for progress tracking

The plan ensures **complete marketplace integration** with **minimal view overhead** and **maximum compatibility** across different marketplace platforms.

---

### **Partner Integration (Customers/Suppliers)**
The `cartona_id` field is also added to partners (customers and suppliers) to enable proper order synchronization and customer matching between Odoo and external marketplaces.

**Partner Field Usage Examples:**
```python
# For Cartona marketplace customer:
partner.cartona_id = "retailer_67890"

# For Amazon marketplace customer:  
partner.cartona_id = "retailer_12345"

# For eBay marketplace customer:
partner.cartona_id = "retailer_98765"

# For B2B supplier platform:
partner.cartona_id = "retailer_456789"
```

**Benefits for Order Processing:**
- **Customer Matching:** Link incoming orders to existing Odoo customers
- **Automatic Customer Creation:** Create new customers from marketplace orders
- **Order History:** Maintain complete customer order history across platforms
- **Supplier Management:** Track supplier relationships across multiple platforms

#### **FAST-010: cartona_id Field for Partners (Generic External Partner ID)** ⏱️ 1.5 hours

**Purpose:** Add universal external partner identifier field for customer/supplier matching

**Description:** Extend res.partner model with cartona_id field to enable matching customers and suppliers across different marketplace platforms.

**Code Implementation:**
```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    cartona_id = fields.Char(
        string="External Partner ID",
        help="Generic external partner ID for any marketplace/supplier integration"
    )
    marketplace_customer_type = fields.Selection([
        ('b2c', 'B2C Customer'),
        ('b2b', 'B2B Customer'), 
        ('supplier', 'Supplier')
    ], string="Marketplace Type")
    marketplace_sync_status = fields.Selection([
        ('pending', 'Pending Sync'),
        ('synced', 'Synced'),
        ('error', 'Sync Error')
    ], string="Sync Status", default='pending')
    last_customer_sync_date = fields.Datetime(string="Last Sync Date")
```

**Acceptance Criteria:**
- [ ] cartona_id field added to res.partner model
- [ ] Partner type classification implemented
- [ ] Sync status tracking implemented
- [ ] Fields visible in extended partner forms
- [ ] Generic sync method supports any supplier customer matching

---

**Partner Forms Extension:**
```xml
<!-- views/res_partner_view.xml -->
<record id="view_partner_form_marketplace" model="ir.ui.view">
    <field name="name">res.partner.form.marketplace</field>
    <field name="model">res.partner</field>
    <field name="inherit_id" ref="base.view_partner_form"/>
    <field name="arch" type="xml">
        <group name="contact_details" position="after">
            <group name="marketplace_integration" string="Marketplace Integration">
                <field name="cartona_id"/>
                <field name="marketplace_customer_type"/>
                <field name="marketplace_sync_status"/>
                <field name="last_customer_sync_date"/>
            </group>
        </group>
    </field>
</record>
```

---

### **cartona_id Naming Conventions**

**For Products (product.template / product.product):**
- **Format:** `XXXXXX` (no prefix)
- **Examples:** `12345`, `B08XYZ123`, `394857392`, `PROD_789`
- **Purpose:** Store the raw external product ID as provided by the marketplace/supplier API

**For Partners (res.partner):**
- **Format:** `retailer_XXXXX` (with retailer_ prefix)
- **Examples:** `retailer_67890`, `retailer_12345`, `retailer_98765`
- **Purpose:** Distinguish partner IDs from product IDs and ensure consistent partner identification

**Benefits of This Convention:**
- **Clear Separation:** Easy to distinguish between product and partner external IDs
- **API Compatibility:** Product IDs match exactly what external APIs expect
- **Partner Consistency:** All partner IDs follow the same retailer_ prefix pattern
- **Debugging Friendly:** Clear naming makes troubleshooting easier

---

def _create_or_update_customer(self, customer_data):
        """Create or update customer with cartona_id matching (retailer_ prefix)"""
        if not customer_data:
            return self.env.ref('base.public_partner')
            
        # Find existing customer by cartona_id (with retailer_ prefix)
        partner = self.env['res.partner'].search([
            ('cartona_id', '=', f"retailer_{customer_data.get('external_id')}")
        ], limit=1)
        
        customer_vals = {
            'name': customer_data.get('name', 'Marketplace Customer'),
            'email': customer_data.get('email'),
            'phone': customer_data.get('phone'),
            'street': customer_data.get('address', {}).get('street'),
            'city': customer_data.get('address', {}).get('city'),
            'zip': customer_data.get('address', {}).get('zip'),
            'cartona_id': f"retailer_{customer_data.get('external_id')}",  # Apply retailer_ prefix
            'marketplace_customer_type': customer_data.get('type', 'b2c'),
            'is_company': customer_data.get('type') == 'b2b'
        }
        
        if partner:
            # Update existing customer
            partner.write(customer_vals)
            return partner
        else:
            # Create new customer with retailer_ prefix
            return self.env['res.partner'].create(customer_vals)
````
---

## 📊 SUCCESS METRICS & FINAL VALIDATION

### **Week 1 Sprint Completion Criteria**
- [ ] All FAST-001 through FAST-010 tasks completed
- [ ] Module loads without errors in Odoo 17.0+
- [ ] Multi-supplier configuration working
- [ ] cartona_id fields functional for products and partners
- [ ] Real-time price and stock sync operational
- [ ] Order import system processing test orders
- [ ] API connections tested and stable
- [ ] Error handling and logging functional

### **Performance Benchmarks**
- **Price Sync:** < 5 seconds from Odoo change to marketplace update
- **Stock Sync:** < 10 seconds for inventory updates
- **Order Import:** < 30 seconds for order processing
- **API Reliability:** > 99% success rate for API calls
- **Error Recovery:** < 5 minutes for automatic retry completion

### **User Acceptance Testing**
- [ ] Products visible in existing Odoo product forms with cartona_id
- [ ] Partners visible in existing Odoo partner forms with cartona_id
- [ ] Orders pulled automatically from marketplace
- [ ] Price changes sync to marketplace automatically
- [ ] Stock changes sync to marketplace automatically
- [ ] Marketplace configuration accessible to admin users
- [ ] No duplicate views created - all extensions to existing views

### **Production Readiness Checklist**
- [ ] Security review completed
- [ ] Performance testing passed
- [ ] Error handling tested
- [ ] Documentation reviewed
- [ ] User training materials prepared
- [ ] Rollback plan documented
- [ ] Monitoring and alerting configured

### **Next Steps (Week 2+)**
1. **Advanced Features:** Webhook endpoints, bulk operations
2. **Multiple Marketplace Support:** Add additional suppliers
3. **Reporting & Analytics:** Sync status dashboards
4. **Mobile Optimization:** Responsive design testing
5. **API Rate Limiting:** Advanced throttling controls

---

## 📋 IMPLEMENTATION SUMMARY

**Total Development Time:** 40 hours (1 week sprint)  
**Module Architecture:** Generic, multi-supplier compatible  
**Integration Approach:** Extend existing views, minimal new interfaces  
**Field Strategy:** Universal cartona_id for all external integrations  
**Naming Conventions:** Products (no prefix), Partners (retailer_ prefix)  
**API Strategy:** Bearer token authentication, RESTful endpoints  
**Queue System:** Background processing for all sync operations  
**Error Handling:** Automatic retry with comprehensive logging  

**Key Success Factors:**
- Leverages existing Odoo workflows
- Provides universal external ID matching
- Supports unlimited marketplace integrations
- Maintains data consistency and reliability
- Offers seamless user experience

**Ready for Production:** Module designed for immediate deployment upon completion of Week 1 sprint with comprehensive testing and validation procedures.
