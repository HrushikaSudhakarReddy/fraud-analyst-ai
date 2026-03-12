from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
import pandas as pd

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from src.db import run_query, schema_text
from src.insights import summarize_dataframe

load_dotenv()

ALLOWED_BASE_TABLES = {"transactions", "identity"}
DISALLOWED_SQL = [
    "insert ",
    "update ",
    "delete ",
    "drop ",
    "alter ",
    "truncate ",
    "attach ",
    "detach ",
    "pragma ",
    "create ",
    "replace ",
]


@dataclass
class AgentResult:
    question: str
    sql: str
    dataframe: pd.DataFrame
    summary: str
    mode: str


def extract_cte_names(sql: str) -> set[str]:
    """
    Extract CTE names from queries like:

    WITH daily AS (...),
         rolling AS (...)
    SELECT ...
    """
    normalized = " ".join(sql.strip().lower().split())

    if not normalized.startswith("with"):
        return set()

    cte_names = set()

    # Matches:
    # WITH daily AS (
    # , rolling AS (
    matches = re.findall(r"(?:with|,)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", normalized)
    for name in matches:
        cte_names.add(name)

    return cte_names


def validate_sql(sql: str) -> tuple[bool, str]:
    normalized = " ".join(sql.strip().lower().split())

    if not normalized.startswith(("select", "with")):
        return False, "Only read-only SELECT queries are allowed."

    if ";" in normalized[:-1]:
        return False, "Only one SQL statement can be executed at a time."

    for token in DISALLOWED_SQL:
        if token in normalized:
            return False, f"Blocked token detected: {token.strip()}"

    cte_names = extract_cte_names(sql)

    table_refs = set(
        re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalized)
    )

    if not table_refs:
        return False, "The query does not reference a table."

    allowed_refs = ALLOWED_BASE_TABLES | cte_names
    unknown = table_refs - allowed_refs

    if unknown:
        return False, f"Unknown table reference(s): {', '.join(sorted(unknown))}"

    return True, "ok"


