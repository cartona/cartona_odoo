# Cartona-Odoo Integration: Detailed Technical Implementation Guide

## 1. Document Overview

### 1.1. Purpose of This Document

This document provides a comprehensive, step-by-step technical guide for an Odoo developer to implement the integration between the Cartona Marketplace and the Odoo (Cartona Shop) system. It is designed to be extremely detailed to avoid any ambiguity.

### 1.2. Target Audience

This document is written for building the integration. It assumes a solid understanding of Odoo development but makes no assumptions about prior knowledge of the Cartona API or the specific business logic of this project.

## 2. Executive Summary

### 2.1. Why This Integration Is Needed

To eliminate manual data entry, reduce errors, and provide real-time data synchronization between the two systems. This is critical for scaling operations.

### 2.2. Key Technical Objectives

*   **Automate Data Exchange:** Create a robust, two-way automated data flow between Odoo and the Cartona Marketplace.
*   **Build a Custom Odoo Module:** All integration logic will be encapsulated within a new Odoo module named `cartona_integration`.
*   **Scheduled & Real-Time Sync:** Use a combination of scheduled tasks (cron jobs) and real-time updates (by overriding model methods) to keep data consistent.

## 3. Background and Context

### 3.1. Overview of Cartona Marketplace System

This is the external, customer-facing platform where retailers place orders. It has a set of APIs that we will use to get and send data.

### 3.2. Overview of Odoo (Cartona) System

This is the internal ERP system used for managing inventory, sales, and accounting. We will be building the integration within this system.

## 4. Project Scope: In-Scope Functionalities

### 4.1. Order Placement Sync (Cartona -> Odoo)

*   **Functionality:** Automatically pull new orders from Cartona and create them as Sales Orders in Odoo.
*   **API Endpoint:** `GET /api/v1/order/pull-orders`

### 4.2. Product Synchronization (Odoo -> Cartona)

*   **Functionality:** Update product stock levels and prices on the Cartona Marketplace when they change in Odoo.
*   **API Endpoint:** `POST /api/v1/supplier-product/bulk-update`
*   **Triggers:** 
    - Stock level changes (through stock movements)
    - Price changes (through product template updates)
*   **Data Synced:** Both stock quantities and selling prices are updated in the same API call for efficiency.

### 4.3. Fulfillment Status Updates (Bidirectional)

#### 4.3.1. Status Updates (Odoo -> Cartona)

*   **Functionality:** Update the order status on Cartona when the corresponding Sales Order in Odoo changes state (e.g., confirmed, shipped, canceled).
* **API Endpoint:** `POST /api/v1/order/update-order-status/<cartona_id>`

    **Note:** Use the actual `cartona_id` (hashed ID of the Cartona order) directly, without angle brackets (`< >`).

#### 4.3.2. Status Updates (Cartona -> Odoo)

*   **Functionality:** Receive order status updates from Cartona via webhook and update the corresponding Sales Order in Odoo.
*   **Webhook Endpoint:** `POST /cartona_integration/webhook/order_status` (to be implemented in Odoo)
*   **Purpose:** When Cartona updates an order status (e.g., payment confirmed, shipped, delivered), it will send a webhook to Odoo to keep the systems synchronized.


## 5. Technical Implementation Details

### 5.1. Odoo Module Setup (`cartona_integration`)

**Action:** Create a new custom addon in Odoo with the following structure.

```
cartona_integration/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── marketplace_webhook.py
├── data/
│   ├── cron_data.xml
│   └── queue_job_data.xml
├── models/
│   ├── __init__.py
│   ├── marketplace_api.py
│   ├── marketplace_config.py
│   ├── product_template.py
│   ├── res_partner.py
│   ├── sale_order.py
│   └── stock_move.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── marketplace_config_views.xml
    └── marketplace_menu.xml
```

**`__manifest__.py` High-Level Logic:**

Define the manifest file to declare the module's metadata.
- **Name:** 'Cartona Integration'
- **Version:** '1.0'
- **Summary:** A brief description of the module's purpose.
- **Dependencies:** Specify dependencies on `base`, `sale_management`, `stock`, and `queue_job`.
- **Data Files:** List all XML files for security, views, and data (cron jobs).
- **Application:** Set to `True` to make it a full application.

