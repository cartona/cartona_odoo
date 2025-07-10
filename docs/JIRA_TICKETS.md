# Cartona-Odoo Integration - Jira Tickets

## Epic: Cartona-Odoo Integration Module
**Summary:** Enable ALL Odoo suppliers to sync with Cartona marketplace  
**Business Value:** Expand market reach for all suppliers and reduce manual work

**Business Logic Clarification:**
Cartona marketplace runs on Odoo with ALL suppliers' products in one system. This module serves TWO different use cases:

**Case 1: Cartona's Internal Odoo (Marketplace System)**
- Contains products from ALL suppliers in the marketplace
- `cartona_id IS NULL` = Products belong to external suppliers
- `cartona_id HAS VALUE` = Products belong to Cartona shops (Cartona acting as supplier)
- Uses conditional logic: `IF cartona_id IS NOT NULL THEN sync to marketplace`

**Case 2: External Suppliers' Odoo Systems**
- Contains ONLY that supplier's products
- NO `cartona_id` field needed
- ALL products sync to Cartona marketplace
- Uses simple logic: `ALL products sync to marketplace`

**Key Design Principles:**
- **Dual Architecture:** Module works differently in Cartona's Odoo vs External Suppliers' Odoo
- **Conditional Logic:** `cartona_id` field only exists in Cartona's internal system
- **Universal Sync:** External suppliers sync ALL their products to marketplace
- **Supplier Detection:** Module automatically detects if it's running in Cartona's system or supplier's system
- **Version Compatibility:** Support multiple Odoo versions with conditional features
- **Environment-Aware:** Different behavior based on deployment environment

---

## Phase 0: Analysis & Requirements

### CART-001: Project Kickoff & Stakeholder Alignment
**Type:** Story  
**Priority:** Highest  
**Story Points:** 2

**Summary:** Conduct project kickoff and align stakeholders

**Description:**
Organize project kickoff meeting to align business and technical teams.

**Acceptance Criteria:**
- [ ] Kickoff meeting conducted with key stakeholders
- [ ] Project scope and objectives defined
- [ ] Team roles and responsibilities assigned
- [ ] Communication plan established

---

### CART-002: Business Requirements Analysis
**Type:** Story  
**Priority:** Highest  
**Story Points:** 3

**Summary:** Gather and document business requirements for dual deployment scenarios

**Description:**
Understand business needs for two different deployment scenarios:
1. **Cartona's Internal Odoo:** Module filters products using cartona_id field
2. **External Suppliers' Odoo:** Module syncs ALL products to marketplace

**Acceptance Criteria:**
- [ ] **Cartona Internal System requirements documented** (cartona_id filtering logic)
- [ ] **External Supplier System requirements documented** (sync all products)
- [ ] Environment detection logic defined (how to detect deployment type)
- [ ] User stories created for both deployment scenarios with clear differentiation
- [ ] Success criteria established for each deployment type
- [ ] Stakeholder sign-off obtained on dual-architecture approach

---

### CART-003: Technical Architecture Analysis
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Analyze technical requirements and design architecture

**Description:**
Review Cartona API, analyze Odoo system, and design integration architecture.

**Acceptance Criteria:**
- [ ] Cartona API analysis completed
- [ ] Odoo system architecture reviewed
- [ ] Integration design documented
- [ ] Technical approach approved

---

### CART-004: Sample Data Requirements
**Type:** Story  
**Priority:** High  
**Story Points:** 2

**Summary:** Define sample data needs for development

**Description:**
Analyze production data structure and define sample data requirements.

**Acceptance Criteria:**
- [ ] Production database structure analyzed
- [ ] Sample data requirements documented
- [ ] Data extraction approach defined
- [ ] Privacy considerations addressed

---

### CART-005: API Integration Planning
**Type:** Story  
**Priority:** High  
**Story Points:** 3

**Summary:** Plan API integration approach

**Description:**
Study Cartona API capabilities and plan integration strategy.

