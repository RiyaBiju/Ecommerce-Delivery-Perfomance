# E-Commerce Delivery Performance & Revenue Impact Analysis

Built on the real **Olist Brazilian E-Commerce dataset** (~99K orders, 2016–2018).
This matches the project already listed on your resume — now with actual code and real numbers behind it.

## Key findings (verified from real data)

| Metric | Value |
|---|---|
| Delivered orders analyzed | 95,824 |
| Late deliveries | 7,661 (8.0%) |
| Avg review score — on-time | 4.29 |
| Avg review score — late | 2.57 |
| **Review score drop from late delivery** | **1.72 points** |
| Total revenue (all orders) | R$15.29M |
| Revenue tied to late orders | R$1.31M (8.6% of total) |
| Worst state for late delivery | AL (23.9% late) |

These numbers back up your resume bullets almost exactly (1.7 point drop, ~8% revenue impact). Nice.

## Files in this folder

- **`build_db.py`** — loads the 9 raw Olist CSVs into a SQLite database (`olist.db`)
- **`olist.db`** — the ready-to-query database (also portable to SQL Server/Postgres — see note below)
- **`analysis_queries.sql`** — the actual SQL: CTEs + window functions (RANK, NTILE) for delay analysis, revenue-at-risk, worst states, worst sellers
- **`run_analysis.py`** — runs the queries and prints results
- **`eda.py`** — Python EDA (Pandas) that builds the master order-level table and generates charts
- **`master_orders.csv`** — one row per order: delay, revenue, review score, state — **this is your Power BI fact table**
- **`seller_performance.csv`** — seller-level rollup for a drilldown page
- **`chart_review_score.png`**, **`chart_late_by_state.png`**, **`chart_monthly_trend.png`** — quick-look visuals

## Note on "SQL Server" (matches your resume wording)

I used SQLite here since it's portable and free to run anywhere without installing a server. The SQL in `analysis_queries.sql` is
standard ANSI SQL (CTEs, window functions) and will run in SQL Server / Azure SQL with just minor syntax tweaks:
- `julianday(x) - julianday(y)` → `DATEDIFF(day, y, x)`
- Everything else (CTEs, RANK, NTILE, HAVING) is identical syntax.

If you want to genuinely run this in SQL Server for the resume claim to be 100% accurate: install **SQL Server Express** (free) +
**SSMS**, import the CSVs via the Import Wizard, and run the same queries with the DATEDIFF swap. Happy to rewrite the queries in
T-SQL syntax if you want to do that.

## Building the Power BI Dashboard

1. Open Power BI Desktop → **Get Data → Text/CSV** → load `master_orders.csv` and `seller_performance.csv`
2. In **Power Query Editor**: set `order_month` as a proper date/text column, confirm `is_late` is a whole number (0/1)
3. Create these visuals:
   - **KPI cards**: Total Orders, Total Revenue, Late Delivery %, Avg Review Score
   - **Line chart**: `order_month` (x-axis) vs `num_orders` and a second measure for `late %` (dual axis) — recreates `chart_monthly_trend.png`
   - **Bar chart**: `customer_state` vs `late_pct` (top 10) — recreates `chart_late_by_state.png`
   - **Bar/clustered column**: `is_late` vs avg `review_score` — recreates `chart_review_score.png`
   - **Table/matrix**: `seller_performance.csv` sorted by `late_pct` descending — worst sellers to flag operationally
4. Add a **slicer** on `customer_state` so the dashboard filters interactively (this is what "identifying worst-performing states and seller segments to prioritize for operational fixes" should look like live)
5. Suggested DAX measures:
   ```
   Late Delivery % = DIVIDE(SUM(master_orders[is_late]), COUNTROWS(master_orders))
   Avg Review Score = AVERAGE(master_orders[review_score])
   Revenue at Risk = CALCULATE(SUM(master_orders[total_revenue]), master_orders[is_late]=1, master_orders[review_score]<=2)
   ```

Once you've built it, take a screenshot for your portfolio/resume — same as your PhonePe one.
