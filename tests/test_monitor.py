import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics import discount_pct
from database import get_connection, get_stats
from monitor import check_price_changes, fetch_all_products


def product(price="10.00", product_id=1, variant_id=10):
    return {
        "id": product_id, "title": "Demo shirt", "vendor": "Demo",
        "product_type": "Apparel",
        "variants": [{"id": variant_id, "title": "Blue", "price": price,
                      "compare_at_price": "20.00", "available": False}],
    }


class FakeSession:
    def __init__(self, pages):
        self.pages = pages

    def get(self, _url, params, timeout):
        page = params["page"]
        response = type("Response", (), {})()
        response.raise_for_status = lambda: None
        response.json = lambda: {"products": self.pages.get(page, [])}
        return response


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "nested", "prices.db")
        self.conn = get_connection(self.path)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_first_scan_and_price_change(self):
        changes, first = check_price_changes(self.conn, "Demo", [product()])
        self.assertEqual(changes, [])
        self.assertEqual(first["new_products"], 1)
        self.assertEqual(first["discounted"], 1)
        self.assertEqual(first["out_of_stock"], 1)
        changes, second = check_price_changes(self.conn, "Demo", [product("8.00")])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change_pct"], -20.0)
        self.assertEqual(second["new_products"], 0)
        self.assertEqual(get_stats(self.conn)["total_products"], 1)

    def test_invalid_batch_rolls_back(self):
        with self.assertRaises(ValueError):
            check_price_changes(self.conn, "Demo", [product(), product("bad", 2, 20)])
        self.assertEqual(get_stats(self.conn)["total_products"], 0)

    def test_page_limit_is_reported_as_partial(self):
        session = FakeSession({1: [product()], 2: [product(product_id=2)]})
        with patch("monitor.time.sleep"):
            result = fetch_all_products(session, "https://example.com", 2, 1)
        self.assertEqual(result.status, "partial")
        self.assertEqual(len(result.products), 2)

    def test_repeated_page_is_reported(self):
        session = FakeSession({1: [product()], 2: [product()]})
        with patch("monitor.time.sleep"):
            result = fetch_all_products(session, "https://example.com", 2, 1)
        self.assertEqual(result.status, "partial")
        self.assertEqual(len(result.products), 1)

    def test_invalid_json_is_failed(self):
        session = FakeSession({})
        session.get = lambda *_args, **_kwargs: type(
            "Response", (), {"raise_for_status": lambda self: None,
                             "json": lambda self: (_ for _ in ()).throw(ValueError())}
        )()
        result = fetch_all_products(session, "https://example.com", 2, 1)
        self.assertEqual(result.status, "failed")

    def test_discount_metric(self):
        self.assertEqual(discount_pct(8, 10), 20.0)
        self.assertEqual(discount_pct(10, None), 0.0)
        self.assertEqual(discount_pct(10, 8), 0.0)


class MigrationTests(unittest.TestCase):
    def test_legacy_duplicate_products_are_consolidated(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "legacy.db")
            conn = sqlite3.connect(path)
            conn.execute("""
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    store TEXT NOT NULL, product_id INTEGER NOT NULL,
                    title TEXT NOT NULL, vendor TEXT, product_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(store, product_id, created_at)
                )
            """)
            conn.execute("INSERT INTO products(store, product_id, title, created_at) VALUES ('Demo', 1, 'Old', '2025-01-01')")
            conn.execute("INSERT INTO products(store, product_id, title, created_at) VALUES ('Demo', 1, 'New', '2025-01-02')")
            conn.commit()
            conn.close()
            upgraded = get_connection(path)
            self.assertEqual(get_stats(upgraded)["total_products"], 1)
            self.assertEqual(upgraded.execute("SELECT title FROM products").fetchone()[0], "New")
            upgraded.close()


if __name__ == "__main__":
    unittest.main()