### 5.2. Configuration Model

**Purpose:** To securely store API credentials and settings in the Odoo database, accessible via a dedicated configuration menu.

**`models/marketplace_config.py` High-Level Logic:**

Create a new model `marketplace.config` to store the settings.
- **Fields:**
    - `name`: A character field for the configuration record name (e.g., 'Cartona Marketplace').
    - `api_url`: A character field for the base URL of the Cartona API.
    - `api_token`: A character field to store the secret API token.
    - `last_order_sync`: A datetime field to track the timestamp of the last successful order pull. This will be updated automatically by the cron job.

**`views/marketplace_config_views.xml` High-Level Logic:**

Define the user interface for the configuration model.
- **Form View:** Create a form view for the `marketplace.config` model. The layout should be simple, displaying fields for the API URL and token. The `last_order_sync` field should be read-only.
- **Window Action:** Define a window action that opens the configuration form. To ensure there's only one configuration record, this action should be configured to always open the same, pre-existing record.
- **Default Record:** Create a default `marketplace.config` record upon module installation so the user only has to fill in the details.

**`views/marketplace_menu.xml` High-Level Logic:**

Create the menu items for accessing the configuration.
- **Root Menu:** Add a main menu item named "Cartona" to the Odoo sidebar.
- **Configuration Submenu:** Inside the "Cartona" menu, add a "Configuration" submenu that triggers the window action defined above.

### 5.3. API Communication Layer

**Purpose:** To create a centralized, abstract model responsible for all API requests. This approach isolates API logic, making it easier to manage and debug.

**`models/marketplace_api.py` High-Level Logic:**

Create an abstract model `marketplace.api` that will not be stored in the database but will provide reusable API functions.
- **`_get_config()` Method:** A private helper function to fetch the single `marketplace.config` record. It should raise an error if the configuration is missing or the API token is not set.
- **`_make_request()` Method:** A generic, private method for executing API calls.
    - It should accept the endpoint, HTTP method, and data payload as arguments.
    - It should retrieve the API URL and token using `_get_config()`.
    - It must construct the full URL and set the required `AuthorizationToken` and `Content-Type` headers.
    - It should use the `requests` library to perform the HTTP request.
    - It must include robust error handling for network issues or bad responses (e.g., 4xx or 5xx status codes) and log them.
- **Authenticated API Methods:**
    - **`pull_orders()`:** Calls the `_make_request` method to perform an authenticated `GET` request to the `/api/v1/order/pull-orders` endpoint. Requires the `AuthorizationToken` header with the stored API token.
    - **`update_order_status(cartona_id, status)`:** Calls `_make_request` to perform an authenticated `POST` request to the `/api/v1/order/update-order-status/<cartona_id>` endpoint. Requires the `AuthorizationToken` header with the stored API token.
    - **`update_products(products_data)`:** Calls `_make_request` to perform an authenticated `POST` request to the `/api/v1/supplier-product/bulk-update` endpoint. Requires the `AuthorizationToken` header with the stored API token.

### 5.4. Feature Implementation

To ensure reliable synchronization, we will add a `cartona_id` field to the `res.partner`, `product.template`, and `sale.order` models. The `cartona_id` field serves different purposes for each model:
- **For Orders (`sale.order`):** Stores the `hashed_id` from Cartona orders
- **For Partners (`res.partner`):** Stores the retailer ID with naming convention `retailer_XXXXX` where XXXXX is the retailer's ID in Cartona Marketplace
- **For Products (`product.template`):** Stores the `supplier_product_id` from Cartona, while the Odoo product's `id` serves as the `internal_product_id` when syncing data to Cartona

Additionally, for orders, we will add a `delivered_by` field to control status update permissions:
- **`delivered_by="delivered_by_supplier"`:** Odoo can change to any status, Cartona can only change to cancel
- **`delivered_by="delivered_by_cartona"`:** Odoo can only change to cancel, Cartona can change to any status

This field will act as the key for all sync operations.

#### 5.4.1. Add External IDs to Models

