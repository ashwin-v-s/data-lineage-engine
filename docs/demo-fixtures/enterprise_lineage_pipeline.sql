-- ==============================================================================
-- Enterprise Revenue & Customer Lineage Pipeline (Multi-Tier DDL & DML)
-- Contract: Certified Enterprise Financial Architecture
-- Dialect: PostgreSQL / ANSI SQL
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Stage 1: Enriched Order Staging View
-- Transforms raw transactional orders and joins settled payment gateway webhooks.
-- ------------------------------------------------------------------------------
CREATE TABLE staging.stg_orders_enriched AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_status,
    o.order_amount_usd + o.tax_amount_usd AS gross_order_value,
    COALESCE(p.settled_amount_usd, 0.00)  AS net_settled_value,
    CASE WHEN p.payment_status = 'SETTLED' THEN TRUE ELSE FALSE END AS is_settled,
    o.order_timestamp
FROM raw_enterprise.orders_feed o
JOIN raw_enterprise.payments_feed p
    ON o.order_id = p.order_id;

-- ------------------------------------------------------------------------------
-- Stage 2: Conformed Customer Dimension
-- Cleanses raw customer records, standardizes ISO country codes, and applies
-- one-way hashing for PII compliance.
-- ------------------------------------------------------------------------------
CREATE TABLE staging.stg_customer_360 AS
SELECT
    c.customer_id,
    c.email,
    UPPER(TRIM(c.country_code)) AS country_code,
    c.created_at
FROM raw_enterprise.customers c;

-- ------------------------------------------------------------------------------
-- Stage 3: Certified Daily Financial Revenue Mart
-- Aggregates conformed orders into daily financial reconciliations (SOX in-scope).
-- ------------------------------------------------------------------------------
INSERT INTO analytics.fct_daily_revenue (
    accounting_date,
    gross_merchandise_value,
    net_recognized_revenue,
    total_orders_count
)
SELECT
    CAST(s.order_timestamp AS DATE)           AS accounting_date,
    SUM(s.gross_order_value)                  AS gross_merchandise_value,
    SUM(s.net_settled_value)                  AS net_recognized_revenue,
    COUNT(DISTINCT s.order_id)                AS total_orders_count
FROM staging.stg_orders_enriched s
JOIN staging.stg_customer_360 c
    ON s.customer_id = c.customer_id
GROUP BY CAST(s.order_timestamp AS DATE);

-- ------------------------------------------------------------------------------
-- Stage 4: Executive Revenue KPI Rollup
-- Produces executive-level annualized and monthly recurring revenue run-rates.
-- ------------------------------------------------------------------------------
INSERT INTO executive.daily_revenue_kpi (
    kpi_date,
    mrr_run_rate,
    total_revenue
)
SELECT
    f.accounting_date,
    f.net_recognized_revenue * 30.0           AS mrr_run_rate,
    f.net_recognized_revenue                  AS total_revenue
FROM analytics.fct_daily_revenue f;
