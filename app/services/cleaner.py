"""Step a) Data cleaning.

Normalise dates to ISO 8601, strip currency symbols, uppercase status,
fill missing categories, remove exact duplicate rows.
"""
import io

import pandas as pd

EXPECTED_COLUMNS = [
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
    "notes",
]


def _parse_date(value: str) -> str | None:
    """Mixed formats -> ISO YYYY-MM-DD. Returns None if unparseable."""
    if not value or pd.isna(value):
        return None
    raw = str(value).strip()
    for fmt in ("%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return pd.to_datetime(raw, format=fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    # last resort: let pandas guess (dayfirst for DD-MM ambiguity)
    parsed = pd.to_datetime(raw, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _parse_amount(value) -> float:
    """Strip $ and commas -> float. 0.0 if unparseable."""
    if value is None or pd.isna(value):
        return 0.0
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def clean_csv(raw_bytes: bytes) -> tuple[list[dict], int, int]:
    """Returns (clean_rows, row_count_raw, row_count_clean)."""
    df = pd.read_csv(io.BytesIO(raw_bytes), dtype=str, keep_default_na=False)
    row_count_raw = len(df)

    # Remove exact duplicate rows (all columns identical).
    df = df.drop_duplicates(keep="first").reset_index(drop=True)

    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "txn_id": (r.get("txn_id") or "").strip() or None,
                "date": _parse_date(r.get("date")),
                "merchant": (r.get("merchant") or "").strip() or None,
                "amount": _parse_amount(r.get("amount")),
                "currency": (r.get("currency") or "").strip().upper() or None,
                "status": (r.get("status") or "").strip().upper() or None,
                "category": (r.get("category") or "").strip() or "Uncategorised",
                "account_id": (r.get("account_id") or "").strip() or None,
                "notes": (r.get("notes") or "").strip() or None,
            }
        )

    return rows, row_count_raw, len(rows)
