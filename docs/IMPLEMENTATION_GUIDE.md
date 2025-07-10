# Marketplace Supplier Integration - Implementation Guide

**Last Updated:** June 24, 2025  
**Project Status:** Development Ready - Architecture Finalized  
**Compatibility:** Odoo 15.0+, 16.0+, 17.0+ with version-specific adaptations  
**Current Phase:** Foundation Setup & Core Development

## Overview

This guide provides step-by-step instructions for implementing a Cartona marketplace integration module for Odoo. This module enables suppliers to connect their Odoo system directly to the Cartona marketplace platform for bidirectional synchronization of products, prices, inventory, and orders. Each supplier installs this module in their own Odoo instance and connects using their unique Cartona authentication token.

**Integration Model:**
- **One Odoo Instance = One Supplier**
- **Each Supplier** installs this module in their Odoo system
- **Each Supplier** receives a unique authentication token from Cartona
- **Direct Connection:** Supplier's Odoo ↔ Cartona Marketplace Platform

## **Current Development Phase (June 24, 2025)**

### **🚀 Phase 1: Foundation & Core Logic - IN PROGRESS**
**Status:** Active Development  
**Timeline:** June 24-30, 2025 (Week 1)  
**Focus:** Module structure, API framework, and basic synchronization

### **� Development Progress Checklist**
- [ ] **Module Structure** - Create basic Odoo module with manifest
- [ ] **Model Extensions** - Add cartona_id fields to product.template, product.product, res.partner
- [ ] **API Framework** - Build reusable API client with authentication
- [ ] **Configuration System** - Supplier setup and token management
- [ ] **Basic Sync Logic** - Product and order synchronization foundations
- [ ] **View Extensions** - Enhance existing product/order forms with Cartona fields
- [ ] **Testing Framework** - Unit tests and API connection validation

### **🎯 Next Milestones**
- **Week 2 (July 1-7):** Advanced sync features, webhooks, and real-time updates
- **Final Week (July 8):** Testing, documentation, and deployment preparation

### **🔑 Critical Requirements Status**
**Priority:** URGENT - Needed for development and testing  
**Action:** Obtain sample product and order data from your marketplace/supplier platform  
**Why Critical:** 
- **Real Data Structure:** Need actual product data to understand field mappings and data formats
- **API Testing:** Require real examples to test product matching and order processing logic
- **Validation:** Sample data helps validate that our cartona_id approach works with actual supplier products
- **Edge Cases:** Real data reveals edge cases and special scenarios not covered in documentation

### **🏗️ Development Ready - Foundation Setup**
**Priority:** HIGH - Can start immediately  
**Action:** Begin Step 1: Foundation Setup development  
**Why Ready Now:**
- **Independent Work:** Foundation setup doesn't require external dependencies
- **Uses Existing Knowledge:** Leverages existing Odoo expertise
- **Parallel Development:** Can proceed while waiting for sample data and API access
- **Early Validation:** Allows testing of basic concepts and module structure

**Technical Tasks:**
- Set up local Odoo development environment (multiple version support)
- Create `marketplace_integration` module structure with version compatibility
- Add `cartona_id` field to `product.template` and `product.product` models
- **Extend existing Odoo views** rather than creating separate product/order views
- Add `cartona_id` field to `res.partner` model for customer/supplier matching
- Build basic configuration interface for multiple supplier API credentials
- Implement API connection testing framework
- Ensure compatibility across different Odoo versions

## **Module View Architecture**

### **Design Philosophy: Extend, Don't Duplicate**
This module follows the principle of extending existing Odoo functionality rather than creating duplicate views:

✅ **Extend Product Views** - Add marketplace sync fields to existing product forms  
✅ **Extend Sales Order Views** - Add sync status to existing order management  
✅ **Minimal New Views** - Only configuration and monitoring views are new  
❌ **No Duplicate Product Management** - Use existing product views  
❌ **No Duplicate Order Management** - Use existing sales order views  

### **View Structure Overview**

**Extended Views (Inherit Existing):**
- **Product Template/Product Variant Forms** - Add `cartona_id` and sync status
- **Sales Order Forms** - Add marketplace sync status and controls
- **Stock Quant Views** - Add real-time sync indicators

