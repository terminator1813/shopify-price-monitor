"""
Telegram notification helper for price change alerts.
"""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_alert(product_title, variant_title, old_price, new_price, change_pct, direction, store):
    """Send a price change alert via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"  [Telegram not configured] {direction}: {product_title} ({variant_title}) "
              f"${old_price:.2f} → ${new_price:.2f} ({change_pct:+.1f}%)")
        return False

    emoji = "📉" if direction == "decrease" else "📈"
    variant_info = f" ({variant_title})" if variant_title and variant_title != "Default Title" else ""

    message = (
        f"{emoji} **Price {direction}**\n\n"
        f"**Store:** {store}\n"
        f"**Product:** {product_title}{variant_info}\n"
        f"**Old price:** ${old_price:.2f}\n"
        f"**New price:** ${new_price:.2f}\n"
        f"**Change:** {change_pct:+.1f}%"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"  [Telegram] Alert sent: {product_title}")
            return True
        else:
            print(f"  [Telegram] Failed ({response.status_code}): {response.text[:100]}")
            return False
    except Exception as e:
        print(f"  [Telegram] Error: {e}")
        return False


def send_summary(changes_count, stores_checked):
    """Send a summary after monitoring run."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    message = (
        f"📊 **Monitor Run Complete**\n\n"
        f"Stores checked: {stores_checked}\n"
        f"Price changes detected: {changes_count}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass
