# Shopify Competitor Price Monitor

> Portfolio version: Telegram credentials are intentionally blank and local database files are excluded from version control.

Automated price monitoring for Shopify-based e-commerce competitors. Fetches product data via Shopify's `/products.json` API, tracks price changes over time, and sends real-time alerts through Telegram.

## Why Shopify Stores?

Shopify stores expose a public `/products.json` endpoint — no scraping, no HTML parsing, no anti-bot measures. This makes them ideal for competitive price intelligence in cross-border e-commerce.

## Features

- **API-based data collection**: Fetch product catalog from any Shopify store via `/products.json`
- **Price change detection**: Compare current prices against historical snapshots
- **Telegram alerts**: Real-time notifications when prices drop or increase beyond a threshold
- **Multi-store support**: Monitor multiple competitors simultaneously
- **Persistent storage**: SQLite database for price history and change tracking
- **Configurable thresholds**: Set minimum price change percentage for alerts

## Tech Stack

- **Python 3** (requests, pandas, sqlite3)
- **Shopify `/products.json` API** (public, no auth required)
- **Telegram Bot API** for notifications
- **SQLite** for local data persistence

## Project Structure

```
shopify-price-monitor/
├── README.md
├── config.py              # Store URLs, thresholds, Telegram config
├── monitor.py             # Main monitoring script
├── database.py            # SQLite data layer
├── telegram_bot.py        # Telegram notification helper
├── requirements.txt
└── data/
    └── .gitkeep
```

## Quick Start

```bash
pip install -r requirements.txt
# Edit config.py with your store URLs and Telegram bot token
python monitor.py
```

## How It Works

1. Fetches products from configured Shopify stores via `GET /products.json`
2. Compares current prices against the last snapshot in SQLite
3. If any price change exceeds the threshold, sends a Telegram alert
4. Stores the new snapshot for future comparisons

## Use Cases

- **Cross-border e-commerce**: Monitor competitor pricing for fashion/accessories
- **Dynamic pricing research**: Track pricing strategies over time
- **Market intelligence**: Identify sales, promotions, and new product launches

## Course Project

Built as part of cross-border e-commerce research, Monash University BA+FinTech (2026)