**New Views (Module-Specific):**
- **Marketplace Configuration** - Supplier setup and API credentials
- **Sync Monitoring Dashboard** - Overall integration health
- **Connection Testing** - API connectivity validation

**Benefits of This Approach:**
- **Familiar Interface** - Users work with existing Odoo screens they know
- **Reduced Training** - No need to learn new interfaces
- **Seamless Integration** - Marketplace features blend into normal workflow
- **Lower Maintenance** - Fewer views to maintain and update
- **Better UX** - All product info in one place, all order info in one place

### **Specific View Extensions**

**1. Product Template/Product Variant Forms (`product.template`, `product.product`)**
```xml
<!-- Extend existing product forms -->
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
                        class="btn-primary" attrs="{'invisible': [('cartona_id', '=', False)]}"/>
            </group>
        </group>
    </field>
</record>
```

**2. Sales Order Forms (`sale.order`)**
```xml
<!-- Extend existing sales order forms -->
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
                <field name="marketplace_sync_date"/>
                <button name="update_marketplace_status" string="Update Status" 
                        type="object" class="btn-primary"/>
            </group>
        </group>
    </field>
</record>
```

**3. Stock Quant Views (`stock.quant`)**
```xml
<!-- Add sync status to inventory views -->
<record id="view_stock_quant_tree_marketplace" model="ir.ui.view">
    <field name="name">stock.quant.tree.marketplace</field>
    <field name="model">stock.quant</field>
    <field name="inherit_id" ref="stock.view_stock_quant_tree"/>
    <field name="arch" type="xml">
        <field name="quantity" position="after">
            <field name="marketplace_sync_status" string="Sync Status"/>
        </field>
    </field>
</record>
```

**4. Partner Forms (`res.partner`)**
```xml
<!-- Extend existing partner forms -->
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

**4. New Configuration Views (Module-Specific Only)**
```xml
<!-- Only new view: Marketplace supplier configuration -->
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
                    </group>
                    <group>
                        <field name="auto_sync_products"/>
                        <field name="auto_sync_orders"/>
                        <field name="sync_frequency"/>
                    </group>
                </group>
            </sheet>
        </form>
    </field>
</record>
```

**Key Integration Points:**
- **Product Management:** All done through existing product views with added sync fields
- **Order Management:** All done through existing sales order views with marketplace status
- **Inventory Management:** Stock sync indicators added to existing inventory views
- **Configuration:** Only new views are for supplier setup and monitoring

**User Workflow:**
1. **Setup:** Configure suppliers in marketplace settings (new view)
2. **Products:** Manage products in standard product views (extended)
3. **Orders:** Process orders in standard sales order views (extended)
4. **Inventory:** Monitor stock in standard inventory views (extended)
5. **Monitoring:** Check sync status in marketplace dashboard (new view)

### **Module Views Summary**

**Total Views Required: Only 3-4 New Views**

**New Views (Module-Specific):**
1. **Marketplace Supplier Configuration** - Setup and manage API credentials
2. **Sync Monitoring Dashboard** - Overall integration health and status
3. **Connection Test Wizard** - Test API connectivity
4. **Sync Log Viewer** - View sync history and errors (optional)

**Extended Views (Inherit Existing):**
- **Product Template/Variant Forms** - Add cartona_id and sync controls
- **Sales Order Forms** - Add marketplace order status and sync controls  
- **Stock Quant Views** - Add sync status indicators
- **Product Tree Views** - Add sync status column (optional)

**Benefits of Minimal View Approach:**
✅ **Familiar User Experience** - Users stay in views they already know  
✅ **Reduced Development Time** - Fewer views to create and maintain  
✅ **Lower Training Requirements** - No new interfaces to learn  
✅ **Seamless Integration** - Feels like native Odoo functionality  
✅ **Easier Maintenance** - Fewer custom views to update with Odoo upgrades  
✅ **Better Performance** - Leverages existing optimized views  

**What Users Will NOT See:**
❌ Separate "Marketplace Products" menu  
❌ Separate "Marketplace Orders" menu  
❌ Duplicate product management interface  
❌ Duplicate order management interface  
❌ Complex marketplace-specific dashboards  

**What Users WILL See:**
✅ Enhanced product forms with sync fields  
✅ Enhanced sales order forms with marketplace status  
✅ Simple marketplace configuration menu  
✅ Sync monitoring dashboard  
✅ All marketplace features integrated into normal workflow  

This approach ensures the marketplace integration feels like a natural extension of Odoo rather than a separate system bolted on top.

## **Minimal Database Tables to Start Development**

### **Essential Tables (4 Only)**

#### **Product Data**
- **`product_template`** - Contains product names, prices, and categories for sync logic
- **`product_product`** - Contains product variants and SKUs for complete matching

#### **Reference Data** 
- **`product_category`** - Contains product classifications referenced by templates
- **`res_company`** - Contains company information needed for API configuration

### **Additional Tables for Complete Integration**

#### **Customer & Stock Data**
- **`res_partner`** - Customer information for order processing
- **`stock_location`** - Warehouse locations for inventory calculations
- **`stock_quant`** - Current stock levels for real-time sync

#### **Order Management**
- **`sale_order`** - Order structure and status workflow
- **`sale_order_line`** - Product-order relationships and pricing
- **`res_currency`** - Currency handling for multi-currency support

### **Quick Data Extraction Script**
```sql
-- Execute this script to get minimal sample data
-- Only 4 tables, ~20-30 records each

