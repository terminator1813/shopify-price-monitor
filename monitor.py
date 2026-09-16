"""
Shopify Competitor Price Monitor

Fetches product data from Shopify stores via /products.json,
compares prices against historical snapshots, and sends alerts
when prices change beyond the configured threshold.

Usage:
    python monitor.py              # Run one monitoring cycle
    python monitor.py --stats      # Show database statistics
    python monitor.py --changes    # Show recent price changes
"""

import sys
import json
import time
import requests
from datetime import datetime

from config import STORES, PRICE_CHANGE_THRESHOLD, PRODUCTS_PER_PAGE, MAX_PAGES
from database import (
    get_connection, get_last_snapshot, save_snapshot,
    save_product, save_price_change, get_recent_changes, get_stats
)
from telegram_bot import send_alert, send_summary


def fetch_products(base_url, page=1):
    """Fetch a page of products from a Shopify store's /products.json endpoint."""
    url = f"{base_url}/products.json"
    params = {"limit": PRODUCTS_PER_PAGE, "page": page}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("products", [])
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return []


def fetch_all_products(base_url):
    """Fetch all products from a store (up to MAX_PAGES)."""
    all_products = []
    for page in range(1, MAX_PAGES + 1):
        products = fetch_products(base_url, page)
        if not products:
            break
        all_products.extend(products)
        print(f"  Page {page}: {len(products)} products")
        if len(products) < PRODUCTS_PER_PAGE:
            break
        time.sleep(1)  # Be polite to the server
    return all_products


def extract_variants(product):
    """Extract variant information from a Shopify product."""
    variants = []
    for v in product.get("variants", []):
        variants.append({
            "variant_id": v["id"],
            "title": v.get("title", "Default Title"),
            "price": float(v["price"]),
            "compare_at_price": float(v["compare_at_price"]) if v.get("compare_at_price") else None,
            "available": int(v.get("available", False)),
        })
    return variants


def check_price_changes(conn, store_name, products):
    """Compare current prices against last snapshot and detect changes."""
    changes = []

    for product in products:
        product_id = product["id"]
        title = product["title"]
        vendor = product.get("vendor", "")
        product_type = product.get("product_type", "")

        # Save product metadata
        save_product(conn, store_name, product_id, title, vendor, product_type)

        # Check each variant
        variants = extract_variants(product)
        for variant in variants:
            last = get_last_snapshot(conn, store_name, product_id, variant["variant_id"])

            if last:
                old_price = last["price"]
                new_price = variant["price"]

                if old_price > 0:
                    change_pct = ((new_price - old_price) / old_price) * 100

                    if abs(change_pct) >= PRICE_CHANGE_THRESHOLD:
                        direction = "decrease" if change_pct < 0 else "increase"
                        changes.append({
                            "store": store_name,
                            "product_id": product_id,
                            "product_title": title,
                            "variant_title": variant["title"],
                            "old_price": old_price,
                            "new_price": new_price,
                            "change_pct": change_pct,
                            "direction": direction,
                        })

                        save_price_change(
                            conn, store_name, product_id, title,
                            variant["title"], old_price, new_price,
                            change_pct, direction
                        )

            # Save current snapshot
            save_snapshot(
                conn, store_name, product_id,
                variant["variant_id"], variant["title"],
                variant["price"], variant["compare_at_price"],
                variant["available"]
            )

    conn.commit()
    return changes


def run_monitor():
    """Main monitoring loop."""
    print(f"\n{'='*60}")
    print(f"Shopify Price Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    conn = get_connection()
    all_changes = []
    stores_checked = 0

    for store_name, base_url in STORES:
        print(f"\n[{store_name}] Fetching products from {base_url}...")
        products = fetch_all_products(base_url)

        if not products:
            print(f"  No products found or fetch failed.")
            continue

        print(f"  Found {len(products)} products total")
        changes = check_price_changes(conn, store_name, products)

        if changes:
            print(f"  ⚠ {len(changes)} price changes detected!")
            for c in changes:
                emoji = "📉" if c["direction"] == "decrease" else "📈"
                print(f"    {emoji} {c['product_title']} ({c['variant_title']}): "
                      f"${c['old_price']:.2f} → ${c['new_price']:.2f} ({c['change_pct']:+.1f}%)")
                send_alert(
                    c["product_title"], c["variant_title"],
                    c["old_price"], c["new_price"],
                    c["change_pct"], c["direction"], store_name
                )
        else:
            print(f"  ✓ No significant price changes")

        all_changes.extend(changes)
        stores_checked += 1
        time.sleep(2)  # Delay between stores

    send_summary(len(all_changes), stores_checked)

    print(f"\n{'='*60}")
    print(f"Done. Stores: {stores_checked}, Changes: {len(all_changes)}")
    print(f"{'='*60}\n")

    conn.close()
    return all_changes


def show_stats():
    """Display database statistics."""
    conn = get_connection()
    stats = get_stats(conn)
    print(f"\nDatabase Statistics:")
    print(f"  Total products tracked: {stats['total_products']}")
    print(f"  Total price snapshots:  {stats['total_snapshots']}")
    print(f"  Total price changes:    {stats['total_changes']}")
    print(f"\n  Per store:")
    for store, count in stats["per_store"].items():
        print(f"    {store}: {count} products")
    conn.close()


def show_changes():
    """Display recent price changes."""
    conn = get_connection()
    changes = get_recent_changes(conn, limit=20)
    if not changes:
        print("\nNo price changes recorded yet.")
        conn.close()
        return

    print(f"\nRecent Price Changes (last 20):")
    print(f"{'Store':<15} {'Product':<35} {'Variant':<15} {'Old':>8} {'New':>8} {'Change':>8} {'Dir':<10}")
    print("-" * 100)
    for row in changes:
        store, title, variant, old, new, pct, direction, detected = row
        variant = variant if variant and variant != "Default Title" else "-"
        title = title[:32] + "..." if len(title) > 35 else title
        print(f"{store:<15} {title:<35} {variant:<15} ${old:>7.2f} ${new:>7.2f} {pct:>+7.1f}% {direction}")
    conn.close()


if __name__ == "__main__":
    if "--stats" in sys.argv:
        show_stats()
    elif "--changes" in sys.argv:
        show_changes()
    else:
        run_monitor()
