from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.agent import ask
from src.db import db_exists, run_query, scalar
from src.sql_catalog import SQL_QUERIES

st.set_page_config(
    page_title="Fraud Analyst",
    page_icon="◌",
    layout="wide",
)

css_path = Path(__file__).resolve().parent / "assets" / "rhode.css"
st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 1.4rem;
        max-width: 980px;
    }

    div[data-testid="stMetric"] {
        background: transparent;
        padding-top: 0.1rem;
        padding-bottom: 0.1rem;
    }

    .question-label {
        font-size: 0.82rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #6f6a64;
        margin-top: 1.2rem;
        margin-bottom: 0.45rem;
        font-weight: 600;
    }

    .question-helper {
        font-size: 1.55rem;
        line-height: 1.25;
        color: #1f1f1f;
        margin-bottom: 0.85rem;
        font-weight: 500;
    }

    div[data-testid="stTextArea"] textarea {
        min-height: 150px !important;
        border-radius: 18px !important;
        border: 1px solid #d8d2ca !important;
        background: #f7f5f2 !important;
        padding: 1.1rem 1rem !important;
        font-size: 1.03rem !important;
        line-height: 1.55 !important;
    }

    div[data-testid="stTextArea"] textarea:focus {
        border: 1px solid #b9b0a5 !important;
        box-shadow: none !important;
    }

    div[data-testid="stButton"] > button {
        border-radius: 999px !important;
        min-height: 46px !important;
        font-size: 1rem !important;
    }

    .compact-gap {
        margin-top: 0.35rem;
        margin-bottom: 0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Ask the Analyst</div>
            <div class="hero-subtitle">
                Fraud investigation workspace built on handwritten SQL and a schema-aware analyst assistant.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.warning("No database found yet.")
    st.code("python scripts/prepare_ieee_data.py\nstreamlit run app.py", language="bash")


def metrics_row() -> None:
    total_tx = scalar("SELECT COUNT(*) FROM transactions") or 0
    total_fraud = scalar("SELECT COALESCE(SUM(is_fraud), 0) FROM transactions") or 0
    fraud_rate = scalar("SELECT ROUND(100.0 * SUM(is_fraud) / COUNT(*), 2) FROM transactions") or 0
    distinct_products = scalar("SELECT COUNT(DISTINCT product_cd) FROM transactions") or 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Transactions", f"{int(total_tx):,}")
    col2.metric("Fraud Cases", f"{int(total_fraud):,}")
    col3.metric("Fraud Rate", f"{fraud_rate}%")
    col4.metric("Product Codes", f"{int(distinct_products):,}")


def quick_view() -> None:
    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.markdown('<div class="section-label compact-gap">Daily fraud trend</div>', unsafe_allow_html=True)
        daily = run_query(
            """
            SELECT event_date, SUM(is_fraud) AS fraud_transactions
            FROM transactions
            GROUP BY event_date
            ORDER BY event_date
            """
        )
        if not daily.empty:
            daily = daily.set_index("event_date")
            st.line_chart(daily, use_container_width=True)
        else:
            st.info("No daily data available.")

    with right:
        st.markdown('<div class="section-label compact-gap">Fraud by product code</div>', unsafe_allow_html=True)
        by_product = run_query(
            """
            SELECT product_cd, SUM(is_fraud) AS fraud_transactions
            FROM transactions
            GROUP BY product_cd
            ORDER BY fraud_transactions DESC
            """
        )
        if not by_product.empty:
            by_product = by_product.set_index("product_cd")
            st.bar_chart(by_product, use_container_width=True)
        else:
            st.info("No product-level data available.")


def analyst_notes() -> None:
    st.markdown("### Analyst Notes")
    st.caption("Handwritten investigations used as the SQL backbone for the assistant.")

    options = {item["name"]: item for item in SQL_QUERIES}
    selected_name = st.selectbox("Saved investigation", list(options))
    item = options[selected_name]

    st.markdown("**Question**")
    st.write(item["question"])
    st.code(item["sql"], language="sql")

    if st.button("Run this investigation", use_container_width=True):
        df = run_query(item["sql"])
        st.dataframe(df, use_container_width=True, hide_index=True)


def main_screen() -> None:
    render_hero()
    metrics_row()

    st.markdown('<div class="question-label">Investigation Workspace</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="question-helper">Ask the fraud analyst a question</div>',
        unsafe_allow_html=True,
    )

    question = st.text_area(
        label="",
        height=150,
        placeholder="Type your fraud analysis question here...",
        key="question_box",
    )

    if st.button("Run analysis", use_container_width=True):
        if not question.strip():
            st.error("Enter a question first.")
            st.stop()

        with st.spinner("Running analysis..."):
            result = ask(question.strip())

        pill = "OpenAI-assisted" if result.mode == "openai" else "Schema-matched assistant"
        st.caption(pill)
        st.markdown("**Answer**")
        st.write(result.summary)
        st.dataframe(result.dataframe, use_container_width=True, hide_index=True)

        with st.expander("View generated SQL"):
            st.code(result.sql, language="sql")

    st.divider()
    quick_view()


if not db_exists():
    render_hero()
    render_empty_state()
else:
    with st.sidebar:
        analyst_notes()
    main_screen()