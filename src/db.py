from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fraud_analytics.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def db_exists() -> bool:
    return DB_PATH.exists()


def run_query(sql: str, params: tuple | None = None) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params or ())


def scalar(sql: str) -> object:
    with get_connection() as conn:
        cur = conn.execute(sql)
        row = cur.fetchone()
        if row is None:
            return None
        return row[0]


def schema_text() -> str:
    schema = """
Table: transactions
- transaction_id INTEGER PRIMARY KEY
- event_ts TEXT
- event_date TEXT
- event_week TEXT
- transaction_amt REAL
- product_cd TEXT
- card1 INTEGER
- card2 REAL
- card3 REAL
- card4 TEXT
- card6 TEXT
- addr1 REAL
- addr2 REAL
- dist1 REAL
- dist2 REAL
- p_emaildomain TEXT
- r_emaildomain TEXT
- c1 REAL
- c2 REAL
- c5 REAL
- c13 REAL
- d1 REAL
- d2 REAL
- is_fraud INTEGER

Table: identity
- transaction_id INTEGER
- device_type TEXT
- device_info TEXT
- browser TEXT
- os_name TEXT

Join:
transactions.transaction_id = identity.transaction_id
"""
    return schema.strip()
