"""Configuration for the public storefront monitor."""

import os


# Currency is intentionally unset until the requested storefront market is verified.
STORES = [
    {"name": "ColourPop", "url": "https://colourpop.com", "currency": None},
    {"name": "Allbirds", "url": "https://www.allbirds.com", "currency": None},
    {"name": "Matt & Nat", "url": "https://mattandnat.com", "currency": None},
]

PRICE_CHANGE_THRESHOLD = float(os.getenv("PRICE_CHANGE_THRESHOLD", "5.0"))
DB_PATH = os.getenv("SHOPIFY_DB_PATH", "data/prices.db")
PRODUCTS_PER_PAGE = int(os.getenv("PRODUCTS_PER_PAGE", "250"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "2"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
