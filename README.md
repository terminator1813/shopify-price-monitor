# Shopify Competitive Intelligence Monitor

Track price, discount, availability and newly observed products across selected Shopify storefronts. Each run records its completeness (`success`, `partial`, or `failed`) so missing data is not mistaken for a quiet market.

This project uses storefronts' public `/products.json` endpoint. Availability and access rules vary by store, so the monitor handles blocked and incomplete responses explicitly. It does not use the authenticated Shopify Admin API.

## What it does

- Collects public product and variant data with retries for transient errors, page de-duplication, and a configurable page limit.
- Stores current product metadata and historical variant prices in SQLite. Existing databases are migrated automatically: duplicate product rows are consolidated while price history remains.
- Flags price changes above a configurable threshold and records new products, discounted variants, out-of-stock variants, and run status.
- Shows per-store product, price, discount and availability views in a Streamlit dashboard; optionally sends Telegram messages.
- Runs automated unit tests on every push and pull request.

## Setup

Python 3.10 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python monitor.py
python monitor.py --stats
python monitor.py --changes
streamlit run dashboard.py
```

Edit `STORES` in `config.py` to select storefronts. Set `currency` only after checking which market the endpoint serves. Raw prices from different currencies must not be compared directly.

Optional environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `PRICE_CHANGE_THRESHOLD` | Alert threshold in percent | `5.0` |
| `PRODUCTS_PER_PAGE` | Products per request, max 250 | `250` |
| `MAX_PAGES` | Maximum pages per store | `2` |
| `SHOPIFY_DB_PATH` | SQLite file location | `data/prices.db` |
| `TELEGRAM_BOT_TOKEN` | Optional bot credential | unset |
| `TELEGRAM_CHAT_ID` | Optional recipient | unset |

For Telegram, set both values in your shell or a private environment manager; do not commit credentials. If unset, the monitor still collects data. The database, environment files and caches are excluded from Git.

## Data and interpretation

Prices are variant prices in the storefront's active market; the dashboard shows the store's configured currency or marks it unverified. Discount depth is `(compare_at_price - price) / compare_at_price`, only when a positive reference price exceeds the current price. "New product" means newly observed by this monitor, not necessarily newly launched by the retailer. A full final page at `MAX_PAGES` is marked `partial` because more catalogue pages might exist. A failed request is recorded separately from an empty catalogue.

The project does not claim to cover every product on a store or infer inventory quantity. `available=false` is used only as an out-of-stock indicator. Pricing and product comparisons should be made within compatible stores, currencies and product categories.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover first scans, threshold changes, atomic rollback on malformed data, incomplete pagination, invalid JSON, discount calculations and migration of legacy duplicate rows.

## Repository map

| File | Role |
| --- | --- |
| `monitor.py` | Collection, validation and command line interface |
| `database.py` | SQLite schema, migration and queries |
| `analytics.py` | Commerce metric definitions |
| `telegram_bot.py` | Optional notification delivery |
| `dashboard.py` | Streamlit data view |
| `tests/` | Unit tests |
| `shopify_price_monitor.ipynb` | Earlier exploratory notebook; the Python modules are the maintained implementation |

## Current scope

One monitoring run is started manually with `python monitor.py`. A scheduled GitHub Actions job would lose its SQLite history between runs unless a durable database is provided, so this repository schedules tests only. A local task scheduler or an external database can be added for continuous collection.