def rule_based_sql(question: str) -> str | None:
    q = question.lower().strip()

    # ------------------------------------------------------------
    # Core baseline questions
    # ------------------------------------------------------------

    if (
        "overall fraud rate" in q
        or "what percentage of all transactions" in q
        or "overall fraud" in q
    ):
        return """
SELECT
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions;
""".strip()

    if (
        ("product" in q or "product code" in q or "product category" in q)
        and "fraud rate" in q
    ):
        return """
SELECT
    product_cd,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY product_cd
HAVING COUNT(*) >= 25
ORDER BY fraud_rate_pct DESC, total_transactions DESC;
""".strip()

    if "card network" in q or "visa" in q or "mastercard" in q:
        return """
SELECT
    COALESCE(card4, 'Unknown') AS card_network,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY COALESCE(card4, 'Unknown')
HAVING COUNT(*) >= 25
ORDER BY fraud_transactions DESC, fraud_rate_pct DESC;
""".strip()

    if "debit" in q or "credit" in q or "funding type" in q:
        return """
SELECT
    COALESCE(card6, 'Unknown') AS funding_type,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY COALESCE(card6, 'Unknown')
HAVING COUNT(*) >= 25
ORDER BY fraud_rate_pct DESC, total_transactions DESC;
""".strip()

    if "email" in q or "domain" in q:
        return """
SELECT
    COALESCE(p_emaildomain, 'Unknown') AS purchaser_email_domain,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY COALESCE(p_emaildomain, 'Unknown')
HAVING COUNT(*) >= 20
ORDER BY fraud_transactions DESC, fraud_rate_pct DESC
LIMIT 20;
""".strip()

    # ------------------------------------------------------------
    # Trend / time questions
    # ------------------------------------------------------------

    if "week over week" in q or "weeks experienced the biggest change" in q or "largest change in fraud rate" in q:
        return """
WITH weekly AS (
    SELECT
        event_week,
        COUNT(*) AS total_transactions,
        SUM(is_fraud) AS fraud_transactions,
        100.0 * SUM(is_fraud) / COUNT(*) AS fraud_rate_pct
    FROM transactions
    GROUP BY event_week
),
comparison AS (
    SELECT
        event_week,
        total_transactions,
        fraud_transactions,
        ROUND(fraud_rate_pct, 2) AS fraud_rate_pct,
        ROUND(
            fraud_rate_pct - LAG(fraud_rate_pct) OVER (ORDER BY event_week),
            2
        ) AS wow_change_pct_points
    FROM weekly
)
SELECT *
FROM comparison
ORDER BY event_week;
""".strip()

    if "7-day" in q or "7 day" in q or "rolling" in q or "smoothed" in q:
        return """
WITH daily AS (
    SELECT
        event_date,
        COUNT(*) AS total_transactions,
        SUM(is_fraud) AS fraud_transactions
    FROM transactions
    GROUP BY event_date
),
rolling AS (
    SELECT
        event_date,
        total_transactions,
        fraud_transactions,
        SUM(total_transactions) OVER (
            ORDER BY event_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_total_transactions,
        SUM(fraud_transactions) OVER (
            ORDER BY event_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_fraud_transactions
    FROM daily
)
SELECT
    event_date,
    total_transactions,
    fraud_transactions,
    ROUND(100.0 * rolling_fraud_transactions / NULLIF(rolling_total_transactions, 0), 2) AS rolling_7d_fraud_rate_pct
FROM rolling
ORDER BY event_date;
""".strip()

    if "weekly" in q or "week by week" in q:
        return """
SELECT
    event_week,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY event_week
ORDER BY event_week;
""".strip()

    if "hour" in q or "time of day" in q:
        return """
SELECT
    strftime('%H', event_ts) AS hour_of_day,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY strftime('%H', event_ts)
ORDER BY hour_of_day;
""".strip()

    if "trend" in q or "by day" in q or "daily" in q:
        return """
SELECT
    event_date,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY event_date
ORDER BY event_date;
""".strip()

    # ------------------------------------------------------------
    # Amount / address / identity questions
    # ------------------------------------------------------------

    if "amount" in q or "range" in q or "band" in q:
        return """
WITH binned AS (
    SELECT
        CASE
            WHEN transaction_amt < 25 THEN '0-24'
            WHEN transaction_amt < 50 THEN '25-49'
            WHEN transaction_amt < 100 THEN '50-99'
            WHEN transaction_amt < 200 THEN '100-199'
            WHEN transaction_amt < 500 THEN '200-499'
            ELSE '500+'
        END AS amount_band,
        is_fraud
    FROM transactions
)
SELECT
    amount_band,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM binned
GROUP BY amount_band
ORDER BY fraud_transactions DESC, fraud_rate_pct DESC;
""".strip()

    if "address" in q or "billing address" in q:
        return """
SELECT
    COALESCE(CAST(addr1 AS TEXT), 'Unknown') AS addr1_segment,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY COALESCE(CAST(addr1 AS TEXT), 'Unknown')
HAVING COUNT(*) >= 30
ORDER BY fraud_rate_pct DESC, fraud_transactions DESC
LIMIT 20;
""".strip()

    if ("browser" in q and "device" in q) or "browser-device" in q or "browser and device" in q:
        return """
SELECT
    COALESCE(i.device_type, 'Unknown') AS device_type,
    COALESCE(i.browser, 'Unknown') AS browser,
    COUNT(*) AS total_transactions,
    SUM(t.is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(t.is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions t
LEFT JOIN identity i
    ON t.transaction_id = i.transaction_id
GROUP BY COALESCE(i.device_type, 'Unknown'), COALESCE(i.browser, 'Unknown')
HAVING COUNT(*) >= 15
ORDER BY fraud_transactions DESC, fraud_rate_pct DESC
LIMIT 25;
""".strip()

    if "device" in q:
        return """
SELECT
    COALESCE(i.device_type, 'Unknown') AS device_type,
    COUNT(*) AS total_transactions,
    SUM(t.is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(t.is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions t
LEFT JOIN identity i
    ON t.transaction_id = i.transaction_id
GROUP BY COALESCE(i.device_type, 'Unknown')
HAVING COUNT(*) >= 15
ORDER BY fraud_rate_pct DESC, fraud_transactions DESC;
""".strip()

    # ------------------------------------------------------------
    # Advanced analytical questions
    # ------------------------------------------------------------

    if "card signatures" in q or "recurring card combinations" in q or "repeat fraud" in q:
        return """
SELECT
    card1,
    card4,
    card6,
    COUNT(*) AS fraud_transactions
FROM transactions
WHERE is_fraud = 1
GROUP BY card1, card4, card6
HAVING COUNT(*) >= 3
ORDER BY fraud_transactions DESC
LIMIT 20;
""".strip()

    if "percentage of total fraud" in q or "share of total fraud" in q or "contribute the most to total fraud" in q:
        return """
WITH product_fraud AS (
    SELECT
        product_cd,
        SUM(is_fraud) AS fraud_transactions
    FROM transactions
    GROUP BY product_cd
),
totals AS (
    SELECT SUM(fraud_transactions) AS total_fraud_transactions
    FROM product_fraud
)
SELECT
    p.product_cd,
    p.fraud_transactions,
    ROUND(100.0 * p.fraud_transactions / t.total_fraud_transactions, 2) AS fraud_share_pct
FROM product_fraud p
CROSS JOIN totals t
ORDER BY fraud_share_pct DESC, p.fraud_transactions DESC;
""".strip()

    if "highest fraud rate each day" in q or "lead fraud rate on each day" in q or "top fraud product categories by day" in q:
        return """
WITH daily_product AS (
    SELECT
        event_date,
        product_cd,
        COUNT(*) AS total_transactions,
        SUM(is_fraud) AS fraud_transactions,
        100.0 * SUM(is_fraud) / COUNT(*) AS fraud_rate_pct
    FROM transactions
    GROUP BY event_date, product_cd
),
ranked AS (
    SELECT
        event_date,
        product_cd,
        total_transactions,
        fraud_transactions,
        ROUND(fraud_rate_pct, 2) AS fraud_rate_pct,
        DENSE_RANK() OVER (
            PARTITION BY event_date
            ORDER BY fraud_rate_pct DESC
        ) AS fraud_rank
    FROM daily_product
    WHERE total_transactions >= 15
)
SELECT *
FROM ranked
WHERE fraud_rank <= 3
ORDER BY event_date, fraud_rank, product_cd;
""".strip()

    if "distance information is missing" in q or "missing distance" in q or "dist1" in q or "dist2" in q:
        return """
WITH flags AS (
    SELECT
        CASE WHEN dist1 IS NULL THEN 'dist1_missing' ELSE 'dist1_present' END AS dist1_flag,
        CASE WHEN dist2 IS NULL THEN 'dist2_missing' ELSE 'dist2_present' END AS dist2_flag,
        is_fraud
    FROM transactions
)
SELECT
    dist1_flag,
    dist2_flag,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM flags
GROUP BY dist1_flag, dist2_flag
ORDER BY fraud_rate_pct DESC, total_transactions DESC;
""".strip()

    return None