**Acceptance Criteria:**
- [ ] API documentation reviewed
- [ ] Integration patterns identified
- [ ] Authentication approach defined
- [ ] Error handling strategy planned

---

## Phase 1: Foundation Setup

### CART-006: Create Module Structure
**Type:** Story  
**Priority:** High  
**Story Points:** 3

**Summary:** Set up basic Cartona integration module

**Description:**
Create the foundational module structure for Cartona-Odoo integration.

**Acceptance Criteria:**
- [ ] Module loads in Odoo without errors
- [ ] Basic module structure and dependencies configured
- [ ] Module can be installed successfully

---

### CART-007: Add cartona_id Field (Conditional)
**Type:** Story  
**Priority:** High  
**Story Points:** 2

**Summary:** Add cartona_id field ONLY in Cartona's internal system

**Description:**
Add cartona_id field to product models, but ONLY when module is deployed in Cartona's internal Odoo system. External suppliers' systems don't need this field.

**Acceptance Criteria:**
- [ ] **Environment detection:** Module detects if running in Cartona's internal system
- [ ] **Conditional field creation:** cartona_id field added ONLY in Cartona's internal system
- [ ] **External supplier systems:** Field NOT created in external suppliers' Odoo systems
- [ ] Field visible in product form view with conditional display
- [ ] Field validation works correctly
- [ ] Help text explains field usage for product filtering

---

### CART-008: Environment Detection Logic
**Type:** Story  
**Priority:** High  
**Story Points:** 3

**Summary:** Implement logic to detect deployment environment

**Description:**
Build logic to automatically detect whether the module is running in:
1. **Cartona's Internal Odoo** (marketplace system with all suppliers' products)
2. **External Supplier's Odoo** (individual supplier's system)

**Acceptance Criteria:**
- [ ] Environment detection algorithm implemented
- [ ] Configuration interface for manual environment assignment (if needed)
- [ ] Clear differentiation between Cartona internal vs external supplier deployment
- [ ] Default behavior defined for unclassified environments
- [ ] Environment type visible in module configuration
- [ ] Version compatibility maintained across Odoo versions

---

### CART-009: API Configuration
**Type:** Story  
**Priority:** High  
**Story Points:** 3

**Summary:** Create API settings interface

**Description:**
Build admin interface for managing Cartona API credentials and settings.

**Acceptance Criteria:**
- [ ] Configuration menu accessible to admin users
- [ ] API credentials can be saved securely
- [ ] Connection test functionality works

---

### CART-010: API Connection Framework
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Build API communication layer

**Description:**
Implement basic API communication with authentication and error handling.

**Acceptance Criteria:**
- [ ] API authentication working
- [ ] Basic error handling implemented
- [ ] Connection test passes with valid credentials

---

## Phase 2: Product Synchronization

### CART-011: Product Matching Logic
**Type:** Story  
**Priority:** High  
**Story Points:** 3

**Summary:** Implement environment-aware product matching logic

**Description:**
Build logic to match/filter products based on deployment environment:
- **Cartona Internal:** Filter products where cartona_id IS NOT NULL
- **External Supplier:** Match ALL products (no filtering needed)

**Acceptance Criteria:**
- [ ] **Cartona Internal:** Products filtered using cartona_id field (only non-null values sync)
- [ ] **External Supplier:** ALL products matched for sync (no filtering)
- [ ] Environment detection automatically applies correct matching logic
- [ ] Validation for missing identifiers based on environment type
- [ ] Error handling for invalid mappings with environment-specific messages

---

### CART-012: Bulk Product Setup
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3

**Summary:** Create environment-aware bulk product setup tools

**Description:**
Build tools to help configure products for Cartona integration based on deployment environment:
- **Cartona Internal:** Bulk cartona_id assignment for product filtering
- **External Supplier:** Bulk product validation (all products ready to sync)

