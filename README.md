# Cartona Marketplace Integration

> **Compatible with Odoo 18.0**

## Purpose

This module integrates the Cartona B2B marketplace with Odoo Sales and Inventory modules, enabling suppliers to automatically sync products, manage inventory, and process orders seamlessly between their Odoo system and multiple marketplace platforms.

## Core Features

### 🔗 **Multi-Marketplace Integration**
- **Universal Support**: Connect to Cartona, Amazon, eBay, Shopify, and other REST API marketplaces
- **Bearer Token Authentication**: Standardized authentication across platforms
- **Single Configuration**: Manage multiple marketplaces from one interface

### 📦 **Product & Inventory Management**
- **Real-time Sync**: Automatic price and stock updates (<5 seconds)
- **Universal Product ID**: Single `cartona_id` field for all marketplace integrations
- **Multi-warehouse Support**: Sync inventory across multiple locations
- **Bulk Operations**: Efficient batch processing for large catalogs

### 📋 **Order Processing**
- **Automatic Order Pull**: Import orders from marketplaces every 15 minutes
- **Customer Auto-creation**: Automatically create customer records from marketplace orders
- **Bidirectional Status Sync**: Order status updates flow between Odoo and marketplaces
- **Complete Order Details**: Preserve all order information and line items

### 🎛️ **Seamless User Experience**
- **Extend Existing Views**: No duplicate interfaces - work within familiar Odoo screens
- **Minimal New Views**: Only 2 new screens (Configuration + Monitoring Dashboard)
- **Queue-based Processing**: Reliable background processing with error handling
- **Comprehensive Logging**: Monitor all operations with detailed sync logs

## Supported Odoo Version

- **Odoo 18.0** (Primary)
- Designed for future compatibility with Odoo 15.0+, 16.0+, 17.0+

## Dependencies

### Required Modules
- `base` - Core Odoo functionality
- `sale_management` - Sales order processing
- `stock` - Inventory management
- `product` - Product catalog
- `purchase` - Purchase operations
- `queue_job` - Asynchronous background processing

### External Dependencies
- **Python Libraries**: `requests` (for API communication)

## Installation Steps

1. **Prerequisites Check**:
   ```bash
   # Ensure queue_job module is installed
   # Verify Python requests library is available
   pip install requests
   ```

2. **Install Module**:
   ```bash
   # Copy module to your Odoo addons directory
   cp -r cartona_integration /path/to/odoo/addons/
   
   # Restart Odoo service
   sudo systemctl restart odoo
   ```

3. **Activate Module**:
   - Go to **Apps** → **Update Apps List**
   - Search for "**Cartona**"
   - Click **Install**

4. **Configure Integration**:
   - Navigate to **Cartona** → **Configuration**
   - Enter your marketplace API credentials
   - Test connection and enable auto-sync options

## Basic Usage

### Quick Start
1. **Setup Marketplace Connection**:
   - Go to **Cartona** → **Configuration**
   - Enter API Base URL and Authentication Token
   - Click **Test Connection** to verify

2. **Configure Products**:
   - Open any product in **Sales** → **Products**
   - Set **External Product ID** (cartona_id)
   - Enable **Marketplace Sync**

3. **Monitor Operations**:
   - Check **Cartona** → **Monitoring** for sync status
   - Review logs for any errors or warnings
   - View statistics on synced products and pulled orders

### Automated Operations
- **Product Sync**: Price and stock changes sync automatically within 5 seconds
- **Order Import**: New orders pulled every 15 minutes
- **Status Updates**: Order status changes sync bidirectionally
- **Customer Creation**: New customers created automatically from orders

## Architecture

### Integration Model
- **One Odoo Instance = One Supplier**
- **Direct Connection**: Supplier's Odoo ↔ Marketplace Platform
- **Universal Field Strategy**: Single `cartona_id` field works across all marketplaces

### Processing Flow
1. **Products**: Changes trigger real-time API calls to update marketplace
2. **Orders**: Background jobs pull orders and create Odoo sales orders
3. **Customers**: Auto-created with `retailer_` prefix in cartona_id field
4. **Status Sync**: Bidirectional updates maintain consistency

## Contact / Maintainer Info

- **Author**: Cartona Integration Team
- **Website**: [https://cartona.com](https://cartona.com)
- **License**: LGPL-3
- **Version**: 18.0.1.0.0

### Support
- **Documentation**: Check module views for built-in help text
- **Logs**: Review **Cartona** → **Monitoring** for troubleshooting
- **Configuration**: Use **Test Connection** feature to verify setup

---

**Ready for Production**: This module includes comprehensive error handling, logging, and monitoring capabilities for immediate deployment in production environments.