def llm_sql(question: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("No OPENAI_API_KEY configured.")

    if OpenAI is None:
        raise RuntimeError("openai package is not installed.")

    client = OpenAI(api_key=api_key)

    system = f"""
You are a senior fraud analyst writing SQLite SQL.
Return JSON with one key: sql

Use only the schema below.
{schema_text()}

Rules:
- SQLite syntax only
- Read-only SQL only
- Start with SELECT or WITH
- Use only transactions and identity
- CTEs are allowed
- Keep results concise and business-relevant
- Prefer grouped analysis unless the user explicitly asks for raw rows
- Use COALESCE where missing values matter
- Do not include markdown fences
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
    )
    content = resp.choices[0].message.content
    payload = json.loads(content)
    return payload["sql"].strip()


def ask(question: str) -> AgentResult:
    sql = None
    mode = "rule-based"

    try:
        sql = llm_sql(question)
        mode = "openai"
    except Exception:
        sql = rule_based_sql(question)

    if not sql:
        raise ValueError(
            "The assistant could not map that question to a supported analysis. "
            "Try a more specific fraud, trend, device, product, amount, share, or missing-data question."
        )

    ok, message = validate_sql(sql)
    if not ok:
        raise ValueError(message)

    df = run_query(sql)
    summary = summarize_dataframe(df, question)

    return AgentResult(
        question=question,
        sql=sql,
        dataframe=df,
        summary=summary,
        mode=mode,
    )