**Acceptance Criteria:**
- [ ] **Cartona Internal:** Bulk cartona_id assignment interface available
- [ ] **External Supplier:** Bulk product validation and sync preparation interface
- [ ] CSV import/export functionality for both environment types
- [ ] Validation prevents duplicate IDs/identifiers
- [ ] Environment detection automatically applies correct setup method

---

## Phase 3: Real-time Sync

### CART-013: Price Sync
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Sync price changes with environment-aware filtering

**Description:**
Automatically sync product price changes from Odoo to Cartona marketplace using environment-specific logic:
- **Cartona Internal:** Sync only products where cartona_id IS NOT NULL
- **External Supplier:** Sync ALL product price changes

**Acceptance Criteria:**
- [ ] Price changes trigger sync within 5 seconds
- [ ] **Cartona Internal:** Only products with cartona_id sync to marketplace
- [ ] **External Supplier:** ALL products sync to marketplace
- [ ] Environment automatically detected for correct sync filtering
- [ ] Queue system prevents UI blocking
- [ ] Version compatibility maintained across Odoo versions

---

### CART-014: Stock Sync
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Sync stock levels to Cartona

**Description:**
Automatically sync inventory changes from Odoo to Cartona marketplace.

**Acceptance Criteria:**
- [ ] Stock changes trigger immediate sync
- [ ] Multi-warehouse support
- [ ] Error handling and retry logic

---

## Phase 4: Order Management

### CART-015: Order Pull
**Type:** Story  
**Priority:** High  
**Story Points:** 8

**Summary:** Pull orders with environment-aware product matching

**Description:**
Build system to receive and process orders from Cartona marketplace using environment-specific product matching logic.

**Acceptance Criteria:**
- [ ] Orders pulled automatically from Cartona
- [ ] **Cartona Internal:** Product matching via cartona_id field filtering
- [ ] **External Supplier:** Direct product matching (all products available)
- [ ] Customer auto-creation works for both environment types
- [ ] Order data validation with environment-specific rules
- [ ] Version compatibility maintained across Odoo versions

---

### CART-016: Special Payment Handling
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3

**Summary:** Handle special Cartona payment methods

**Description:**
Support OTP, installments, and Cartona credits payment methods.

**Acceptance Criteria:**
- [ ] OTP payment method supported
- [ ] Installment payments handled
- [ ] Cartona credits processed correctly

---

## Phase 5: Status Sync

### CART-017: Odoo to Cartona Status
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Sync order status changes to Cartona

**Description:**
Update Cartona when order status changes in Odoo.

**Acceptance Criteria:**
- [ ] Status changes trigger Cartona updates
- [ ] Proper status mapping between systems
- [ ] Error handling for failed updates

---

### CART-018: Cartona to Odoo Status
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Receive status updates from Cartona

**Description:**
Update Odoo orders when status changes in Cartona.

**Acceptance Criteria:**
- [ ] Status updates received from Cartona
- [ ] Odoo orders updated correctly
- [ ] Special delivery confirmation handling

---

## Phase 6: Production Ready

### CART-019: Error Handling
**Type:** Story  
**Priority:** High  
**Story Points:** 5

**Summary:** Implement comprehensive error handling

**Description:**
Build robust error handling with retry and logging.

**Acceptance Criteria:**
- [ ] Automatic retry with backoff
- [ ] Comprehensive error logging
- [ ] Manual retry tools available

---

### CART-020: Monitoring Dashboard
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5

**Summary:** Create sync monitoring dashboard

**Description:**
Build dashboard to monitor integration health and performance.

**Acceptance Criteria:**
- [ ] Real-time sync status display
- [ ] Success/failure statistics
- [ ] Manual operation tools

---

### CART-021: Documentation
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3

**Summary:** Complete user and admin documentation

**Description:**
Create comprehensive documentation for users and administrators.

**Acceptance Criteria:**
- [ ] User guide completed
- [ ] Admin setup guide available
- [ ] Troubleshooting documentation