-- 1. Product Templates (20 records)
\copy (
    SELECT id, name, list_price, categ_id, active, default_code, barcode
    FROM product_template 
    WHERE active = true
    ORDER BY create_date DESC
    LIMIT 20
) TO 'product_template_minimal.csv' CSV HEADER;

-- 2. Product Variants (30 records)
\copy (
    SELECT id, product_tmpl_id, default_code, active, barcode
    FROM product_product 
    WHERE active = true
    ORDER BY create_date DESC
    LIMIT 30
) TO 'product_product_minimal.csv' CSV HEADER;

-- 3. Product Categories (all categories)
\copy (
    SELECT id, name, parent_id, complete_name
    FROM product_category
    ORDER BY complete_name
) TO 'product_category_minimal.csv' CSV HEADER;

-- 4. Company Configuration (1 record)
\copy (
    SELECT id, name, currency_id, country_id
    FROM res_company
    LIMIT 1
) TO 'res_company_minimal.csv' CSV HEADER;

\echo 'SUCCESS: Minimal data extracted!'
\echo 'Files created: 4 CSV files with ~50 total records'
\echo 'Ready to start Phase 1 development immediately'
```

### **How to Use These Tables**

**Step 1: Foundation Development**
- Use `product_template` and `product_product` to add cartona_id field
- Use `product_category` for product classification validation
- Use `res_company` for API configuration testing

**Step 2: Expand for Full Integration**
- Add `res_partner` for customer data handling
- Add `stock_location` and `stock_quant` for inventory sync
- Add `sale_order` and `sale_order_line` for order management
- Add `res_currency` for multi-currency support

### **Single Command to Start**
```bash
# Save the SQL script above as 'minimal_data.sql' then run:
psql -h your-server -d your-database -U your-user -f minimal_data.sql

