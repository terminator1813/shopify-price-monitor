"""SQLite storage and migration for product history and monitoring runs."""

import sqlite3
from pathlib import Path

from config import DB_PATH


def get_connection(db_path=None):
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            vendor TEXT,
            product_type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(store, product_id, created_at)
        );
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            variant_title TEXT,
            price REAL NOT NULL,
            compare_at_price REAL,
            available INTEGER,
            snapshot_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS price_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            product_title TEXT NOT NULL,
            variant_title TEXT,
            old_price REAL NOT NULL,
            new_price REAL NOT NULL,
            change_pct REAL NOT NULL,
            direction TEXT NOT NULL,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,
            status TEXT NOT NULL,
            products INTEGER NOT NULL DEFAULT 0,
            variants INTEGER NOT NULL DEFAULT 0,
            changes INTEGER NOT NULL DEFAULT 0,
            new_products INTEGER NOT NULL DEFAULT 0,
            out_of_stock INTEGER NOT NULL DEFAULT 0,
            discounted INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            ran_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
            ON price_snapshots(store, product_id, variant_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_changes_recent
            ON price_changes(detected_at DESC, id DESC);
    """)
    # Upgrade old databases while retaining their price history.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN updated_at TEXT")
    conn.execute("""
        DELETE FROM products WHERE id NOT IN (
            SELECT MAX(id) FROM products GROUP BY store, product_id
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_store_id
        ON products(store, product_id)
    """)
    conn.commit()
    return conn


def get_last_snapshot(conn, store, product_id, variant_id):
    row = conn.execute("""
        SELECT price, snapshot_at FROM price_snapshots
        WHERE store = ? AND product_id = ? AND variant_id = ?
        ORDER BY id DESC LIMIT 1
    """, (store, product_id, variant_id)).fetchone()
    return dict(row) if row else None


def save_product(conn, store, product_id, title, vendor, product_type):
    """Upsert metadata and return True only for a newly observed product."""
    existed = conn.execute(
        "SELECT 1 FROM products WHERE store = ? AND product_id = ?",
        (store, product_id),
    ).fetchone() is not None
    conn.execute("""
        INSERT INTO products(store, product_id, title, vendor, product_type, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(store, product_id) DO UPDATE SET
            title=excluded.title, vendor=excluded.vendor,
            product_type=excluded.product_type, updated_at=CURRENT_TIMESTAMP
    """, (store, product_id, title, vendor, product_type))
    return not existed


def save_snapshot(conn, store, product_id, variant_id, variant_title, price,
                  compare_at_price, available):
    conn.execute("""
        INSERT INTO price_snapshots
            (store, product_id, variant_id, variant_title, price,
             compare_at_price, available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (store, product_id, variant_id, variant_title, price,
          compare_at_price, available))


def save_price_change(conn, store, product_id, product_title, variant_title,
                      old_price, new_price, change_pct, direction):
    conn.execute("""
        INSERT INTO price_changes
            (store, product_id, product_title, variant_title, old_price,
             new_price, change_pct, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (store, product_id, product_title, variant_title, old_price,
          new_price, change_pct, direction))


def save_run(conn, store, status, metrics=None, error=None):
    metrics = metrics or {}
    conn.execute("""
        INSERT INTO monitor_runs
            (store, status, products, variants, changes, new_products,
             out_of_stock, discounted, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (store, status, metrics.get("products", 0),
          metrics.get("variants", 0), metrics.get("changes", 0),
          metrics.get("new_products", 0), metrics.get("out_of_stock", 0),
          metrics.get("discounted", 0), error))
    conn.commit()


def get_recent_changes(conn, store=None, limit=50):
    where = "WHERE store = ?" if store else ""
    params = (store, limit) if store else (limit,)
    return conn.execute(f"""
        SELECT store, product_title, variant_title, old_price, new_price,
               change_pct, direction, detected_at
        FROM price_changes {where} ORDER BY id DESC LIMIT ?
    """, params).fetchall()


def get_stats(conn):
    return {
        "total_products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "total_snapshots": conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0],
        "total_changes": conn.execute("SELECT COUNT(*) FROM price_changes").fetchone()[0],
        "per_store": dict(conn.execute(
            "SELECT store, COUNT(*) FROM products GROUP BY store").fetchall()),
    }
