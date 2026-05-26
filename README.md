# Cartona Integration (Odoo 18)

Odoo module for Cartona supplier-integrations API. Products link via **`internal_product_id = str(product.product.id)`** on Cartona. Orders and partners keep **`cartona_id`**.

## Overview

- **Product sync:** variant-only (`product.product`); outbound price/stock via `POST supplier-product/bulk-update`
- **Order sync:** inbound pull + outbound status/line updates
- **Multi-company:** one `cartona.config` per Odoo company, each with its own API token
- **Sync gate:** `cartona.config.is_cartona_sync_enabled` per company (default off)
- **Async jobs:** OCA `queue_job` on channel `cartona` (bundled in `addons/`)

## Prerequisites

- Docker and Docker Compose

## Local development

```bash
cd cartona_odoo
docker compose up
```

First boot creates database `cartona_dev` and installs `queue_job` + `cartona_odoo` (~1–2 min).

Open http://localhost:8069 — login `admin` / `admin`.

Reset database:

```bash
docker compose down -v && docker compose up
```

### Day-to-day

```bash
docker compose logs -f web
docker compose restart web
```

## Configure Cartona

1. Switch to the target company (multi-company installs)
2. **Cartona → Configuration** (creates a config for the active company if none exists)
3. Set API URL and auth token (Cartona Manager only)
4. **Test Connection**
5. Enable **Enable Cartona Sync** when ready for live sync

Repeat for each Odoo company that connects to a separate Cartona supplier account.

## Multi-company notes

- Overview, Recent Activity, and Log Details always reflect the **active company**
- Product sync uses the config for the variant's company (or active company for shared products)
- Per-config sync state lives on `cartona.product.sync` (one row per variant + config); shared variants get independent rows per company
- The variant **Cartona** tab lists sync rows per configuration (rows appear after the first sync attempt for that config)
- Record rules restrict configs, logs, and product sync rows to allowed companies

## Linking products

Each sellable Odoo variant maps to Cartona `ProductSupplier.internal_product_id`:

```
ProductSupplier.internal_product_id = "<odoo variant id>"
```

The variant form **Cartona** tab shows the Internal Product ID (readonly `id`). Bootstrap on Cartona side is out of scope for this module.

## Production install

1. Copy `cartona_odoo/` to your addons directory
2. Extend `addons_path` with `.../cartona_odoo/addons`
3. Install `queue_job`, then `cartona_odoo`
4. Configure API credentials per company; enable sync when ready

Example `addons_path`:

```ini
addons_path = /opt/odoo/addons,/opt/odoo/addons/cartona_odoo/addons,/usr/lib/python3/dist-packages/odoo/addons
```

## Upgrade / migration

```bash
odoo-bin -u cartona_odoo -d <database>
```

Version **18.0.2.0.0** renames `marketplace_*` → `cartona_*` and removes product `cartona_id`. Run on every existing install before enabling sync.

Version **18.0.2.0.31** enables one Cartona config per company (replaces global singleton).

Version **18.0.2.0.32** moves variant sync status from `product.product` to `cartona.product.sync` (per variant and config).

## Architecture

| Direction | Trigger | API |
|---|---|---|
| Cartona → Odoo orders | Cron + manual pull | `GET order/pull-orders` |
| Odoo → Cartona price | Variant `lst_price` write | `POST supplier-product/bulk-update` |
| Odoo → Cartona stock | Stock move/quant | `POST supplier-product/bulk-update` |
| Odoo → Cartona status | SO state change / delivery validate | `POST order/update-order-status/:id` |
| Odoo → Cartona lines | SO line create/write/unlink | `POST order/update-order-details` |

**Emergency stop:** set `is_cartona_sync_enabled = False` on the company's config.

## Troubleshooting

- **Overview / logs:** Cartona → Overview / Recent Activity / Log Details
- **queue_job:** Settings → Technical → Queue Jobs (requires debug mode)
- **Connection errors:** verify token and `api_base_url` trailing slash
- **Order pull rejects lines:** ensure `internal_product_id` is set on Cartona and variant exists in Odoo for that company
