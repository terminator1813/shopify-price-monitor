"""Launch with: streamlit run dashboard.py"""

import os
from contextlib import closing

import pandas as pd
import streamlit as st

from config import DB_PATH, STORES
from database import get_connection


st.set_page_config(page_title="Shopify Competitive Intelligence", layout="wide")
st.title("Shopify Competitive Intelligence")
st.caption("Public storefront observations. Prices are shown in each store's storefront currency.")

if not os.path.exists(DB_PATH):
    st.info("No data yet. Run `python3 monitor.py` first.")
    st.stop()

with closing(get_connection()) as conn:
    products = pd.read_sql_query("SELECT store, product_id, title, vendor, product_type FROM products", conn)
    latest = pd.read_sql_query("""
        SELECT s.store, s.product_id, s.variant_id, s.variant_title,
               s.price, s.compare_at_price, s.available, s.snapshot_at
        FROM price_snapshots s
        WHERE s.id = (
            SELECT MAX(t.id) FROM price_snapshots t
            WHERE t.store = s.store AND t.product_id = s.product_id
              AND t.variant_id = s.variant_id
        )
    """, conn)
    changes = pd.read_sql_query("""
        SELECT store, product_title, variant_title, old_price, new_price,
               change_pct, direction, detected_at
        FROM price_changes ORDER BY id DESC LIMIT 100
    """, conn)
    runs = pd.read_sql_query("""
        SELECT store, status, products, variants, changes, new_products,
               out_of_stock, discounted, error, ran_at
        FROM monitor_runs ORDER BY id DESC LIMIT 100
    """, conn)

if latest.empty:
    st.info("No price snapshots yet. Run `python3 monitor.py` first.")
    st.stop()

store_names = sorted(latest["store"].unique())
selected = st.selectbox("Store", store_names)
currency = next((s.get("currency") for s in STORES if s["name"] == selected), None)
st.caption(f"Currency: {currency or 'unverified'} — do not compare raw prices across stores with different currencies.")

view = latest[latest["store"] == selected].merge(
    products, on=["store", "product_id"], how="left",
)
view["discount_pct"] = (
    (view["compare_at_price"] - view["price"]) / view["compare_at_price"] * 100
).where(view["compare_at_price"] > view["price"], 0).fillna(0)

cols = st.columns(5)
cols[0].metric("Products", view["product_id"].nunique())
cols[1].metric("Variants", len(view))
cols[2].metric("Median price", f"{view['price'].median():.2f}")
cols[3].metric("Discounted", f"{(view['discount_pct'] > 0).mean():.1%}")
cols[4].metric("Out of stock", f"{(view['available'] == 0).mean():.1%}")

st.subheader("Price distribution")
price_bands = pd.cut(view["price"], bins=10, duplicates="drop").astype(str)
distribution = price_bands.value_counts(sort=False).rename_axis("Price range").reset_index(name="Variants")
st.bar_chart(distribution, x="Price range", y="Variants")

st.subheader("Current product and promotion view")
st.dataframe(view[["title", "vendor", "product_type", "variant_title", "price",
                   "compare_at_price", "discount_pct", "available", "snapshot_at"]],
             width="stretch", hide_index=True)

st.subheader("Recent price changes")
st.dataframe(changes[changes["store"] == selected], width="stretch",
             hide_index=True)

st.subheader("Collection health")
st.dataframe(runs[runs["store"] == selected], width="stretch",
             hide_index=True)
