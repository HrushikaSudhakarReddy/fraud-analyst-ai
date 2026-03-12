from __future__ import annotations

import pandas as pd


def summarize_dataframe(df: pd.DataFrame, question: str) -> str:
    if df.empty:
        return "No rows were returned for this question."

    cols = list(df.columns)
    numeric_cols = list(df.select_dtypes(include=["number"]).columns)
    first = df.iloc[0].to_dict()

    parts = []
    if len(df) == 1:
        bits = [f"{k}={first[k]}" for k in cols[:4]]
        parts.append("Single-row result: " + ", ".join(bits) + ".")
    else:
        anchor_cols = [c for c in cols if c not in numeric_cols][:2] + numeric_cols[:2]
        anchor_cols = anchor_cols[:4]
        bits = [f"{c}={first[c]}" for c in anchor_cols if c in first]
        parts.append("Top row: " + ", ".join(bits) + ".")

    if numeric_cols:
        for c in numeric_cols[:2]:
            series = pd.to_numeric(df[c], errors="coerce").dropna()
            if not series.empty:
                parts.append(f"{c} ranges from {series.min():,.2f} to {series.max():,.2f}.")
                break

    if len(df) > 1:
        parts.append(f"{len(df):,} rows matched the request.")

    return " ".join(parts)
