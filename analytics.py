"""Simple, interpretable commerce metrics."""


def discount_pct(price, compare_at_price):
    """Return the advertised markdown; zero if there is no valid reference price."""
    if compare_at_price is None or compare_at_price <= 0 or price >= compare_at_price:
        return 0.0
    return 100 * (compare_at_price - price) / compare_at_price