**`models/res_partner.py` High-Level Logic:**

- Inherit the `res.partner` model.
- Add a new character field named `cartona_id`.
- This field should be indexed for fast searching. It will store the retailer ID from Cartona with the naming convention `retailer_XXXXX` where XXXXX is the retailer's ID in Cartona Marketplace.

**`models/product_template.py` High-Level Logic:**

- Inherit the `product.template` model.
- Add a new character field `cartona_id` (indexed) to store the `supplier_product_id` from Cartona.
- **Override the `write` method:**
    - After the original `write` method is called, check if the `list_price` (selling price) field was changed.
    - If it was, trigger an asynchronous background job (`with_delay()`) to sync the updated product data to Cartona. This prevents the user from having to wait for the API call to complete.
- **Stock Change Monitoring:**
    - Since `virtual_available` is a computed field, stock changes should be monitored through the stock movement system.
    - Create a method to be triggered when stock quantities change (either through stock moves, inventory adjustments, or other stock operations).
    - When stock changes are detected, trigger an asynchronous background job (`with_delay()`) to sync the updated stock levels to Cartona.
- **`sync_products_to_marketplace(product_ids)` Method:**
    - This method will be called by the `write` method override, stock change detection, and the daily cron job.
    - It should take a list of product IDs to sync.
    - For each product, it constructs a data dictionary containing:
        - `supplier_product_id`: The value from the product's `cartona_id` field
        - `internal_product_id`: The Odoo product's `id` (this is how Cartona identifies the product internally)
        - `selling_price`: The product's `list_price`
        - `available_stock_quantity`: The product's `virtual_available`
    - It then calls the `update_products` method from the `marketplace.api` service.
- **Inherit `product.product` model:**
    - Add a `cartona_id` field that is related to the `cartona_id` on the parent `product.template`, making it accessible at the variant level.

**Additional File Required: `models/stock_move.py` High-Level Logic:**

- Inherit the `stock.move` model to monitor stock changes.
- **Override the `_action_done` method:**
    - After the original method is called (when a stock move is completed), check if the move affects products that have a `cartona_id`.
    - If affected products are found, trigger an asynchronous background job (`with_delay()`) to sync the updated stock levels to Cartona.
    - Use the same `sync_products_to_marketplace` method from `product.template` to ensure consistency.

#### 5.4.2. Order Placement (Cartona -> Odoo)

**`models/sale_order.py` High-Level Logic:**

- Inherit the `sale.order` model.
- Add a `cartona_id` character field (indexed, read-only) to store the `hashed_id` of the order from Cartona.
- Add a `delivered_by` character field to store who handles delivery (`delivered_by_supplier` or `delivered_by_cartona`).
- **`cron_pull_orders()` Method:**
    - This method will be called by a cron job every X minutes.
    - It calls the `pull_orders` method from the `marketplace.api` service.
    - For each order received from the API, it should trigger an asynchronous background job (`with_delay()`) to create the order in Odoo, passing the order data payload to it.
- **`create_or_update_order(order_data)` Method:**
    - This method handles the creation of a single Sales Order.
    - **Step 1: Check for Duplicates:** Search for an existing `sale.order` with the same `cartona_id`. If found, stop processing to prevent duplicate orders.
    - **Step 2: Find or Create Customer:**
        - Get the retailer's unique ID from the order data.
        - Construct the `cartona_id` using the naming convention `retailer_XXXXX` where XXXXX is the retailer's ID from the order data.
        - Search for a `res.partner` with a matching `cartona_id`.
        - If the partner doesn't exist, create a new one using the name from the order data and the constructed `cartona_id`.
    - **Step 3: Create Order Lines:**
        - Loop through the `order_details` array in the order data.
        - For each item, get the `internal_product_id` (which corresponds to the Odoo product ID).
        - Search for the corresponding `product.product` in Odoo using the `internal_product_id` as the product's `id`.
        - If the product is not found, log a warning and skip that line item.
        - If found, create an order line tuple with the product, quantity, and price.
    - **Step 4: Create the Sales Order:**
        - If any valid order lines were created, create a new `sale.order` record.
        - Populate it with the `partner_id`, the `cartona_id`, the `delivered_by` value from order data, and the list of order lines.

