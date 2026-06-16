"""Step b) Anomaly detection.

- Statistical outlier: amount > 3x the account's median.
- Currency mismatch: USD on a domestic-only merchant.
"""
from statistics import median

# Domestic-only India brands. USD on these is suspicious.
DOMESTIC_MERCHANTS = {
    "swiggy",
    "ola",
    "irctc",
    "zomato",
    "jio recharge",
    "bookmyshow",
    "flipkart",
    "hdfc atm",
}


def detect_anomalies(rows: list[dict]) -> None:
    """Mutates each row in place: sets is_anomaly + anomaly_reason."""
    # Median amount per account (over rows with a real amount).
    by_account: dict[str, list[float]] = {}
    for r in rows:
        acc = r.get("account_id")
        if acc and r["amount"] > 0:
            by_account.setdefault(acc, []).append(r["amount"])
    medians = {acc: median(amts) for acc, amts in by_account.items()}

    for r in rows:
        reasons = []

        acc = r.get("account_id")
        med = medians.get(acc)
        if med and r["amount"] > 3 * med:
            reasons.append(f"amount {r['amount']} exceeds 3x account median ({med})")

        merchant = (r.get("merchant") or "").strip().lower()
        if r.get("currency") == "USD" and merchant in DOMESTIC_MERCHANTS:
            reasons.append(f"USD currency on domestic-only merchant '{r['merchant']}'")

        r["is_anomaly"] = bool(reasons)
        r["anomaly_reason"] = "; ".join(reasons) if reasons else None
