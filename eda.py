import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

conn = sqlite3.connect("/home/claude/olist_project/olist.db")

# ---------------------------------------------------------------
# Build one master, order-level table (this becomes the Power BI fact table)
# ---------------------------------------------------------------
master_sql = """
WITH order_delivery AS (
    SELECT
        o.order_id, o.customer_id,
        o.order_purchase_timestamp,
        substr(o.order_purchase_timestamp,1,7) AS order_month,
        o.order_estimated_delivery_date,
        o.order_delivered_customer_date,
        julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS delay_days,
        CASE WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date)
             THEN 1 ELSE 0 END AS is_late
    FROM orders o
    WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
),
order_revenue AS (
    SELECT order_id, SUM(price) AS item_revenue, SUM(freight_value) AS freight_revenue,
           SUM(price+freight_value) AS total_revenue
    FROM order_items GROUP BY order_id
),
order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
)
SELECT
    d.order_id, d.order_month, d.delay_days, d.is_late,
    r.item_revenue, r.freight_revenue, r.total_revenue,
    rv.review_score,
    c.customer_state, c.customer_city
FROM order_delivery d
JOIN order_revenue r ON d.order_id = r.order_id
JOIN order_review rv ON d.order_id = rv.order_id
JOIN customers c ON d.customer_id = c.customer_id
"""
master = pd.read_sql_query(master_sql, conn)
print("Master table shape:", master.shape)
master.to_csv("/home/claude/olist_project/exports/master_orders.csv", index=False)

# ---------------------------------------------------------------
# Aggregate: seller-level performance table (for dashboard drilldown)
# ---------------------------------------------------------------
seller_sql = """
WITH order_delivery AS (
    SELECT o.order_id,
        julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date) AS delay_days,
        CASE WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date)
             THEN 1 ELSE 0 END AS is_late
    FROM orders o
    WHERE o.order_status='delivered' AND o.order_delivered_customer_date IS NOT NULL
),
seller_items AS (
    SELECT DISTINCT seller_id, order_id FROM order_items
),
seller_revenue AS (
    SELECT seller_id, SUM(price+freight_value) AS seller_revenue
    FROM order_items GROUP BY seller_id
)
SELECT
    si.seller_id,
    s.seller_state,
    COUNT(*) AS num_orders,
    ROUND(AVG(od.delay_days),2) AS avg_delay_days,
    ROUND(100.0*SUM(od.is_late)/COUNT(*),2) AS late_pct,
    sr.seller_revenue
FROM seller_items si
JOIN order_delivery od ON si.order_id = od.order_id
JOIN sellers s ON si.seller_id = s.seller_id
JOIN seller_revenue sr ON si.seller_id = sr.seller_id
GROUP BY si.seller_id
HAVING COUNT(*) >= 10
ORDER BY late_pct DESC
"""
sellers = pd.read_sql_query(seller_sql, conn)
sellers.to_csv("/home/claude/olist_project/exports/seller_performance.csv", index=False)
print("Seller table shape:", sellers.shape)

conn.close()

# ---------------------------------------------------------------
# CHART 1: Review score, late vs on-time
# ---------------------------------------------------------------
plt.figure(figsize=(6,4))
grp = master.groupby("is_late")["review_score"].mean()
labels = ["On-time", "Late"]
plt.bar(labels, [grp[0], grp[1]], color=["#2ca02c", "#d62728"])
plt.ylabel("Average Review Score")
plt.title("Review Score: On-time vs Late Delivery")
for i, v in enumerate([grp[0], grp[1]]):
    plt.text(i, v+0.05, f"{v:.2f}", ha="center", fontweight="bold")
plt.ylim(0,5)
plt.tight_layout()
plt.savefig("/home/claude/olist_project/exports/chart_review_score.png", dpi=150)
plt.close()

# ---------------------------------------------------------------
# CHART 2: Late % by state (top 10)
# ---------------------------------------------------------------
state_late = master.groupby("customer_state").agg(
    num_orders=("order_id","count"),
    late_pct=("is_late","mean")
).reset_index()
state_late = state_late[state_late["num_orders"]>=30]
state_late["late_pct"] = state_late["late_pct"]*100
state_late = state_late.sort_values("late_pct", ascending=False).head(10)

plt.figure(figsize=(8,5))
plt.barh(state_late["customer_state"], state_late["late_pct"], color="#d62728")
plt.xlabel("Late Delivery %")
plt.title("Top 10 States by Late Delivery Rate")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("/home/claude/olist_project/exports/chart_late_by_state.png", dpi=150)
plt.close()

# ---------------------------------------------------------------
# CHART 3: Monthly order volume + late % trend
# ---------------------------------------------------------------
monthly = master.groupby("order_month").agg(
    num_orders=("order_id","count"),
    late_pct=("is_late","mean"),
    revenue=("total_revenue","sum")
).reset_index()
monthly = monthly[monthly["order_month"] >= "2017-01"]  # data gets sparse before this

fig, ax1 = plt.subplots(figsize=(10,5))
ax1.bar(monthly["order_month"], monthly["num_orders"], color="#1f77b4", alpha=0.6, label="Orders")
ax1.set_ylabel("Number of Orders", color="#1f77b4")
ax1.tick_params(axis='x', rotation=90)
ax2 = ax1.twinx()
ax2.plot(monthly["order_month"], monthly["late_pct"]*100, color="#d62728", marker="o", label="Late %")
ax2.set_ylabel("Late Delivery %", color="#d62728")
plt.title("Monthly Order Volume vs Late Delivery Rate")
fig.tight_layout()
plt.savefig("/home/claude/olist_project/exports/chart_monthly_trend.png", dpi=150)
plt.close()

print("\nAll exports and charts created in /home/claude/olist_project/exports/")
