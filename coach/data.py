"""Data access layer.

Loads data/transactions.csv if present, otherwise generates synthetic data.

To plug in the official Junction / S-Bank dataset:
  1. Put the file in data/ (CSV or Parquet).
  2. Set env var COACH_DATA=data/<file>.
  3. If its column names differ, edit COLUMN_MAP below (their name -> our name).
     Required: customer_id, date, amount. Strongly recommended: merchant, category.
"""
from __future__ import annotations

import os
import pathlib
from functools import lru_cache

import pandas as pd

from .generate import PERSONAS, generate

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Map dataset column names -> internal names. Extend for the official dataset.
COLUMN_MAP = {
    "booking_date": "date", "transaction_date": "date", "value_date": "date",
    "client_id": "customer_id", "account_id": "customer_id", "user_id": "customer_id",
    "counterparty": "merchant", "counterparty_name": "merchant", "merchant_name": "merchant",
    "mcc_category": "category", "category_name": "category",
    "eur_amount": "amount", "amount_eur": "amount",
}


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: COLUMN_MAP.get(c.lower(), c.lower()) for c in df.columns})
    missing = {"customer_id", "date", "amount"} - set(df.columns)
    if missing:
        raise ValueError(f"dataset is missing required columns: {missing}. Edit COLUMN_MAP in coach/data.py")
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["customer_id"] = df["customer_id"].astype(str)
    for col, default in [("merchant", "Unknown"), ("category", "Other"), ("account", "Main account"),
                         ("source_bank", "S-Pankki"), ("description", "")]:
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default).astype(str)
    if "txn_id" not in df.columns:
        df["txn_id"] = [f"T{i:07d}" for i in range(len(df))]
    return df.sort_values(["customer_id", "date"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def load_all() -> pd.DataFrame:
    path = os.environ.get("COACH_DATA")
    p = pathlib.Path(path) if path else DATA_DIR / "transactions.csv"
    if not p.is_absolute():
        p = ROOT / p
    if p.exists():
        df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
        return _normalise(df)
    df = generate()
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(DATA_DIR / "transactions.csv", index=False)
    return _normalise(df)


def customers() -> list[dict]:
    df = load_all()
    out = []
    for cid in df["customer_id"].unique().tolist():
        meta = PERSONAS.get(cid, {})
        out.append({"id": cid, "name": meta.get("name", cid), "age": meta.get("age"),
                    "city": meta.get("city"), "blurb": meta.get("blurb", "")})
    return out


def customer_df(customer_id: str, include_other_banks: bool = True) -> pd.DataFrame:
    df = load_all()
    df = df[df["customer_id"] == customer_id].copy()
    if not include_other_banks:
        df = df[df["source_bank"].str.startswith("S-Pankki")]
    return df


def today() -> pd.Timestamp:
    """'Now' for the app. Pinned to the last transaction date so demos are stable."""
    override = os.environ.get("COACH_TODAY")
    if override:
        return pd.Timestamp(override)
    return load_all()["date"].max().normalize()