---

## Additional Tasks

### CART-022: Sample Data Extraction
**Type:** Task  
**Priority:** High  
**Story Points:** 1

**Summary:** Extract sample data for development

**Description:**
Get minimal sample data from production to start development.

**Acceptance Criteria:**
- [ ] 4 core tables extracted (product_template, product_product, product_category, res_company)
- [ ] Data anonymized and ready for development

---

### CART-023: Multi-Version Testing
**Type:** Task  
**Priority:** Medium  
**Story Points:** 3

**Summary:** Test compatibility across Odoo versions

**Description:**
Ensure module works on Odoo 15.0+, 16.0+, and 17.0+.

**Acceptance Criteria:**
- [ ] Tested on Odoo 15.0+, 16.0+, 17.0+
- [ ] Compatibility issues resolved
- [ ] Version-specific notes documented

---

## Project Summary

**Total Story Points:** 93  
**Estimated Timeline:** 18-22 weeks  
**Phases:** 7 phases (Analysis + 6 Development phases)

**Phase Breakdown:**
- **Phase 0:** Analysis & Requirements (5 tickets, 15 points)
- **Phase 1:** Foundation Setup (5 tickets, 16 points) 
- **Phase 2:** Product Synchronization (2 tickets, 6 points)
- **Phase 3:** Real-time Sync (2 tickets, 10 points)
- **Phase 4:** Order Management (2 tickets, 11 points)
- **Phase 5:** Status Sync (2 tickets, 10 points)
- **Phase 6:** Production Ready (3 tickets, 13 points)
- **Additional Tasks:** (2 tickets, 4 points)

**Key Deliverables:**
- Comprehensive requirements and architecture documentation
- Working Odoo module with Cartona integration
- Real-time price and stock sync
- Automated order import and processing
- Bidirectional status synchronization
- Production-ready monitoring and error handling

**Success Criteria:**
- Requirements fully documented and approved
- Sync operations complete within 5 seconds
- Error rate below 1% with automatic recovery
- All features tested and documented
- Module compatible with multiple Odoo versions

**Critical Path:**
1. **Weeks 1-3:** Analysis and requirements (CART-001 to CART-005)
2. **Weeks 4-7:** Foundation development (CART-006 to CART-010)
3. **Weeks 8-18:** Feature development and testing
4. **Weeks 19-22:** Production readiness and deployment

---

## 🔑 FINAL BUSINESS LOGIC CLARIFICATION

**The Complete Picture:**

### **Two Different Deployment Scenarios:**

#### **Scenario 1: Cartona's Internal Odoo System (Marketplace Backend)**
- **Contains:** Products from ALL suppliers in the marketplace
- **cartona_id Field:** Used to filter which products belong to Cartona shops vs other suppliers
- **Sync Logic:** `IF cartona_id IS NOT NULL THEN sync to marketplace`
- **Purpose:** Cartona acts as BOTH marketplace AND supplier

#### **Scenario 2: External Supplier's Odoo System (Individual Supplier)**
- **Contains:** ONLY that supplier's own products
- **cartona_id Field:** NOT needed (field doesn't exist)
- **Sync Logic:** `ALL products sync to marketplace`
- **Purpose:** Supplier wants to sell their products on Cartona marketplace

### **Why This Architecture Makes Sense:**
1. **Cartona Internal:** Needs filtering because they have everyone's products but only want to sync their own
2. **External Suppliers:** No filtering needed because all their products should be on the marketplace
3. **Single Module:** Same codebase handles both scenarios through environment detection

### **Technical Implementation:**
```python
# Environment detection logic
if self.is_cartona_internal_system():
    # Cartona's internal system - filter by cartona_id
    products_to_sync = products.filtered(lambda p: p.cartona_id)
else:
    # External supplier system - sync all products
    products_to_sync = products
```

**This approach allows one module to serve both Cartona's internal needs and external suppliers' needs.**
