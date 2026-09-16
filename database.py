"""
SQLite data layer for Shopify price monitor.
Stores product snapshots and detects price changes.
"""

import sqlite3
from datetime import datetime
from config import DB_PATH


def get_connection():
    """Create database connection and initialize tables."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            vendor TEXT,
            product_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(store, product_id, created_at)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            variant_title TEXT,
            price REAL NOT NULL,
            compare_at_price REAL,
            available INTEGER,
            snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
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
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
        ON price_snapshots(store, product_id, variant_id, snapshot_at DESC)
    """)
    conn.commit()
    return conn


def get_last_snapshot(conn, store, product_id, variant_id):
    """Get the most recent price for a specific variant."""
    cursor = conn.execute("""
        SELECT price, snapshot_at FROM price_snapshots
        WHERE store = ? AND product_id = ? AND variant_id = ?
        ORDER BY snapshot_at DESC LIMIT 1
    """, (store, product_id, variant_id))
    row = cursor.fetchone()
    if row:
        return {"price": row[0], "snapshot_at": row[1]}
    return None


def save_snapshot(conn, store, product_id, variant_id, variant_title, price, compare_at_price, available):
    """Save a price snapshot for a product variant."""
    conn.execute("""
        INSERT INTO price_snapshots (store, product_id, variant_id, variant_title, price, compare_at_price, available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (store, product_id, variant_id, variant_title, price, compare_at_price, available))


def save_product(conn, store, product_id, title, vendor, product_type):
    """Save or update product metadata."""
    conn.execute("""
        INSERT OR REPLACE INTO products (store, product_id, title, vendor, product_type)
        VALUES (?, ?, ?, ?, ?)
    """, (store, product_id, title, vendor, product_type))


def save_price_change(conn, store, product_id, product_title, variant_title, old_price, new_price, change_pct, direction):
    """Record a detected price change."""
    conn.execute("""
        INSERT INTO price_changes (store, product_id, product_title, variant_title, old_price, new_price, change_pct, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (store, product_id, product_title, variant_title, old_price, new_price, change_pct, direction))


def get_recent_changes(conn, store=None, limit=50):
    """Get recent price changes, optionally filtered by store."""
    if store:
        cursor = conn.execute("""
            SELECT store, product_title, variant_title, old_price, new_price, change_pct, direction, detected_at
            FROM price_changes WHERE store = ?
            ORDER BY detected_at DESC LIMIT ?
        """, (store, limit))
    else:
        cursor = conn.execute("""
            SELECT store, product_title, variant_title, old_price, new_price, change_pct, direction, detected_at
            FROM price_changes ORDER BY detected_at DESC LIMIT ?
        """, (limit,))
    return cursor.fetchall()


def get_stats(conn):
    """Get summary statistics."""
    stats = {}
    cursor = conn.execute("SELECT COUNT(DISTINCT store || '-' || product_id) FROM products")
    stats["total_products"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM price_snapshots")
    stats["total_snapshots"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM price_changes")
    stats["total_changes"] = cursor.fetchone()[0]
    cursor = conn.execute("SELECT store, COUNT(*) FROM products GROUP BY store")
    stats["per_store"] = {row[0]: row[1] for row in cursor.fetchall()}
    return stats
