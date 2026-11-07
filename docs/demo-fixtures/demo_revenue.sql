-- Static lineage example only. This file is parsed; it is never executed.
CREATE TABLE analytics.demo_order_revenue AS
SELECT o.order_id, p.amount
FROM raw.orders AS o
JOIN raw.payments AS p ON p.order_id = o.order_id;
