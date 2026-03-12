from __future__ import annotations

from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "fraud_analytics.db"

TX_PATH = DATA_DIR / "train_transaction.csv"
ID_PATH = DATA_DIR / "train_identity.csv"


def monday_of_week(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series)
    return (dt - pd.to_timedelta(dt.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")


def main() -> None:
    if not TX_PATH.exists() or not ID_PATH.exists():
        raise FileNotFoundError(
            "Place train_transaction.csv and train_identity.csv inside data/ before running this script."
        )

    print("Reading transaction file...")
    tx = pd.read_csv(TX_PATH, low_memory=False)
    print("Reading identity file...")
    identity = pd.read_csv(ID_PATH, low_memory=False)

    base_date = pd.Timestamp("2017-11-30")

    tx = tx.rename(columns={
        "TransactionID": "transaction_id",
        "TransactionDT": "transaction_dt",
        "TransactionAmt": "transaction_amt",
        "ProductCD": "product_cd",
        "P_emaildomain": "p_emaildomain",
        "R_emaildomain": "r_emaildomain",
        "isFraud": "is_fraud",
    })

    tx["event_ts"] = base_date + pd.to_timedelta(tx["transaction_dt"], unit="s")
    tx["event_date"] = tx["event_ts"].dt.strftime("%Y-%m-%d")
    tx["event_week"] = monday_of_week(tx["event_ts"])

    tx_cols = [
        "transaction_id", "event_ts", "event_date", "event_week", "transaction_amt",
        "product_cd", "card1", "card2", "card3", "card4", "card6", "addr1", "addr2",
        "dist1", "dist2", "p_emaildomain", "r_emaildomain", "C1", "C2", "C5", "C13",
        "D1", "D2", "is_fraud"
    ]
    tx = tx[tx_cols].rename(columns={
        "C1": "c1", "C2": "c2", "C5": "c5", "C13": "c13", "D1": "d1", "D2": "d2"
    })
    tx["event_ts"] = pd.to_datetime(tx["event_ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    identity = identity.rename(columns={
        "TransactionID": "transaction_id",
        "DeviceType": "device_type",
        "DeviceInfo": "device_info",
        "id_31": "browser",
        "id_30": "os_name",
    })
    identity = identity[["transaction_id", "device_type", "device_info", "browser", "os_name"]]

    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        print("Writing transactions table...")
        tx.to_sql("transactions", conn, index=False, if_exists="replace")
        print("Writing identity table...")
        identity.to_sql("identity", conn, index=False, if_exists="replace")

        conn.execute("CREATE INDEX idx_transactions_event_date ON transactions(event_date)")
        conn.execute("CREATE INDEX idx_transactions_event_week ON transactions(event_week)")
        conn.execute("CREATE INDEX idx_transactions_product_cd ON transactions(product_cd)")
        conn.execute("CREATE INDEX idx_transactions_card4 ON transactions(card4)")
        conn.execute("CREATE INDEX idx_transactions_is_fraud ON transactions(is_fraud)")
        conn.execute("CREATE INDEX idx_identity_transaction_id ON identity(transaction_id)")

    print(f"Done. Database created at: {DB_PATH}")


if __name__ == "__main__":
    main()
