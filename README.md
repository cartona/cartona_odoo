# Cartona Marketplace Integration

Universal marketplace integration module for Odoo suppliers to connect with Cartona, Amazon, eBay, Shopify, and other marketplaces.

## Overview

This module enables suppliers to:
- Connect their Odoo system to multiple marketplace platforms
- Sync products, prices, and stock in real-time
- Pull orders automatically from marketplaces  
- Manage customer data from marketplace orders
- Monitor synchronization status and errors

## Key Features

### 🔗 Universal Integration
- **Multi-Marketplace Support**: Cartona, Amazon, eBay, Shopify, and more
- **Generic API Client**: Works with any REST API marketplace
- **Bearer Token Authentication**: Standardized authentication method
- **Flexible Configuration**: Each marketplace has independent settings

### 📦 Product Management
- **Universal External ID**: Single `cartona_id` field for all marketplaces
- **Real-time Price Sync**: Automatic price updates (<5 seconds)
- **Stock Synchronization**: Multi-warehouse inventory sync
- **Product Matching**: Reliable product identification across platforms

### 📋 Order Management
- **Automatic Order Pull**: Webhook-based order processing
- **Customer Creation**: Auto-create customers from marketplace orders
- **Status Synchronization**: Bidirectional order status updates
- **Order Line Details**: Complete order information preservation

### 🎛️ Minimal UI Approach
- **Extend Existing Views**: No duplicate product/order management
- **Familiar Interface**: Users work in standard Odoo screens
- **Only 2 New Views**: Configuration and monitoring dashboard
- **Seamless Integration**: Marketplace features blend naturally

## Architecture

### Integration Model
- **One Odoo Instance = One Supplier**
- **Direct Connection**: Supplier's Odoo ↔ Marketplace Platform
- **Independent Operation**: Each supplier manages their own integration

### Field Strategy
- **Products**: `cartona_id` field stores external product ID
- **Partners**: `cartona_id` field with `retailer_` prefix for customers
- **Orders**: `cartona_id` field for external order matching

## Installation

1. **Prerequisites**: 
   - Odoo 15.0+, 16.0+, or 17.0+
   - `queue_job` module installed
   - Python `requests` library

2. **Install Module**:
   ```bash
   # Copy module to addons directory
   cp -r cartona_integration /path/to/odoo/addons/
   
   # Update app list and install
   # Go to Apps > Update Apps List > Search "Cartona" > Install
   ```

3. **Configure Marketplace**:
   - Navigate to Marketplace Integration > Configuration > Marketplaces
   - Create new marketplace configuration
   - Enter API credentials and test connection

## Configuration

### Basic Setup
1. **Marketplace Configuration**:
   - Name: Display name (e.g., "Cartona", "Amazon")
   - API Base URL: Marketplace API endpoint
   - Auth Token: Bearer token from marketplace
   - Enable auto-sync options as needed

2. **Product Setup**:
   - Set `External Product ID` on products you want to sync
   - Enable marketplace sync on products
   - Products sync automatically on price/stock changes

3. **Order Processing**:
   - Configure webhook endpoint: `/marketplace_integration/webhook/orders`
   - Orders import automatically every 15 minutes
   - Customer records created automatically

### Webhook Configuration
Configure your marketplace to send webhooks to:
- **Orders**: `https://your-odoo-domain.com/marketplace_integration/webhook/orders`
- **Status Updates**: `https://your-odoo-domain.com/marketplace_integration/webhook/status`
- **Test**: `https://your-odoo-domain.com/marketplace_integration/webhook/test`

## Usage

### Product Synchronization
1. **Set External Product ID**: Add `cartona_id` to products you want to sync
2. **Enable Sync**: Check "Enable Marketplace Sync" on product
3. **Automatic Sync**: Price and stock changes sync automatically
4. **Manual Sync**: Use "Manual Sync" button when needed

### Order Management
1. **Automatic Pull**: Orders import automatically from webhooks
2. **Customer Creation**: Customers created automatically from order data
3. **Status Updates**: Order statuses sync bidirectionally
4. **Order Processing**: Use standard Odoo sales order workflow

### Monitoring
1. **Dashboard**: View sync status for all marketplaces
2. **Sync Logs**: Monitor operations and troubleshoot errors
3. **Connection Testing**: Test API connections anytime
4. **Statistics**: Track products synced and orders pulled

## API Integration

### Supported Marketplaces

#### Cartona
- **Base URL**: `https://supplier-integrations.cartona.com/api/v1/`
- **Auth Header**: `AuthorizationToken`
- **Token Format**: Bearer token

#### Amazon (Example)
- **Base URL**: `https://sellingpartnerapi.amazon.com/v1/`
- **Auth Header**: `Authorization`
- **Token Format**: Bearer token

#### Generic REST API
- Any marketplace with REST API and bearer token authentication
- Configurable endpoints and headers
- Standard HTTP methods (GET, POST, PUT, DELETE)

### Key Endpoints
- `GET /supplier-product` - List products
- `POST /supplier-product/bulk-update` - Update products
- `POST /supplier-product/bulk-update-stock` - Update stock
- `GET /order/pull-orders` - Pull orders
- `POST /order/update-order-status` - Update order status

## Troubleshooting

### Connection Issues
1. **Verify API URL**: Ensure base URL is correct and accessible
2. **Check Token**: Verify authentication token is valid
3. **Test Connection**: Use "Test Connection" button in configuration
4. **Review Logs**: Check sync logs for detailed error messages

### Sync Problems
1. **Missing External IDs**: Ensure products have `cartona_id` set
2. **Disabled Sync**: Check "Enable Marketplace Sync" is enabled
3. **Queue Jobs**: Verify queue job worker is running
4. **API Limits**: Check if API rate limits are being hit

### Common Errors
- **"Missing external ID"**: Set `cartona_id` on products/partners
- **"Connection timeout"**: Increase timeout setting or check network
- **"Invalid token"**: Verify authentication token with marketplace
- **"Product not found"**: Ensure product exists in marketplace catalog

## Development

### Module Structure
```
cartona_integration/
├── models/           # Data models and business logic
├── views/            # UI extensions and new views
├── controllers/      # Webhook endpoints
├── security/         # Access rights and security
├── data/             # Default data and configurations
└── demo/             # Demo data for testing
```

### Key Models
- `marketplace.config`: Marketplace configurations
- `marketplace.api`: Generic API client
- `marketplace.order.processor`: Order processing logic
- `marketplace.sync.log`: Operation logging

### Extending the Module
1. **New Marketplace**: Add configuration in `marketplace.config`
2. **Custom API**: Override methods in `marketplace.api`
3. **Data Mapping**: Customize `_prepare_product_data()` methods
4. **UI Extensions**: Add fields to existing view extensions

## Support

### Documentation
- Technical docs: `/path/to/module/docs/`
- API reference: Check sync logs for request/response examples
- Configuration guide: Built-in help text in forms

### Getting Help
1. **Check Logs**: Review marketplace sync logs first
2. **Test Connection**: Verify API connectivity
3. **Configuration**: Double-check marketplace settings
4. **Odoo Logs**: Check Odoo server logs for detailed errors

## License

This module is licensed under LGPL-3.

## Version History

- **v17.0.1.0.0**: Initial release with universal marketplace support
  - Multi-marketplace configuration
  - Real-time sync capabilities  
  - Webhook-based order pull
  - Minimal UI architecture
  - Queue-based processing

---

**Ready for Production**: This module is designed for immediate deployment with comprehensive error handling, logging, and monitoring capabilities.
