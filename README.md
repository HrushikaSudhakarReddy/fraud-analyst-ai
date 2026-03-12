# Fraud Analyst — SQL-Powered Investigation Assistant

This project explores how a fraud analyst might investigate suspicious transaction patterns using a combination of **structured SQL queries** and a lightweight **agentic interface**.

Instead of manually writing queries for every investigation, the application allows a user to ask questions in natural language. The system translates those questions into SQL, executes them against a real financial transaction dataset, and returns the results along with the generated query.

---

## Dataset

The analysis is built on the **IEEE-CIS Fraud Detection dataset**, a public dataset of financial transactions used for fraud research.

Dataset source:

https://www.kaggle.com/competitions/ieee-fraud-detection

The dataset contains:

- ~590,000 transaction records
- fraud labels for each transaction
- product categories
- card network information
- device and browser metadata
- transaction amounts and timestamps

Only the training dataset is used in this project.

---

## Project Goal

Fraud analysts typically work by asking investigative questions such as:

- Which product categories carry the highest fraud rate?
- How does fraud activity change over time?
- Are certain device or browser combinations associated with fraud?
- Are fraudulent transactions concentrated within certain amount ranges?

Answering these questions normally requires writing SQL queries repeatedly.

This project demonstrates a workflow where:

1. A question is asked in natural language  
2. The assistant determines the relevant SQL investigation  
3. The query is executed on the transaction database  
4. The result and generated SQL are returned to the user

This keeps the **analytical logic transparent** while reducing the friction of writing queries.

---

## System Overview

The application is built around three core components:

### 1. Transaction Database

The IEEE transaction dataset is converted into a local SQL database.

Key table:

`transactions`

Important fields used in analysis:

- `event_date`
- `transaction_amt`
- `product_cd`
- `card4`
- `card6`
- `device_type`
- `browser`
- `email_domain`
- `is_fraud`

---

### 2. SQL Investigation Layer

A curated set of investigation queries forms the analytical backbone of the system.

Examples include:

- fraud rate by product category
- fraud trends over time
- fraud by device and browser
- fraud by transaction amount bands
- fraud by card network

These queries represent the types of investigations analysts commonly run during fraud reviews.

---

### 3. Analyst Assistant

The interface accepts natural language questions and maps them to SQL investigations.

The assistant can operate in two modes:

**Schema-matched assistant**
Maps questions to known investigation patterns using the database schema.

**OpenAI-assisted mode**
Uses an LLM to generate SQL dynamically based on the schema.

The generated SQL is always visible in the interface for transparency.

---

## Interface

The application provides a minimal investigation workspace.

Features include:

- Dataset overview metrics
- Fraud activity visualizations
- Natural language query interface
- Generated SQL inspection
- Saved investigation queries in the sidebar

The design intentionally keeps the interface simple so the focus remains on the analytical workflow.

---

## Example Questions

Examples of supported investigations:

- Which product codes have the highest fraud rate?
- How does fraud activity change day-to-day?
- Which device and browser combinations appear most often in fraud cases?
- Are fraud cases concentrated in specific transaction amount bands?
- Which card networks appear most frequently in fraud cases?

---

## Running the Project

### 1. Download the dataset

Download the dataset from Kaggle:

https://www.kaggle.com/competitions/ieee-fraud-detection

Place the following files inside the `data/` folder:
train_transaction.csv
train_identity.csv

---

### 2. Prepare the database

Run the preparation script:
python scripts/prepare_ieee_data.py

This will:

- read the raw CSV files
- extract relevant columns
- create a local SQLite database
- load the transactions into SQL tables

---

### 3. Start the application
streamlit run app.py

The investigation interface will open in your browser.

---

## Project Structure
fraud-analyst/
app.py
scripts/
src/
data/
assets/

Key components:

- `app.py` — Streamlit interface
- `src/agent.py` — question-to-SQL mapping
- `src/db.py` — database connection utilities
- `src/sql_catalog.py` — curated investigation queries
- `scripts/prepare_ieee_data.py` — dataset preparation
- `assets/rhode.css` — minimal UI styling

---

## What This Project Demonstrates

This project focuses on two core skills:

### SQL-based analytics

The investigation workflow is built around SQL queries that:

- aggregate fraud metrics
- segment transactions
- analyze time-based patterns
- identify concentration of fraud risk

### Agentic interfaces for analytics

The project explores how natural language interfaces can sit on top of structured analytical systems, allowing users to query data more interactively while maintaining SQL transparency.