# Result: 4 small CSV files, ready to begin development
```

**Bottom Line:** Start with just 4 tables and ~50 records total. This is enough to build and test the core integration concepts before expanding to the full system.

## Multi-Supplier Configuration

### **Supplier-Side Integration Architecture**
This module is designed for **supplier-side installation**, where each supplier installs the module in their own Odoo instance to connect to the Cartona marketplace.

**Architecture Overview:**
- **Individual Supplier Integration:** Each supplier has their own Odoo instance with this module
- **Unique Authentication:** Each supplier receives a unique auth token from Cartona
- **Direct API Connection:** Each supplier's Odoo connects directly to Cartona's API
- **Independent Operations:** Each supplier manages their own products, orders, and customers

**Configuration Per Supplier:**
```python
# Each supplier configures their own connection
supplier_config = {
    'supplier_name': 'Your Company Name',
    'auth_token': 'eyJhbGciOiJIUzI1NiJ9...',  # Unique token from Cartona
    'sync_settings': {
        'auto_sync_products': True,
        'auto_sync_orders': True,
        'auto_sync_stock': True
    }
}
```

**Configuration Structure:**
```python
# Fixed API configuration for all suppliers (Cartona platform)
CARTONA_API_CONFIG = {
    'base_url': 'https://supplier-integrations.cartona.com/api/v1/',
    'auth_method': 'bearer_token',
    'auth_header': 'AuthorizationToken',
    'endpoints': {
        'orders': {
            'pull': '/order/pull-orders',
            'update_status': '/order/update-order-status',
            'update_details': '/order/update-order-details'
        },
        'products': {
            'list': '/supplier-product',
            'bulk_update': '/supplier-product/bulk-update',
            'base_products': '/supplier-product/base-products',
            'base_update': '/supplier-product/base-product/bulk-update',
            'stock_update': '/supplier-product/base-product/bulk-update-stock'
        }
    }
}

# Per-supplier configuration (each supplier configures their own instance)
supplier_instance_config = {
    'supplier_name': 'ABC Foods Ltd',
    'auth_token': 'eyJhbGciOiJIUzI1NiJ9...',  # Unique token from Cartona
    'sync_settings': {
        'auto_sync_orders': True,
        'auto_sync_stock': True,
        'bulk_operations': True
    }
}
```
            'auto_sync_stock': True,
            'bulk_operations': True
        }
    }
]
```

**Benefits of Supplier-Side Integration:**
- **Direct Control:** Each supplier manages their own integration and data
- **Simple Setup:** Each supplier needs only their unique Cartona auth token
- **Independent Operations:** No dependency on other suppliers' configurations
- **Scalable Platform:** Cartona can onboard unlimited suppliers independently
- **Data Privacy:** Each supplier's data stays in their own Odoo instance
- **Custom Settings:** Each supplier can configure sync preferences independently

**Implementation Strategy:**
- Build core framework that works with any API
- Create supplier-specific configuration profiles
- Use abstract classes for common integration patterns
- Implement supplier-specific adapters for unique requirements

### **API Endpoints Reference**
Based on the provided API structure, here are the key endpoints that the generic module should support:

**Authentication:**
- **Method:** Bearer Token authentication
- **Header:** `AuthorizationToken: {{token}}`
- **Base URL:** `https://{{domain}}/api/v1/`

**Core API Endpoints:**

**1. Order Management:**
```
GET  /order/pull-orders           # Pull new orders from marketplace
POST /order/update-order-status   # Update order status (synced, approved, delivered)
POST /order/update-order-details  # Update order items (quantities, cancellations, additions)
```

**2. Product Management:**
```
GET  /supplier-product                    # List supplier products
POST /supplier-product/bulk-update        # Update product stock, pricing, availability
GET  /supplier-product/base-products      # List base products catalog
POST /supplier-product/base-product/bulk-update       # Update base product details
POST /supplier-product/base-product/bulk-update-stock # Update stock across all units
```

**Generic API Configuration:**
```python
# Fixed API Configuration Structure - Same for all suppliers
class MarketplaceAPIConfig:
    BASE_URL = 'https://supplier-integrations.cartona.com/api/v1/'
    AUTH_METHOD = 'bearer_token'
    AUTH_HEADER = 'AuthorizationToken'
    
    ENDPOINTS = {
        'orders': {
            'pull': '/order/pull-orders',
            'update_status': '/order/update-order-status',
            'update_details': '/order/update-order-details'
        },
        'products': {
            'list': '/supplier-product',
            'bulk_update': '/supplier-product/bulk-update',
            'base_products': '/supplier-product/base-products',
            'base_update': '/supplier-product/base-product/bulk-update',
            'stock_update': '/supplier-product/base-product/bulk-update-stock'
        }
    }

# Per-supplier configuration model
api_config = {
    'base_url': MarketplaceAPIConfig.BASE_URL,
    'auth_method': MarketplaceAPIConfig.AUTH_METHOD,
    'auth_header': MarketplaceAPIConfig.AUTH_HEADER,
    'endpoints': MarketplaceAPIConfig.ENDPOINTS,
    # Only these fields vary per supplier:
    'supplier_domain': '{{supplier_domain}}',  # e.g., 'api.cartona.com'
    'auth_token': '{{supplier_token}}'         # e.g., 'eyJhbGciOiJIUzI1NiJ9...'
}
```

