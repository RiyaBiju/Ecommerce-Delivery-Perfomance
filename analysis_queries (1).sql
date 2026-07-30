-- ============================================================
-- E-Commerce Delivery Performance & Revenue Impact Analysis
-- Dataset: Olist Brazilian E-Commerce (~99K orders, 2016-2018)
-- ============================================================

-- --------------------------------------------------------------
-- 1. Base CTE: one row per delivered order with delivery delay flag
-- --------------------------------------------------------------
WITH order_delivery AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_purchase_timestamp,
        o.order_estimated_delivery_date,
        o.order_delivered_customer_date,
        julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS delay_days,
        CASE
            WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date)
            THEN 1 ELSE 0
        END AS is_late
    FROM orders o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
),

-- --------------------------------------------------------------
-- 2. Revenue per order (sum of item price + freight)
-- --------------------------------------------------------------
order_revenue AS (
    SELECT
        order_id,
        SUM(price) AS item_revenue,
        SUM(freight_value) AS freight_revenue,
        SUM(price + freight_value) AS total_revenue
    FROM order_items
    GROUP BY order_id
),

-- --------------------------------------------------------------
-- 3. Review score per order
-- --------------------------------------------------------------
order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews
    GROUP BY order_id
),

-- --------------------------------------------------------------
-- 4. Join everything + customer state (via customers table)
-- --------------------------------------------------------------
joined AS (
    SELECT
        d.order_id,
        d.is_late,
        d.delay_days,
        r.total_revenue,
        rv.review_score,
        c.customer_state
    FROM order_delivery d
    JOIN order_revenue r  ON d.order_id = r.order_id
    JOIN order_review rv  ON d.order_id = rv.order_id
    JOIN customers c      ON d.customer_id = c.customer_id
)

-- --------------------------------------------------------------
-- 5. Headline metric: avg review score, late vs on-time
-- --------------------------------------------------------------
SELECT
    is_late,
    COUNT(*) AS num_orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(SUM(total_revenue), 2) AS total_revenue
FROM joined
GROUP BY is_late;

-- ================================================================
-- QUERY B: Revenue "at risk" from late deliveries
-- Logic: revenue tied to orders with review_score <= 2 AND late,
-- as a proxy for lost repeat-purchase revenue
-- ================================================================
WITH order_delivery AS (
    SELECT
        o.order_id, o.customer_id,
        CASE WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date)
             THEN 1 ELSE 0 END AS is_late
    FROM orders o
    WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
),
order_revenue AS (
    SELECT order_id, SUM(price + freight_value) AS total_revenue
    FROM order_items GROUP BY order_id
),
order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
),
joined AS (
    SELECT d.order_id, d.is_late, r.total_revenue, rv.review_score
    FROM order_delivery d
    JOIN order_revenue r ON d.order_id = r.order_id
    JOIN order_review rv ON d.order_id = rv.order_id
)
SELECT
    ROUND(SUM(CASE WHEN is_late = 1 AND review_score <= 2 THEN total_revenue ELSE 0 END), 2) AS revenue_at_risk,
    ROUND(SUM(total_revenue), 2) AS total_revenue,
    ROUND(100.0 * SUM(CASE WHEN is_late = 1 AND review_score <= 2 THEN total_revenue ELSE 0 END) / SUM(total_revenue), 2) AS pct_revenue_at_risk
FROM joined;

-- ================================================================
-- QUERY C: Worst-performing states by late delivery rate (window functions)
-- ================================================================
WITH order_delivery AS (
    SELECT
        o.order_id, o.customer_id,
        CASE WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date)
             THEN 1 ELSE 0 END AS is_late
    FROM orders o
    WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
),
state_stats AS (
    SELECT
        c.customer_state,
        COUNT(*) AS num_orders,
        SUM(d.is_late) AS late_orders,
        ROUND(100.0 * SUM(d.is_late) / COUNT(*), 2) AS late_pct
    FROM order_delivery d
    JOIN customers c ON d.customer_id = c.customer_id
    GROUP BY c.customer_state
    HAVING COUNT(*) >= 30   -- filter out tiny-sample states
)
SELECT
    customer_state,
    num_orders,
    late_orders,
    late_pct,
    RANK() OVER (ORDER BY late_pct DESC) AS worst_rank
FROM state_stats
ORDER BY late_pct DESC
LIMIT 10;

-- ================================================================
-- QUERY D: Worst-performing sellers by avg delay (window functions)
-- ================================================================
WITH order_delivery AS (
    SELECT
        o.order_id,
        julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS delay_days
    FROM orders o
    WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
),
seller_orders AS (
    SELECT DISTINCT oi.seller_id, oi.order_id
    FROM order_items oi
),
seller_delay AS (
    SELECT
        so.seller_id,
        AVG(od.delay_days) AS avg_delay_days,
        COUNT(*) AS num_orders
    FROM seller_orders so
    JOIN order_delivery od ON so.order_id = od.order_id
    GROUP BY so.seller_id
    HAVING COUNT(*) >= 20
)
SELECT
    seller_id,
    num_orders,
    ROUND(avg_delay_days, 2) AS avg_delay_days,
    NTILE(4) OVER (ORDER BY avg_delay_days DESC) AS delay_quartile
FROM seller_delay
ORDER BY avg_delay_days DESC
LIMIT 15;
