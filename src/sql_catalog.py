from __future__ import annotations

# The goal of these queries is not just to retrieve rows, but to reflect
# the kinds of questions a fraud analyst would ask while investigating
# suspicious transaction behavior.
#
# Broadly, these queries fall into three groups:
#
# 1. Foundational
#    - Descriptive summaries of fraud exposure across key dimensions
#    - Mostly built with aggregates, GROUP BY, HAVING, and ORDER BY
#
# 2. Investigative
#    - Pattern-finding queries across time, amount bands, address segments,
#      and identity attributes
#    - Often use CASE WHEN, joins, bucketing, and grouped comparisons
#
# 3. Advanced
#    - More analytical views using CTEs and window functions
#    - Used for rolling metrics, ranking, contribution analysis, and
#      period-over-period comparisons


SQL_QUERIES = [
    {
        "name": "Overall fraud rate",
        "category": "Foundational",
        "question": "What share of all transactions are labeled as fraud?",
        # Purpose:
        # Establish the baseline fraud level in the dataset.
        #
        # What this helps answer:
        # - How large is the dataset overall?
        # - How many transactions are fraud?
        # - What percentage of all transactions are fraud?
        #
        # SQL logic used:
        # - Aggregate functions: COUNT, SUM
        # - Rate calculation using fraud count / total count
        #
        # Why this query matters:
        # This is the starting point for any fraud investigation because it gives
        # the overall level of exposure before segmenting into products, devices or time.
        "sql": """
SELECT
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions;
""".strip(),
    },
    {
        "name": "Fraud by product code",
        "category": "Foundational",
        "question": "Which product codes carry the highest fraud rate?",
        # Purpose:
        # Compare fraud across transaction product categories.
        #
        # What this helps answer:
        # - Which product category is riskiest?
        # - Is fraud evenly spread or concentrated in a few products?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY to segment by product code
        # - HAVING to remove very small groups that can distort rate comparisons
        # - ORDER BY to surface the riskiest groups first
        #
        # Why this query matters:
        # This is one of the clearest segmentation queries in the project and is a
        # classic example of grouped fraud rate analysis.
        "sql": """
SELECT
    product_cd,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY product_cd
HAVING COUNT(*) >= 25
ORDER BY fraud_rate_pct DESC, total_transactions DESC;
""".strip(),
    },
    {
        "name": "Fraud by card network",
        "category": "Foundational",
        "question": "Which card network is most exposed to fraud volume and rate?",
        # Purpose:
        # Compare fraud behavior across card network companies.
        #
        # What this helps answer:
        # - Which card network contributes the most fraud?
        # - Does one network have a higher fraud rate than others?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY on a categorical variable
        # - COALESCE to handle missing values explicitly as "Unknown"
        # - HAVING to remove tiny segments
        #
        # Why this query matters:
        # It shows practical null handling and business-friendly segmentation.
        "sql": """
SELECT
    COALESCE(card4, 'Unknown') AS card_network,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY COALESCE(card4, 'Unknown')
HAVING COUNT(*) >= 25
ORDER BY fraud_transactions DESC, fraud_rate_pct DESC;
""".strip(),
    },
    {
        "name": "Fraud by funding type",
        "category": "Foundational",
        "question": "How does fraud compare between debit and credit cards?",
        # Purpose:
        # Compare fraud exposure across funding types such as debit and credit.
        #
        # What this helps answer:
        # - Is one funding type more exposed to fraud?
        # - Is the difference driven by raw volume or by rate?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY on funding type
        # - COALESCE for missing values
        # - HAVING for stable group sizes
        #
        # Why this query matters:
        # It reuses the same analytical pattern as the card network query,
        # which reusses the same SQL structure to a new dimension.
        "sql": """
SELECT
    COALESCE(card6, 'Unknown') AS funding_type,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY COALESCE(card6, 'Unknown')
HAVING COUNT(*) >= 25
ORDER BY fraud_rate_pct DESC, total_transactions DESC;
""".strip(),
    },
    {
        "name": "Fraud by purchaser email domain",
        "category": "Foundational",
        "question": "Which purchaser email domains appear most often in fraud cases?",
        # Purpose:
        # Investigate whether specific email domains appear frequently in fraud activity.
        #
        # What this helps answer:
        # - Are some email providers overrepresented in fraud?
        # - Which domains deserve closer review?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY email domain
        # - COALESCE to keep missing values visible
        # - HAVING to avoid noisy low-volume domains
        # - LIMIT to keep the result focused on the top segments
        #
        # Why this query matters:
        # This is a strong example of top-N grouped analysis with thresholding.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Daily fraud trend",
        "category": "Investigative",
        "question": "How does fraud move over time day by day?",
        # Purpose:
        # Track fraud behavior at the daily level.
        #
        # What this helps answer:
        # - Are there visible spikes in fraud activity?
        # - Is fraud stable or volatile over time?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY on a date field
        # - ORDER BY chronological sequence
        #
        # Why this query matters:
        # This is one of the core time-series views in the project and supports
        # charting and trend inspection.
        "sql": """
SELECT
    event_date,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY event_date
ORDER BY event_date;
""".strip(),
    },
    {
        "name": "Weekly fraud trend",
        "category": "Investigative",
        "question": "What does fraud look like at a weekly level?",
        # Purpose:
        # Smooth the daily view into a weekly summary.
        #
        # What this helps answer:
        # - Does fraud shift meaningfully from week to week?
        # - Are there broader patterns that are less visible in daily noise?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY on event_week
        # - ORDER BY chronological sequence
        #
        # Why this query matters:
        # Weekly aggregation is useful when daily data is noisy and we want a cleaner trend.
        "sql": """
SELECT
    event_week,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY event_week
ORDER BY event_week;
""".strip(),
    },
    {
        "name": "Hourly fraud pattern",
        "category": "Investigative",
        "question": "Are there specific hours where fraud concentrates?",
        # Purpose:
        # Check whether fraud clusters at certain times of day.
        #
        # What this helps answer:
        # - Are there hours with unusually high fraud activity?
        # - Does time-of-day behavior suggest operational or behavioral patterns?
        #
        # SQL logic used:
        # - Timestamp feature extraction using strftime
        # - Aggregate functions
        # - GROUP BY extracted hour
        #
        # Why this query matters:
        # This shows how to derive analytical features from timestamps rather than relying
        # only on raw stored columns.
        "sql": """
SELECT
    strftime('%H', event_ts) AS hour_of_day,
    COUNT(*) AS total_transactions,
    SUM(is_fraud) AS fraud_transactions,
    ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY strftime('%H', event_ts)
ORDER BY hour_of_day;
""".strip(),
    },
    {
        "name": "Fraud by transaction amount band",
        "category": "Investigative",
        "question": "Which amount bands hold the most fraud cases?",
        # Purpose:
        # Convert raw transaction amounts into interpretable ranges.
        #
        # What this helps answer:
        # - Is fraud concentrated in small, medium, or large transaction ranges?
        # - Are there specific amount bands that deserve closer monitoring?
        #
        # SQL logic used:
        # - CTE to create a transformed working table
        # - CASE WHEN to bucket a continuous variable into bands
        # - Aggregate functions after bucketing
        #
        # Why this query matters:
        # This is a strong analytical pattern because it transforms a raw numeric column
        # into business-friendly segments before analysis.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Top risky addresses",
        "category": "Investigative",
        "question": "Which billing address segments have elevated fraud exposure?",
        # Purpose:
        # Compare fraud behavior across billing address segments.
        #
        # What this helps answer:
        # - Are some address segments more exposed to fraud than others?
        # - Which address groups are most suspicious by rate or count?
        #
        # SQL logic used:
        # - Aggregate functions
        # - GROUP BY address segment
        # - CAST for consistent display
        # - COALESCE for null handling
        # - HAVING to remove unstable small groups
        # - LIMIT for top-risk focus
        #
        # Why this query matters:
        # It is another example of segmentation analysis with guardrails for low-volume groups.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Browser by device type",
        "category": "Investigative",
        "question": "Which browser and device combinations show up most often in fraud cases?",
        # Purpose:
        # Investigate fraud at the level of browser-device combinations.
        #
        # What this helps answer:
        # - Are there suspicious combinations of browser and device type?
        # - Does fraud cluster in a few identity patterns?
        #
        # SQL logic used:
        # - LEFT JOIN to combine transactions with identity data
        # - Aggregate functions across joined tables
        # - GROUP BY across two dimensions
        # - COALESCE for null handling
        # - HAVING to remove very small combinations
        #
        # Why this query matters:
        # This is one of the strongest multi-dimensional investigations in the project
        # because it combines two identity fields after joining datasets.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Fraud concentration by device type",
        "category": "Investigative",
        "question": "How does fraud compare across device types?",
        # Purpose:
        # Get a simpler device-level fraud comparison.
        #
        # What this helps answer:
        # - Are mobile or desktop transactions more exposed?
        # - Is one device type more represented in fraud activity?
        #
        # SQL logic used:
        # - LEFT JOIN to bring in identity data
        # - Aggregate functions
        # - GROUP BY device type
        # - COALESCE for missing values
        #
        # Why this query matters:
        # This is a clean one-dimensional follow-up to the browser-device combination query.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Top repeating fraud card signatures",
        "category": "Advanced",
        "question": "Which card signatures repeat most often inside fraud cases?",
        # Purpose:
        # Identify combinations of card attributes that repeatedly appear in fraud.
        #
        # What this helps answer:
        # - Are certain card signatures recurring in fraudulent activity?
        # - Do a small set of card combinations account for repeated fraud cases?
        #
        # SQL logic used:
        # - WHERE filter to keep only fraud rows
        # - GROUP BY across multiple card fields
        # - HAVING to keep only repeating signatures
        #
        # Why this query matters:
        # This is a pattern repetition query rather than a general segmentation query,
        # which makes it feel closer to investigative fraud work.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Seven-day rolling fraud rate",
        "category": "Advanced",
        "question": "How is fraud moving when smoothed over a 7-day window?",
        # Purpose:
        # Smooth the daily fraud rate to reduce noise and show trend direction more clearly.
        #
        # What this helps answer:
        # - Is fraud really rising or falling, beyond daily fluctuation?
        # - What does the short-term trend look like when smoothed?
        #
        # SQL logic used:
        # - CTE to build daily totals first
        # - Window functions with OVER(...)
        # - Rolling 7-day sums using ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        #
        # Why this query matters:
        # Window-function-based trend analysis.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Week-over-week fraud change",
        "category": "Advanced",
        "question": "Which weeks showed the sharpest changes in fraud rate?",
        # Purpose:
        # Compare each week’s fraud rate to the previous week.
        #
        # What this helps answer:
        # - When did fraud rate jump or drop the most?
        # - Which weeks deserve closer review?
        #
        # SQL logic used:
        # - CTE for weekly aggregation
        # - Window function LAG to reference the previous row
        # - Period-over-period comparison
        #
        # Why this query matters:
        # Analytical SQL pattern used for week-over-week or month-over-month change analysis.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Rank top product codes by daily fraud rate",
        "category": "Advanced",
        "question": "Which product codes lead fraud rate on each day?",
        # Purpose:
        # Rank product codes within each day by fraud rate.
        #
        # What this helps answer:
        # - Which products are leading fraud risk on a day-by-day basis?
        # - Does the riskiest product change over time?
        #
        # SQL logic used:
        # - CTE for daily product-level aggregation
        # - Window function DENSE_RANK partitioned by day
        # - Partitioned ranking within each event_date
        #
        # Why this query matters:
        # It demonstrates how ranking logic can be applied within groups rather than across the full table.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Fraud share contribution by product code",
        "category": "Advanced",
        "question": "How much of total fraud is contributed by each product code?",
        # Purpose:
        # Measure each product code’s share of total fraud volume.
        #
        # What this helps answer:
        # - Which product codes contribute the most to total fraud?
        # - Is fraud concentrated in a small number of product groups?
        #
        # SQL logic used:
        # - CTE for product-level fraud totals
        # - CTE for overall total fraud
        # - CROSS JOIN to combine each segment with the grand total
        # - Share calculation
        #
        # Why this query matters:
        # This goes beyond raw counts and rates by showing proportional contribution.
        "sql": """
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
""".strip(),
    },
    {
        "name": "Fraud rate by distance availability",
        "category": "Advanced",
        "question": "Is fraud higher when distance fields are missing or present?",
        # Purpose:
        # Test whether missingness in distance-related fields is associated with fraud.
        #
        # What this helps answer:
        # - Does fraud behave differently when dist1 or dist2 is absent?
        # - Is missingness itself a useful analytical signal?
        #
        # SQL logic used:
        # - CTE to create presence/missing flags using CASE WHEN
        # - Aggregate comparison across missing/present combinations
        #
        # Why this query matters:
        # This is a useful example of feature engineering directly inside SQL.
        # Instead of analyzing the raw numeric values, it analyzes whether the field exists at all.
        "sql": """
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
""".strip(),
    },
]


# Categories are derived dynamically so the UI can stay in sync with the query catalog.
CATEGORIES = sorted({item["category"] for item in SQL_QUERIES})