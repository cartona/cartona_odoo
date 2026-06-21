# Cartona Integration (Odoo 18)

Odoo module for Cartona supplier-integrations API. Products link via **`internal_product_id = str(product.product.id)`** on Cartona. Orders and partners keep **`cartona_id`**.

## Overview

- **Product sync:** variant-only (`product.product`); outbound price/stock via `POST supplier-product/bulk-update`
- **Order sync:** inbound pull + outbound status/line updates
- **Per-warehouse, company-aware:** one `cartona.config` **per warehouse** (`warehouse_id` unique), each with its own API token / Cartona supplier. `company_id` is derived from the warehouse and still drives multi-company record rules and product eligibility.
- **Stock is warehouse-scoped:** the quantity pushed is the variant's **Free to Use in that warehouse** (`free_qty` with `warehouse` context), not company-wide.
- **Trigger routing:** a stock change syncs only the **affected warehouse's** config; a price/product change fans out to **all enabled configs in the company** (same `lst_price` to every supplier).
- **Sync gate:** `cartona.config.is_cartona_sync_enabled` per config (default off)
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

1. **Cartona** menu → opens the configs list (one row per warehouse, scoped to the active company)
2. **Create** a config: pick the **Warehouse** (company auto-fills), set API URL and auth token (Cartona Manager only)
3. **Test Connection**
4. Enable **Enable Cartona Sync** when ready for live sync
5. Use **Open Dashboard**, **Recent Activity**, **Log Details** per config (row buttons or form buttons)

Repeat per warehouse that connects to a separate Cartona supplier account. Each warehouse must have its own token.

## Per-warehouse / multi-company notes

- One `cartona.config` per **warehouse** (`unique(warehouse_id)`); `company_id` is a stored related field from the warehouse.
- A company can have **N warehouses → N configs**, each pushing its own warehouse's stock to its own supplier.
- Stock pushed = `free_qty` evaluated **with the config's warehouse context**.
- Per-config sync state lives on `cartona.product.sync` (one row per variant + config); the same variant gets independent rows per warehouse config.
- The variant **Cartona** tab lists sync rows per configuration (rows appear after the first sync attempt for that config).
- Record rules restrict configs, logs, and product sync rows to allowed companies (via the derived `company_id`).

## Breaking changes (per-warehouse migration, 18.0.2.0.47)

- `cartona.config` now requires `warehouse_id` and is unique per warehouse (the old `unique(company_id)` is dropped).
- Resolver API: `get_for_company()` / `require_for_company()` are replaced by `get_for_warehouse()` / `require_for_warehouse()` (stock) and `enabled_configs_for_company()` (price/product fan-out).
- Stock numbers sent to Cartona change from company-wide to warehouse-scoped. For a company whose stock is concentrated in one warehouse, the value is unchanged once that config is mapped to the stock-holding warehouse.
- The top-level **Overview / Recent Activity / Log Details** menus are gone; these are now per-config actions reached from the configs list or the config form.
- `post_init_hook` no longer auto-creates a placeholder config (a config now needs a warehouse). Managers create configs from the list.

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

Version **18.0.2.0.33** cleans stale product views referencing removed `cartona_id` / `cartona_sync_*` fields before upgrade.

Version **18.0.2.0.39** removes marketplace-era cron, groups, ACL duplicates, orphan wizard table, and legacy `product_product.cartona_sync_*` columns.

Version **18.0.2.0.47** moves config scoping from per-company to **per-warehouse**. The pre-migrate adds `cartona_config.warehouse_id`, backfills each config to the warehouse holding its stock (most `stock_quant` rows; falls back to the company's first warehouse; leaves NULL only for a warehouse-less company), and drops `company_uniq`. `NOT NULL` + `warehouse_uniq` are then applied by the ORM (Odoo logs and continues for any residual NULL). Idempotent and a no-op on a DB with no configs.

### Prod rollout checklist (18.0.2.0.47)

1. **Test locally first** (fresh install, two-step migration upgrade, multi-warehouse routing).
2. Pre-deploy: confirm the existing prod config should map to its **stock-holding warehouse** (e.g. `SB2B`), and document the warehouse ↔ supplier token mapping for any extra warehouses.
3. Deploy + upgrade; verify `cartona_config.warehouse_id` is set to the stock-holding warehouse before re-enabling sync.
4. Create additional configs + tokens for other warehouses from the configs list.
5. Run **Sync All Variants** per warehouse config.
6. Verify Cartona stock per supplier matches Odoo warehouse `free_qty`.
7. Monitor order pull per config (no duplicate orders when tokens are supplier-distinct).

## Architecture

| Direction | Trigger | API |
|---|---|---|
| Cartona → Odoo orders | Cron + manual pull | `GET order/pull-orders` |
| Odoo → Cartona price | Variant `lst_price` write (fan-out to all company configs) | `POST supplier-product/bulk-update` |
| Odoo → Cartona stock | Stock move/quant (only the affected warehouse's config) | `POST supplier-product/bulk-update` |
| Odoo → Cartona status | SO state change / delivery validate | `POST order/update-order-status/:id` |
| Odoo → Cartona lines | SO line create/write/unlink | `POST order/update-order-details` |

**Emergency stop:** set `is_cartona_sync_enabled = False` on the warehouse config (or all of them).

## Troubleshooting

- **Overview / logs:** Cartona → open a config → Open Dashboard / Recent Activity / Log Details
- **queue_job:** Settings → Technical → Queue Jobs (requires debug mode)
- **Connection errors:** verify token and `api_base_url` trailing slash
- **Order pull rejects lines:** ensure `internal_product_id` is set on Cartona and variant exists in Odoo for that company