#### 5.4.3. Fulfillment Status Updates (Bidirectional)

##### 5.4.3.1. Status Updates (Odoo -> Cartona)

**`models/sale_order.py` High-Level Logic:**

- **Override the `write` method:**
    - After the original `write` method is called, check if the `state` field of the Sales Order was changed.
    - **Business Rule Check:** Before syncing, verify the delivery permission rules:
        - If `delivered_by="delivered_by_cartona"`, only allow status changes to `cancel` to be synced to Cartona.
        - If `delivered_by="delivered_by_supplier"`, allow any status change to be synced to Cartona.
    - If the state was changed AND the order has a `cartona_id` AND the change is allowed by business rules, trigger an asynchronous background job (`with_delay()`) to sync the new status to Cartona.
- **`sync_status_to_marketplace(order_ids)` Method:**
    - This method takes a list of order IDs to process.
    - **Status Mapping:** Define a dictionary that maps Odoo's `sale.order` states to the required status strings for the Cartona API (e.g., `'sale'` -> `'approved'`, `'done'` -> `'delivered'`, `'cancel'` -> `'cancelled'`).
    - For each order, check the `delivered_by` field and apply business rules:
        - If `delivered_by="delivered_by_cartona"` and the new status is not `cancel`, skip this order.
        - If `delivered_by="delivered_by_supplier"`, proceed with any status change.
    - If the change is allowed, find the corresponding Cartona status from the mapping.
    - If a mapping exists, construct the data payload containing the `hashed_id` and the new `status`.
    - Call the `update_order_status` method from the `marketplace.api` service.

##### 5.4.3.2. Status Updates (Cartona -> Odoo via Webhook)

**`controllers/marketplace_webhook.py` High-Level Logic:**

- Create a new controller to handle incoming webhooks from Cartona.
- **`/cartona_integration/webhook/order_status` Endpoint:**
    - This endpoint will receive POST requests from Cartona when order statuses change.
    - **Authentication:** Verify the request comes from Cartona (could use API token verification or IP whitelisting).
    - **Request Processing:**
        - Extract the `hashed_id` and new `status` from the webhook payload.
        - Search for the corresponding `sale.order` in Odoo using the `cartona_id` field.
        - If the order is found, check the `delivered_by` field and apply business rules:
            - If `delivered_by="delivered_by_supplier"`, only allow status changes to `cancel` from Cartona.
            - If `delivered_by="delivered_by_cartona"`, allow any status change from Cartona.
        - If the change is allowed by business rules, update the order's state based on the received status.
        - **Status Mapping:** Define a dictionary that maps Cartona's status strings to Odoo's `sale.order` states (reverse of the Odoo -> Cartona mapping).
        - Log the webhook activity for debugging and audit purposes.
        - Return a success response to acknowledge receipt of the webhook.
    - **Error Handling:** If the order is not found, the status change is not allowed by business rules, or any error occurs, log the issue and return an appropriate error response.

**Security Considerations for Webhook:**
- Implement proper authentication to ensure webhooks come from Cartona.
- Consider rate limiting to prevent abuse.
- Validate the webhook payload structure before processing.

**Business Rules Summary:**
- **`delivered_by="delivered_by_supplier"`:**
  - **Odoo → Cartona:** Can change to any status
  - **Cartona → Odoo:** Can only change to cancel
- **`delivered_by="delivered_by_cartona"`:**
  - **Odoo → Cartona:** Can only change to cancel  
  - **Cartona → Odoo:** Can change to any status

### 5.5. Automation (Cron Jobs)

**`data/cron_data.xml` High-Level Logic:**

Define cron jobs in an XML file to automate the synchronization tasks.
- **Pull New Orders**
    - **Name:** "Cartona: Pull New Orders"
    - **Model:** `sale.order`
    - **Method to Call:** `cron_pull_orders`
    - **Interval:** Set to run every X minutes.
    - **Active:** Should be active by default.
---

This detailed guide should provide all the necessary information to complete the integration successfully. Please follow it carefully.