**Key API Features:**
- **Bulk Operations:** All update operations support bulk processing for efficiency
- **Pagination:** List endpoints support `page` and `per_page` parameters
- **Filtering:** Search and filter capabilities on product endpoints
- **Stock Management:** Separate endpoints for product-level and base-product stock updates
- **Order Flexibility:** Support for order detail modifications (quantity changes, cancellations, additions)

### **API Request/Response Examples**

**Order Status Update:**
```json
// Request Body for updating order status
[
    {
        "status": "synced",           // synced, approved, delivered
        "hashed_id": "31387392471"
    },
    {
        "status": "delivered",
        "hashed_id": "568058982471",
        "retailer_otp": "123456"      // For delivery confirmation
    }
]
```

**Product Stock Update:**
```json
// Request Body for bulk product updates
[
    {
        "internal_product_id": "103",
        "min_order": 1,
        "max_order": 20,
        "available_stock_quantity": 10000,
        "in_stock": true,
        "is_published": true
    },
    {
        "internal_product_id": "100",
        "min_order": 1,
        "max_order": 10,
        "available_stock_quantity": 5000,
        "in_stock": false,
        "is_published": false
    }
]
```

**Order Details Update:**
```json
// Request Body for modifying order items
[
    {
        "hashed_id": "31387392471",
        "order_details": [
            {
                "id": 11988950,
                "amount": 5.0              // Update quantity
            },
            {
                "id": 11988951,
                "cancelled": true          // Cancel order line
            },
            {
                "internal_product_id": "104",
                "amount": 4.0,
                "price": 320               // Add new order line
            }
        ]
    }
]
```

**Base Product Stock Update:**
```json
// Request Body for base product stock (affects all variants)
[
    { 
        "base_product_id": 4090,
        "available_stock_quantity": 300
    }
]
```

## Development Implementation Phases

### **Phase 1: Foundation Setup**
**Prerequisites:** Sample data from marketplace/supplier platform, API credentials  
**Dependencies:** None - can start immediately

**Objectives:**
- Establish core module structure and API connectivity
- Implement configuration management system
- Add product identification schema

**Tasks:**
- [ ] **Module Setup:** Create marketplace_integration module structure
- [ ] **Database Schema:** Add cartona_id field to product models
- [ ] **Partner Integration:** Add cartona_id field to res.partner model
- [ ] **API Framework:** Build connection and authentication system
- [ ] **Configuration UI:** Create admin interface for multiple supplier settings
- [ ] **Testing Framework:** Basic API connection testing capability

**Deliverables:**
- Working module structure with proper dependencies (`queue_job` for async operations, `sale` for orders, `stock` for inventory)
- Product models extended with cartona_id field (for product matching between systems)
- Partner models extended with cartona_id field (for customer matching between systems)
- Multi-supplier configuration interface accessible to admin users
- API authentication and connection testing for multiple suppliers
- Basic error logging and monitoring framework

**Completion Criteria:**
- [ ] Module loads successfully in Odoo without errors
- [ ] cartona_id field visible and functional in product forms
- [ ] cartona_id field visible and functional in partner forms
- [ ] Configuration interface accessible to admin users for multiple suppliers
- [ ] API connection test passes with valid credentials for configured suppliers
- [ ] Basic error logging captures and displays issues

### **Phase 2: Product & Partner Synchronization**
**Prerequisites:** Phase 1 complete, sample product data available  
**Dependencies:** Phase 1

**Objectives:**
- Establish reliable product matching between systems
- Implement customer/supplier matching and creation
- Create tools for initial data migration
- Implement validation and error handling

**Tasks:**
- [ ] **Product Matching:** Implement cartona_id-based product identification
- [ ] **Partner Matching:** Implement cartona_id-based customer/supplier identification
- [ ] **Customer Creation:** Build automatic customer creation from marketplace orders
- [ ] **Validation:** Build product and partner data integrity checks
- [ ] **Migration Tools:** Create bulk product and partner import functionality
- [ ] **UI Enhancement:** Extend existing forms with sync status indicators
- [ ] **Testing:** Validate matching with sample data

