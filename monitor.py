"""Collect public Shopify catalogues and record variant price changes."""

import argparse
from contextlib import closing
from dataclasses import dataclass
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from analytics import discount_pct
from config import MAX_PAGES, PRICE_CHANGE_THRESHOLD, PRODUCTS_PER_PAGE, STORES
from database import (
    get_connection, get_last_snapshot, get_recent_changes, get_stats,
    save_price_change, save_product, save_run, save_snapshot,
)
from telegram_bot import send_alert, send_summary


@dataclass
class FetchResult:
    products: list
    status: str  # success, partial, or failed
    pages: int
    error: str = ""


def create_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "ShopifyPriceMonitor/1.0 (portfolio research)"})
    retry = Retry(
        total=3, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"], respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_products(session, base_url, page, page_size=PRODUCTS_PER_PAGE):
    url = f"{base_url.rstrip('/')}/products.json"
    response = session.get(url, params={"limit": page_size, "page": page}, timeout=30)
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError(f"Invalid JSON from {url}, page {page}") from exc
    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, list):
        raise ValueError(f"Missing products list from {url}, page {page}")
    return products


def fetch_all_products(session, base_url, max_pages=MAX_PAGES,
                       page_size=PRODUCTS_PER_PAGE, pause=1):
    if max_pages < 1 or not 1 <= page_size <= 250:
        raise ValueError("MAX_PAGES must be >= 1 and PRODUCTS_PER_PAGE must be 1–250")
    products = []
    seen = set()
    pages = 0
    for page in range(1, max_pages + 1):
        try:
            batch = fetch_products(session, base_url, page, page_size)
        except (requests.RequestException, ValueError) as exc:
            return FetchResult(products, "partial" if products else "failed", pages, str(exc))
        pages += 1
        if not batch:
            return FetchResult(products, "success", pages)
        page_ids = [p.get("id") for p in batch if isinstance(p, dict)]
        if len(page_ids) != len(batch) or any(pid is None for pid in page_ids):
            return FetchResult(products, "partial", pages, "Invalid product entry")
        new = [p for p in batch if p["id"] not in seen]
        if not new:
            return FetchResult(products, "partial", pages, "Repeated product page")
        products.extend(new)
        seen.update(p["id"] for p in new)
        if len(batch) < page_size:
            return FetchResult(products, "success", pages)
        if page < max_pages:
            time.sleep(pause)
    # A full final page may have more products after the configured limit.
    return FetchResult(products, "partial", pages, "Page limit reached; catalogue may be incomplete")


def extract_variants(product):
    variants = product.get("variants", [])
    if not isinstance(variants, list):
        raise ValueError("Invalid variants list")
    result = []
    for variant in variants:
        if not isinstance(variant, dict) or "id" not in variant or "price" not in variant:
            raise ValueError("Variant missing id or price")
        try:
            price = float(variant["price"])
            compare = variant.get("compare_at_price")
            compare = float(compare) if compare is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid variant price") from exc
        if price < 0 or (compare is not None and compare < 0):
            raise ValueError("Negative variant price")
        result.append({
            "variant_id": variant["id"],
            "title": variant.get("title") or "Default Title",
            "price": price,
            "compare_at_price": compare,
            "available": int(bool(variant.get("available", False))),
        })
    return result


def check_price_changes(conn, store_name, products, threshold=PRICE_CHANGE_THRESHOLD):
    """Persist a batch atomically and return (changes, run metrics)."""
    changes = []
    metrics = {"products": len(products), "variants": 0, "changes": 0,
               "new_products": 0, "out_of_stock": 0, "discounted": 0}
    with conn:
        for product in products:
            product_id = product["id"]
            title = product["title"]
            variants = extract_variants(product)
            if save_product(conn, store_name, product_id, title,
                            product.get("vendor", ""), product.get("product_type", "")):
                metrics["new_products"] += 1
            for variant in variants:
                metrics["variants"] += 1
                metrics["out_of_stock"] += 1 - variant["available"]
                if discount_pct(variant["price"], variant["compare_at_price"]) > 0:
                    metrics["discounted"] += 1
                last = get_last_snapshot(conn, store_name, product_id, variant["variant_id"])
                if last and last["price"] > 0:
                    pct = 100 * (variant["price"] - last["price"]) / last["price"]
                    if abs(pct) >= threshold:
                        change = {
                            "store": store_name, "product_id": product_id,
                            "product_title": title, "variant_title": variant["title"],
                            "old_price": last["price"], "new_price": variant["price"],
                            "change_pct": pct,
                            "direction": "decrease" if pct < 0 else "increase",
                        }
                        changes.append(change)
                        save_price_change(conn, store_name, product_id, title,
                                          variant["title"], last["price"],
                                          variant["price"], pct, change["direction"])
                save_snapshot(conn, store_name, product_id, variant["variant_id"],
                              variant["title"], variant["price"],
                              variant["compare_at_price"], variant["available"])
    metrics["changes"] = len(changes)
    return changes, metrics


def run_monitor(stores=None, session=None, pause=2):
    stores = STORES if stores is None else stores
    own_session = session is None
    session = session or create_session()
    all_changes = []
    stores_checked = 0
    with closing(get_connection()) as conn:
        for store in stores:
            name, url = store["name"], store["url"]
            result = fetch_all_products(session, url)
            if result.products:
                try:
                    changes, metrics = check_price_changes(conn, name, result.products)
                except (KeyError, TypeError, ValueError) as exc:
                    save_run(conn, name, "failed", error=f"Invalid product data: {exc}")
                    print(f"[{name}] invalid product data: {exc}")
                    continue
                all_changes.extend(changes)
                stores_checked += 1
                save_run(conn, name, result.status, metrics, result.error)
                print(f"[{name}] {result.status}: {metrics['products']} products, "
                      f"{metrics['variants']} variants, {len(changes)} changes")
                currency = store.get("currency") or "currency unverified"
                for change in changes:
                    send_alert(change["product_title"], change["variant_title"],
                               change["old_price"], change["new_price"],
                               change["change_pct"], change["direction"], name,
                               currency=currency)
            else:
                status = result.status if result.status == "failed" else "success"
                save_run(conn, name, status, error=result.error)
                print(f"[{name}] {status}: {result.error or 'no products'}")
            if pause:
                time.sleep(pause)
    send_summary(len(all_changes), stores_checked)
    if own_session:
        session.close()
    return all_changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--changes", action="store_true")
    args = parser.parse_args()
    if args.stats:
        with closing(get_connection()) as conn:
            stats = get_stats(conn)
        print(f"Products: {stats['total_products']}; snapshots: "
              f"{stats['total_snapshots']}; changes: {stats['total_changes']}")
        for store, count in stats["per_store"].items():
            print(f"  {store}: {count} products")
    elif args.changes:
        with closing(get_connection()) as conn:
            rows = get_recent_changes(conn, limit=20)
        for row in rows:
            print(f"{row['detected_at']} {row['store']}: {row['product_title']} "
                  f"{row['old_price']:.2f} -> {row['new_price']:.2f} "
                  f"({row['change_pct']:+.1f}%)")
        if not rows:
            print("No price changes recorded yet.")
    else:
        run_monitor()


if __name__ == "__main__":
    main()
