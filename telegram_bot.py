"""Optional Telegram delivery. Credentials are read from environment variables."""

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def _send(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        # Avoid printing the request URL because it contains the bot token.
        print(f"Telegram delivery failed: {type(exc).__name__}")
        return False


def send_alert(product_title, variant_title, old_price, new_price, change_pct,
               direction, store, currency="currency unverified"):
    message = (
        f"Price {direction}: {store} — {product_title} ({variant_title})\n"
        f"{old_price:.2f} → {new_price:.2f} {currency} ({change_pct:+.1f}%)"
    )
    return _send(message)


def send_summary(changes_count, stores_checked):
    return _send(
        f"Monitor run complete: {stores_checked} stores checked, "
        f"{changes_count} price changes detected."
    )