**Deliverables:**
- Reliable product identification system
- Customer/supplier matching and automatic creation system
- Bulk import tool for existing products and partners
- Enhanced forms with marketplace sync fields (no separate views)
- Validation framework with clear error messages
- UI enhancements integrated into existing Odoo workflows

**Completion Criteria:**
- [ ] Products successfully matched using cartona_id
- [ ] Customers/suppliers successfully matched using cartona_id (with retailer_ prefix)
- [ ] Automatic customer creation from marketplace data works
- [ ] Bulk import tool processes existing data without errors
- [ ] Validation catches and reports data integrity issues
- [ ] Marketplace sync fields visible in existing forms
- [ ] Error handling works for missing or invalid mappings
- [ ] No duplicate views created - all extensions to existing views

### **Phase 3: Real-time Price & Stock Synchronization**
**Prerequisites:** Phase 2 complete, queue system configured  
**Dependencies:** Phase 1, Phase 2

**Objectives:**
- Implement real-time price updates to marketplace platforms
- Add instant stock synchronization
- Ensure reliable delivery with queue system

**Tasks:**
- [ ] **Price Triggers:** Override product write() method for price changes
- [ ] **Queue System:** Implement async API calls with queue_job
- [ ] **Stock Monitoring:** Add inventory change detection
- [ ] **Error Handling:** Build retry mechanisms and error logging
- [ ] **Performance Testing:** Validate sync speed targets (<5 seconds)
- [ ] **Bulk Operations:** Handle mass price/stock updates efficiently

**Deliverables:**
- Real-time price synchronization (<5 second updates)
- Queue system with automatic retry capability
- Stock sync with multi-warehouse support
- Comprehensive logging and error reporting
- Performance optimization for bulk operations

**Completion Criteria:**
- [ ] Real-time price sync completes within 5 seconds
- [ ] Stock updates reflect immediately on marketplace platforms
- [ ] Queue system handles failures with automatic retry
- [ ] Error rate below 1% with automatic recovery
- [ ] Bulk operations complete without blocking UI

## Technical Environment Setup

### **Development Environment Requirements**
**Each requirement serves a specific purpose for successful integration:**

- **Odoo (multiple version compatibility - 15.0+, 16.0+, 17.0+)**
  - *Why needed:* Core platform for the integration module
  - *Multi-version support:* Ensures wider adoption and reduces maintenance overhead for different client environments
  - *Version range rationale:* Covers most active Odoo installations in production use

- **PostgreSQL database**
  - *Why needed:* Odoo's primary database system, required for storing cartona_id mappings and integration logs
  - *Performance benefit:* Better handling of concurrent API operations and data synchronization

- **Python 3.8+ with required packages**
  - *Why needed:* Odoo's runtime environment and API request handling
  - *Version rationale:* 3.8+ ensures compatibility with modern Odoo versions and security updates

- **Git for version control**
  - *Why needed:* Code versioning, collaboration, and deployment management
  - *Integration benefit:* Enables proper testing and rollback procedures

- **Access to marketplace/supplier API documentation**
  - *Why needed:* Reference for endpoint structures, authentication methods, and data formats
  - *Development efficiency:* Prevents trial-and-error development approach

### **Module Dependencies**
**Each dependency addresses specific integration requirements:**

- **`queue_job` - For asynchronous processing**
  - *Why critical:* Prevents UI blocking during API calls and ensures reliable delivery
  - *Business impact:* Users can continue working while sync operations run in background
  - *Reliability:* Automatic retry capability for failed operations

- **`sale` - For sales order integration**
  - *Why needed:* Core functionality for importing and managing marketplace orders
  - *Data integrity:* Ensures proper order workflow and status tracking

- **`stock` - For inventory synchronization**
  - *Why needed:* Real-time stock updates to marketplace platforms
  - *Business critical:* Prevents overselling and maintains accurate inventory levels

