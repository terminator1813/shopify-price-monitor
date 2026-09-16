# Shopify stores to monitor
# Each entry: (name, base_url)
STORES = [
    ("ColourPop", "https://colourpop.com"),
    ("Allbirds", "https://www.allbirds.com"),
    ("Matt & Nat", "https://mattandnat.com"),
]

# Price change threshold (percentage) to trigger alert
# e.g., 5.0 means alert when price changes by 5% or more
PRICE_CHANGE_THRESHOLD = 5.0

# Telegram bot configuration
# Set these to enable Telegram notifications
TELEGRAM_BOT_TOKEN = ""  # Get from @BotFather
TELEGRAM_CHAT_ID = ""    # Your chat ID (use @userinfobot to find)

# Database path
DB_PATH = "data/prices.db"

# How many products to fetch per store per request (Shopify default max: 250)
PRODUCTS_PER_PAGE = 250

# Max pages to fetch per store (to avoid excessive requests)
MAX_PAGES = 2