- **`base` - Core Odoo functionality**
  - *Why needed:* Provides fundamental Odoo framework and database access
  - *Foundation requirement:* All custom modules depend on base functionality

### **API Integration Setup**
**Each component ensures secure and reliable API communication:**

- **Marketplace/supplier API credentials (test environment)**
  - *Why test environment first:* Prevents accidental live marketplace changes during development
  - *Safety measure:* Allows full testing without business impact
  - *Development efficiency:* Enables iterative testing and debugging

- **Webhook endpoint configuration**
  - *Why needed:* Real-time order pull and status updates from marketplace platforms
  - *Performance benefit:* Eliminates need for polling and reduces API usage
  - *User experience:* Instant order processing improves customer satisfaction

- **SSL certificates for secure communication**
  - *Why required:* Protects sensitive business data during API communication
  - *Compliance need:* Meets security standards for financial and customer data
  - *Trust factor:* Ensures secure integration between business systems

- **Rate limiting and authentication setup**
  - *Why critical:* Prevents API overuse and ensures authorized access only
  - *System stability:* Protects both marketplace and Odoo systems from overload
  - *Business continuity:* Ensures consistent service availability

---

## Odoo Version Compatibility

### **Multi-Version Support Strategy**
The marketplace integration module is designed to be compatible with multiple Odoo versions to maximize adoption and reduce maintenance overhead.

**Target Versions:**
- Odoo 15.0+ (Community and Enterprise)
- Odoo 16.0+ (Community and Enterprise) 
- Odoo 17.0+ (Community and Enterprise)
- Future versions through backward-compatible design

**Compatibility Considerations:**
- Use standard Odoo ORM methods that are stable across versions
- Avoid version-specific features or APIs
- Implement conditional imports for version-specific functionality
- Use abstract base classes for core functionality
- Maintain separate view files for version-specific UI differences

**Implementation Approach:**
```python
# Add cartona_id field to products and partners
# These fields will store the supplier's unique identifiers

from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    cartona_id = fields.Char(
        string="External Product ID",
        help="Links this product to marketplace/supplier platform"
    )

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    cartona_id = fields.Char(
        string="External Product ID", 
        help="Links this product variant to marketplace/supplier platform"
    )

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    cartona_id = fields.Char(
        string="External Partner ID",
        help="Links this partner to marketplace/supplier platform"
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

**Why this works:** Each Odoo product gets a `cartona_id` field that stores the external supplier's product ID, and each partner gets a `cartona_id` field for customer/supplier matching, making it easy to match both products and customers between systems regardless of which marketplace or supplier platform is being integrated.

**Multi-Version Compatibility:** This basic field definition works across all Odoo versions (15.0+, 16.0+, 17.0+) because it uses standard Odoo field types that haven't changed between versions.

**Testing Strategy:**
- Test core functionality on all target Odoo versions
- Maintain compatibility test suite
- Document any version-specific limitations or requirements

## Partner Integration (Customers/Suppliers)

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

**Simplified Supplier Configuration Example:**
```python
# Fixed API structure - same for all suppliers
FIXED_CONFIG = {
    'base_url_template': 'https://{domain}/api/v1/',
    'auth_header': 'AuthorizationToken',
    'auth_method': 'bearer_token'
}

# Per-supplier configuration - only domain and token vary
supplier_config = {
    'name': 'Cartona Marketplace',
    'domain': 'api.cartona.com',              # Only this varies
    'auth_token': 'eyJhbGciOiJIUzI1NiJ9...',  # Only this varies
    'active': True,
    'auto_sync_products': True,
    'auto_sync_orders': True
}

# Another supplier example
supplier_config_2 = {
    'name': 'Another Marketplace',
    'domain': 'marketplace-b.com',            # Only this varies  
    'auth_token': 'abc123def456...',          # Only this varies
    'active': True,
    'auto_sync_products': False,
    'auto_sync_orders': True
}
```

**Key Benefits of Fixed API Structure:**
- **Consistency:** All suppliers use the same API endpoints and authentication method
- **Simplicity:** Only domain and token need to be configured per supplier
- **Maintainability:** Single API client handles all suppliers
- **Standardization:** Bearer token authentication across all integrations
